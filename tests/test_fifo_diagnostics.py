"""
Tests for FIFO diagnostic warnings:
- ISIN-based auto-alias (single-candidate ticker rename resolved silently)
- ISIN rename hint (ambiguous / qty-mismatch cases still warn)
- Same-day round-trip detection (sell + repurchase, tiny gain → possible FIFO mismatch)
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


# ── ISIN auto-alias ───────────────────────────────────────────────────────────

def test_isin_auto_alias_resolves_single_candidate(cfg):
    """Single matching buy-symbol with same ISIN and sufficient qty → auto-resolved, no warning."""
    buy  = make_trade("OEWA", "AT0000746409", TransactionType.BUY,
                      quantity=10, price_eur=70.0, trade_date=date(2024, 1, 1))
    sell = make_trade("VER",  "AT0000746409", TransactionType.SELL,
                      quantity=10, price_eur=60.0, trade_date=date(2025, 6, 1))
    summary = _engine(cfg).calculate([buy, sell])
    assert summary.unmatched_sells == 0
    assert not any("ticker rename" in w or "no purchase record" in w
                   for w in summary.warnings)


def test_isin_auto_alias_gain_correct(cfg):
    """After auto-alias, gain/loss is computed against the correct FIFO lots."""
    buy  = make_trade("OEWA", "AT0000746409", TransactionType.BUY,
                      quantity=10, price_eur=70.0, trade_date=date(2024, 1, 1))
    sell = make_trade("VER",  "AT0000746409", TransactionType.SELL,
                      quantity=10, price_eur=60.0, trade_date=date(2025, 6, 1))
    summary = _engine(cfg).calculate([buy, sell])
    # proceeds=600, cost=700 → net loss €100 → foreign loss KZ 892
    assert summary.kz_892 == Decimal("100.00")


def test_isin_auto_alias_multiple_candidates_warns(cfg):
    """Two buy-symbols share the same ISIN → ambiguous, can't auto-resolve → rename hint fires."""
    buy_a = make_trade("OEWA",  "AT0000746409", TransactionType.BUY,
                       quantity=10, price_eur=70.0, trade_date=date(2024, 1, 1))
    buy_b = make_trade("VBUND", "AT0000746409", TransactionType.BUY,
                       quantity=10, price_eur=72.0, trade_date=date(2024, 2, 1))
    sell  = make_trade("VER",   "AT0000746409", TransactionType.SELL,
                       quantity=10, price_eur=60.0, trade_date=date(2025, 6, 1))
    summary = _engine(cfg).calculate([buy_a, buy_b, sell])
    assert summary.unmatched_sells == 1
    assert any("ticker rename" in w for w in summary.warnings)


def test_isin_auto_alias_qty_mismatch_warns(cfg):
    """Buy qty < sell qty → auto-alias skipped (qty plausibility fails) → unmatched warning."""
    buy  = make_trade("OEWA", "AT0000746409", TransactionType.BUY,
                      quantity=5, price_eur=70.0, trade_date=date(2024, 1, 1))
    sell = make_trade("VER",  "AT0000746409", TransactionType.SELL,
                      quantity=10, price_eur=60.0, trade_date=date(2025, 6, 1))
    summary = _engine(cfg).calculate([buy, sell])
    assert summary.unmatched_sells == 1


def test_isin_auto_alias_not_triggered_when_explicit_alias_resolves(cfg):
    """Explicit symbol_aliases resolves it first — FIFO queue found, auto-alias not needed."""
    cfg["symbol_aliases"] = {"VER": "OEWA"}
    buy  = make_trade("OEWA", "AT0000746409", TransactionType.BUY,
                      quantity=10, price_eur=70.0, trade_date=date(2024, 1, 1))
    sell = make_trade("VER",  "AT0000746409", TransactionType.SELL,
                      quantity=10, price_eur=60.0, trade_date=date(2025, 6, 1))
    summary = _engine(cfg).calculate([buy, sell])
    assert summary.unmatched_sells == 0
    assert not any("ticker rename" in w for w in summary.warnings)


