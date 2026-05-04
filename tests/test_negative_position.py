"""
Tests for negative position check (sell > bought for a symbol).
"""
from datetime import date
from decimal import Decimal

import pytest

from core.models import TransactionType
from core.tax_engine import TaxEngine
from tests.conftest import make_trade


def _engine(cfg):
    return TaxEngine(cfg, tax_year=2025, person_label="Test")


def test_balanced_position_no_warning(cfg):
    """Buy 10, sell 10 — no negative position warning."""
    buy  = make_trade("ALV", "DE0008404005", TransactionType.BUY,
                      quantity=10, price_eur=30.0, trade_date=date(2024, 1, 1))
    sell = make_trade("ALV", "DE0008404005", TransactionType.SELL,
                      quantity=10, price_eur=50.0, trade_date=date(2025, 6, 1))
    summary = _engine(cfg).calculate([buy, sell])
    assert not any("negative position" in w.lower() for w in summary.warnings)


def test_partial_sell_no_warning(cfg):
    """Buy 10, sell 5 — still positive, no warning."""
    buy  = make_trade("ALV", "DE0008404005", TransactionType.BUY,
                      quantity=10, price_eur=30.0, trade_date=date(2024, 1, 1))
    sell = make_trade("ALV", "DE0008404005", TransactionType.SELL,
                      quantity=5, price_eur=50.0, trade_date=date(2025, 6, 1))
    summary = _engine(cfg).calculate([buy, sell])
    assert not any("negative position" in w.lower() for w in summary.warnings)


def test_oversell_warns(cfg):
    """Buy 5, sell 10 — net = -5, warning expected."""
    buy  = make_trade("ALV", "DE0008404005", TransactionType.BUY,
                      quantity=5, price_eur=30.0, trade_date=date(2024, 1, 1))
    sell = make_trade("ALV", "DE0008404005", TransactionType.SELL,
                      quantity=10, price_eur=50.0, trade_date=date(2025, 6, 1))
    summary = _engine(cfg).calculate([buy, sell])
    assert any("negative position" in w.lower() for w in summary.warnings)
    assert any("ALV" in w for w in summary.warnings)


def test_no_buy_sell_warns(cfg):
    """Sell with no buy record at all — negative position warning."""
    sell = make_trade("SOLV", "US83444M1018", TransactionType.SELL,
                      quantity=10, price_eur=50.0, trade_date=date(2025, 6, 1))
    summary = _engine(cfg).calculate([sell])
    assert any("negative position" in w.lower() for w in summary.warnings)
    assert any("SOLV" in w for w in summary.warnings)


def test_symbol_alias_respected(cfg):
    """Sell under alias (e.g. 1CO for 1COV) resolves to buy symbol — no false warning."""
    cfg["symbol_aliases"] = {"1CO": "1COV"}
    buy  = make_trade("1COV", "DE000A2BVUK1", TransactionType.BUY,
                      quantity=10, price_eur=50.0, trade_date=date(2024, 1, 1))
    sell = make_trade("1CO",  "DE000A40KY26", TransactionType.SELL,
                      quantity=10, price_eur=60.0, trade_date=date(2025, 6, 1))
    summary = _engine(cfg).calculate([buy, sell])
    assert not any("negative position" in w.lower() for w in summary.warnings)


