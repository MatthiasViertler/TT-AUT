"""
Tests for manual cost basis override (config.manual_cost_basis).

Use case: SOLV (Solventum) — 3M spin-off with no buy record in IB.
Without a manual override the sell is unmatched and cost basis defaults to 0.
With the override the FIFO queue is seeded correctly and gain/loss is accurate.
"""
from datetime import date
from decimal import Decimal

import pytest

from core.models import TransactionType
from core.tax_engine import TaxEngine
from tests.conftest import make_trade

ZERO = Decimal("0")


def _engine(cfg: dict) -> TaxEngine:
    return TaxEngine(cfg, tax_year=2025, person_label="Test")


# ── No buy record → unmatched warning (baseline) ─────────────────────────────

def test_sell_without_buy_raises_warning(cfg):
    """Without manual_cost_basis, selling SOLV triggers an unmatched-sell warning."""
    sell = make_trade("SOLV", "US83444M1018", TransactionType.SELL,
                      quantity=10, price_eur=50.0, trade_date=date(2025, 6, 1))
    summary = _engine(cfg).calculate([sell])
    assert summary.unmatched_sells == 1
    assert any("SOLV" in w for w in summary.warnings)


def test_sell_without_buy_cost_basis_zero(cfg):
    """Unmatched sell defaults cost basis to 0 → gain equals proceeds."""
    sell = make_trade("SOLV", "US83444M1018", TransactionType.SELL,
                      quantity=10, price_eur=50.0, trade_date=date(2025, 6, 1))
    summary = _engine(cfg).calculate([sell])
    assert summary.kz_994 == Decimal("500.00")   # 10 × 50 = 500, basis 0


# ── Manual cost basis seeds the FIFO correctly ────────────────────────────────

def test_manual_cost_basis_no_warning(cfg):
    """With manual_cost_basis set, the sell is fully matched — no unmatched warning."""
    cfg["manual_cost_basis"] = [{
        "symbol": "SOLV",
        "isin": "US83444M1018",
        "purchase_date": "2024-04-01",
        "quantity": 10,
        "cost_eur": 300.00,
    }]
    sell = make_trade("SOLV", "US83444M1018", TransactionType.SELL,
                      quantity=10, price_eur=50.0, trade_date=date(2025, 6, 1))
    summary = _engine(cfg).calculate([sell])
    assert summary.unmatched_sells == 0
    assert not any("SOLV" in w for w in summary.warnings)


def test_manual_cost_basis_correct_gain(cfg):
    """Gain = proceeds − manual cost basis (500 − 300 = 200)."""
    cfg["manual_cost_basis"] = [{
        "symbol": "SOLV",
        "isin": "US83444M1018",
        "purchase_date": "2024-04-01",
        "quantity": 10,
        "cost_eur": 300.00,
    }]
    sell = make_trade("SOLV", "US83444M1018", TransactionType.SELL,
                      quantity=10, price_eur=50.0, trade_date=date(2025, 6, 1))
    summary = _engine(cfg).calculate([sell])
    assert summary.kz_994 == Decimal("200.00")


def test_manual_cost_basis_zero_spin_off(cfg):
    """Spin-off with cost_eur=0: full proceeds = gain (worst case for tax)."""
    cfg["manual_cost_basis"] = [{
        "symbol": "SOLV",
        "isin": "US83444M1018",
        "purchase_date": "2024-04-01",
        "quantity": 10,
        "cost_eur": 0.00,
    }]
    sell = make_trade("SOLV", "US83444M1018", TransactionType.SELL,
                      quantity=10, price_eur=50.0, trade_date=date(2025, 6, 1))
    summary = _engine(cfg).calculate([sell])
    assert summary.kz_994 == Decimal("500.00")
    assert summary.unmatched_sells == 0


def test_manual_cost_basis_partial_sell(cfg):
    """Selling fewer shares than the manual lot leaves remaining shares in queue."""
    cfg["manual_cost_basis"] = [{
        "symbol": "SOLV",
        "isin": "US83444M1018",
        "purchase_date": "2024-04-01",
        "quantity": 10,
        "cost_eur": 300.00,   # 30 EUR/share
    }]
    sell = make_trade("SOLV", "US83444M1018", TransactionType.SELL,
                      quantity=5, price_eur=50.0, trade_date=date(2025, 6, 1))
    summary = _engine(cfg).calculate([sell])
    # proceeds=250, cost=5×30=150 → gain=100
    assert summary.kz_994 == Decimal("100.00")
    assert summary.unmatched_sells == 0


def test_manual_cost_basis_date_object(cfg):
    """purchase_date can be a date object (from YAML parsing), not just a string."""
    cfg["manual_cost_basis"] = [{
        "symbol": "SOLV",
        "isin": "US83444M1018",
        "purchase_date": date(2024, 4, 1),   # date object, not string
        "quantity": 10,
        "cost_eur": 300.00,
    }]
    sell = make_trade("SOLV", "US83444M1018", TransactionType.SELL,
                      quantity=10, price_eur=50.0, trade_date=date(2025, 6, 1))
    summary = _engine(cfg).calculate([sell])
    assert summary.kz_994 == Decimal("200.00")
    assert summary.unmatched_sells == 0


def test_manual_cost_basis_fifo_ordering(cfg):
    """Manual lot (older date) is consumed before a real buy (newer date)."""
    cfg["manual_cost_basis"] = [{
        "symbol": "SOLV",
        "isin": "US83444M1018",
        "purchase_date": "2024-01-01",
        "quantity": 5,
        "cost_eur": 100.00,   # 20 EUR/share
    }]
    real_buy = make_trade("SOLV", "US83444M1018", TransactionType.BUY,
                          quantity=5, price_eur=40.0, trade_date=date(2024, 6, 1))
    sell = make_trade("SOLV", "US83444M1018", TransactionType.SELL,
                      quantity=5, price_eur=50.0, trade_date=date(2025, 6, 1))
    summary = _engine(cfg).calculate([real_buy, sell])
    # FIFO: manual lot (Jan) consumed first → cost = 5×20 = 100, gain = 250−100 = 150
    assert summary.kz_994 == Decimal("150.00")
    assert summary.unmatched_sells == 0
