"""
Tests for FIFO cross-check against IB FifoPnlRealized.

IB reports a realized PnL per sell in the HEADER/DATA format (HEADER/DATA TRNT rows).
We capture it as broker_fifo_pnl_eur and warn if our computed gain differs by > EUR 1.00.
"""
import dataclasses
from datetime import date
from decimal import Decimal

import pytest

from core.models import TransactionType
from core.tax_engine import TaxEngine
from tests.conftest import make_trade

ZERO = Decimal("0")


def _engine(cfg: dict) -> TaxEngine:
    return TaxEngine(cfg, tax_year=2025, person_label="Test")


def _sell_with_broker_pnl(broker_pnl_eur: float | None):
    """SELL of 10 ALV @ 50 EUR = 500 EUR proceeds; buy cost 300 EUR → our gain = 200 EUR."""
    buy  = make_trade("ALV", "DE0008404005", TransactionType.BUY,
                      quantity=10, price_eur=30.0, trade_date=date(2024, 1, 1))
    sell = make_trade("ALV", "DE0008404005", TransactionType.SELL,
                      quantity=10, price_eur=50.0, trade_date=date(2025, 6, 1))
    if broker_pnl_eur is not None:
        sell = dataclasses.replace(sell, broker_fifo_pnl_eur=Decimal(str(broker_pnl_eur)))
    return buy, sell


# ── No broker PnL → never warns ──────────────────────────────────────────────

def test_no_broker_pnl_no_warning(cfg):
    """When broker_fifo_pnl_eur is None (BOS/EOS format), no cross-check warning."""
    buy, sell = _sell_with_broker_pnl(None)
    summary = _engine(cfg).calculate([buy, sell])
    assert not any("mismatch" in w.lower() for w in summary.warnings)


# ── Match within tolerance → no warning ──────────────────────────────────────

def test_exact_match_no_warning(cfg):
    """Broker reports same gain as us → no warning."""
    buy, sell = _sell_with_broker_pnl(200.0)
    summary = _engine(cfg).calculate([buy, sell])
    assert not any("mismatch" in w.lower() for w in summary.warnings)


def test_within_one_euro_no_warning(cfg):
    """Diff of exactly €1.00 is not warned (threshold is strictly > 1.00)."""
    buy, sell = _sell_with_broker_pnl(199.0)   # diff = 1.00
    summary = _engine(cfg).calculate([buy, sell])
    assert not any("mismatch" in w.lower() for w in summary.warnings)


def test_rounding_noise_suppressed(cfg):
    """Small rounding diff (< €1) is silently ignored."""
    buy, sell = _sell_with_broker_pnl(200.50)   # diff = 0.50
    summary = _engine(cfg).calculate([buy, sell])
    assert not any("mismatch" in w.lower() for w in summary.warnings)


# ── Diff > €1.00 → warns ─────────────────────────────────────────────────────

def test_large_diff_warns(cfg):
    """Broker reports a materially different gain → warning emitted."""
    buy, sell = _sell_with_broker_pnl(150.0)   # our gain=200, broker=150, diff=50
    summary = _engine(cfg).calculate([buy, sell])
    assert any("mismatch" in w.lower() for w in summary.warnings)


def test_warning_contains_symbol(cfg):
    buy, sell = _sell_with_broker_pnl(100.0)
    summary = _engine(cfg).calculate([buy, sell])
    assert any("ALV" in w for w in summary.warnings)


def test_warning_contains_both_values(cfg):
    buy, sell = _sell_with_broker_pnl(100.0)
    summary = _engine(cfg).calculate([buy, sell])
    w = next(w for w in summary.warnings if "mismatch" in w.lower())
    assert "200" in w    # our gain
    assert "100" in w    # broker gain


def test_gain_value_unaffected_by_mismatch(cfg):
    """The warning is informational — our computed gain is still used for tax."""
    buy, sell = _sell_with_broker_pnl(100.0)
    summary = _engine(cfg).calculate([buy, sell])
    assert summary.kz_994 == Decimal("200.00")


# ── eur_gain_loss / eur_cost_basis populated on SELL ─────────────────────────

def test_eur_gain_loss_set_on_sell(cfg):
    """After calculate(), SELL transactions have eur_gain_loss populated."""
    buy, sell = _sell_with_broker_pnl(None)
    _engine(cfg).calculate([buy, sell])
    assert sell.eur_gain_loss is not None
    assert sell.eur_gain_loss == Decimal("200")


def test_eur_cost_basis_set_on_sell(cfg):
    """eur_cost_basis holds the matched purchase cost (10 × 30 EUR = 300)."""
    buy, sell = _sell_with_broker_pnl(None)
    _engine(cfg).calculate([buy, sell])
    assert sell.eur_cost_basis == Decimal("300")


def test_eur_gain_loss_negative_for_loss(cfg):
    """Losses produce a negative eur_gain_loss."""
    buy  = make_trade("ALV", "DE0008404005", TransactionType.BUY,
                      quantity=10, price_eur=50.0, trade_date=date(2024, 1, 1))
    sell = make_trade("ALV", "DE0008404005", TransactionType.SELL,
                      quantity=10, price_eur=30.0, trade_date=date(2025, 6, 1))
    _engine(cfg).calculate([buy, sell])
    assert sell.eur_gain_loss == Decimal("-200")


def test_buy_has_no_eur_gain_loss(cfg):
    """BUY transactions are not touched — eur_gain_loss stays None."""
    buy, _ = _sell_with_broker_pnl(None)
    _engine(cfg).calculate([buy])
    assert buy.eur_gain_loss is None