def test_isin_auto_alias_not_triggered_without_isin(cfg):
    """Without an ISIN on the sell, auto-alias can't run → unmatched warning (no rename hint)."""
    buy  = make_trade("OEWA", "AT0000746409", TransactionType.BUY,
                      quantity=10, price_eur=70.0, trade_date=date(2024, 1, 1))
    sell = make_trade("VER",  "AT0000746409", TransactionType.SELL,
                      quantity=10, price_eur=60.0, trade_date=date(2025, 6, 1))
    sell = dataclasses.replace(sell, isin=None)
    summary = _engine(cfg).calculate([buy, sell])
    assert summary.unmatched_sells == 1
    assert not any("ticker rename" in w for w in summary.warnings)


# ── Same-day round-trip detection ─────────────────────────────────────────────

def test_roundtrip_warns_on_tiny_gain(cfg):
    """Sell + same-day repurchase, gain < 1% of proceeds → suspicious round-trip warning."""
    # Only lot: same-day buy (simulates ticker-rename FIFO matching against wrong lot)
    buy  = make_trade("TST", "US0000000001", TransactionType.BUY,
                      quantity=100, price_eur=55.10, trade_date=date(2025, 6, 1))
    sell = make_trade("TST", "US0000000001", TransactionType.SELL,
                      quantity=100, price_eur=55.00, trade_date=date(2025, 6, 1))
    # proceeds=5500, cost=5510, gain=−10 → 0.18% → suspicious
    summary = _engine(cfg).calculate([buy, sell])
    assert any("round-trip" in w.lower() or "suspicious" in w.lower() for w in summary.warnings)


def test_roundtrip_warns_contains_symbol_and_date(cfg):
    """Round-trip warning includes the symbol and date for easy identification."""
    buy  = make_trade("TST", "US0000000001", TransactionType.BUY,
                      quantity=100, price_eur=55.10, trade_date=date(2025, 6, 1))
    sell = make_trade("TST", "US0000000001", TransactionType.SELL,
                      quantity=100, price_eur=55.00, trade_date=date(2025, 6, 1))
    summary = _engine(cfg).calculate([buy, sell])
    w = next(w for w in summary.warnings if "round-trip" in w.lower() or "suspicious" in w.lower())
    assert "TST" in w
    assert "2025-06-01" in w


def test_roundtrip_no_warn_when_large_gain(cfg):
    """Old lot + same-day repurchase: if FIFO uses old lot the gain is large → no round-trip warning."""
    buy_old = make_trade("TST", "US0000000001", TransactionType.BUY,
                         quantity=100, price_eur=30.0, trade_date=date(2024, 1, 1))
    buy_new = make_trade("TST", "US0000000001", TransactionType.BUY,
                         quantity=100, price_eur=55.10, trade_date=date(2025, 6, 1))
    sell    = make_trade("TST", "US0000000001", TransactionType.SELL,
                         quantity=100, price_eur=55.00, trade_date=date(2025, 6, 1))
    # FIFO uses buy_old (2024), gain = 5500 − 3000 = 2500 → 45% → not suspicious
    summary = _engine(cfg).calculate([buy_old, buy_new, sell])
    assert not any("round-trip" in w.lower() or "suspicious" in w.lower() for w in summary.warnings)


def test_roundtrip_no_warn_without_same_day_buy(cfg):
    """Tiny gain but no same-day buy → no round-trip warning (could be genuine small move)."""
    buy  = make_trade("TST", "US0000000001", TransactionType.BUY,
                      quantity=100, price_eur=55.10, trade_date=date(2024, 1, 1))
    sell = make_trade("TST", "US0000000001", TransactionType.SELL,
                      quantity=100, price_eur=55.20, trade_date=date(2025, 6, 1))
    # gain = 10, proceeds = 5520, 0.18% → tiny, but NO same-day buy → no warning
    summary = _engine(cfg).calculate([buy, sell])
    assert not any("round-trip" in w.lower() or "suspicious" in w.lower() for w in summary.warnings)


def test_roundtrip_no_warn_below_proceeds_threshold(cfg):
    """Tiny trade below €500 proceeds threshold is not flagged."""
    buy  = make_trade("TST", "US0000000001", TransactionType.BUY,
                      quantity=5, price_eur=50.10, trade_date=date(2025, 6, 1))
    sell = make_trade("TST", "US0000000001", TransactionType.SELL,
                      quantity=5, price_eur=50.00, trade_date=date(2025, 6, 1))
    # proceeds = 250 < 500 → below threshold → no warning
    summary = _engine(cfg).calculate([buy, sell])
    assert not any("round-trip" in w.lower() or "suspicious" in w.lower() for w in summary.warnings)
