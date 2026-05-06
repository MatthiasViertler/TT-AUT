"""
Tests for FIFO diagnostic warnings:
- ISIN-based ticker rename hint (unmatched sell + same ISIN under different symbol)
- Same-day round-trip detection (sell + repurchase, tiny gain → possible FIFO mismatch)
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


# ── ISIN rename hint ──────────────────────────────────────────────────────────

def test_isin_rename_hint_fires(cfg):
    """Unmatched sell: if same ISIN exists under a different buy symbol, hint at symbol_aliases."""
    buy  = make_trade("OEWA", "AT0000746409", TransactionType.BUY,
                      quantity=10, price_eur=70.0, trade_date=date(2024, 1, 1))
    sell = make_trade("VER",  "AT0000746409", TransactionType.SELL,
                      quantity=10, price_eur=60.0, trade_date=date(2025, 6, 1))
    summary = _engine(cfg).calculate([buy, sell])
    # "ticker rename" is unique to the ISIN rename hint (negative-position check says "symbol_aliases" too)
    rename_warnings = [w for w in summary.warnings if "ticker rename" in w]
    assert rename_warnings, f"Expected rename hint, got: {summary.warnings}"
    assert "VER" in rename_warnings[0]
    assert "OEWA" in rename_warnings[0]


def test_isin_rename_hint_suggests_correct_alias(cfg):
    """The hint should suggest adding the sell symbol → buy symbol mapping."""
    buy  = make_trade("OEWA", "AT0000746409", TransactionType.BUY,
                      quantity=10, price_eur=70.0, trade_date=date(2024, 1, 1))
    sell = make_trade("VER",  "AT0000746409", TransactionType.SELL,
                      quantity=10, price_eur=60.0, trade_date=date(2025, 6, 1))
    summary = _engine(cfg).calculate([buy, sell])
    w = next(w for w in summary.warnings if "ticker rename" in w)
    assert "VER: OEWA" in w or "VER': 'OEWA" in w


def test_isin_rename_hint_not_fired_when_alias_resolves(cfg):
    """When symbol_aliases maps sell → buy, lots are found → no unmatched/rename warning."""
    cfg["symbol_aliases"] = {"VER": "OEWA"}
    buy  = make_trade("OEWA", "AT0000746409", TransactionType.BUY,
                      quantity=10, price_eur=70.0, trade_date=date(2024, 1, 1))
    sell = make_trade("VER",  "AT0000746409", TransactionType.SELL,
                      quantity=10, price_eur=60.0, trade_date=date(2025, 6, 1))
    summary = _engine(cfg).calculate([buy, sell])
    assert summary.unmatched_sells == 0
    assert not any("ticker rename" in w for w in summary.warnings)


def test_isin_rename_hint_absent_when_no_isin(cfg):
    """Without an ISIN on the sell, no rename hint is added (just the standard unmatched warning)."""
    import dataclasses
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
