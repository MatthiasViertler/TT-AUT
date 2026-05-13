"""
Tests for dynamic portfolio value computation.

Covers:
- TaxEngine.remaining_positions after FIFO processing
- Synthetic flag for SAXO AggregatedAmounts (broker="saxo") and manual_cost_basis lots
- _compute_portfolio_value in pipeline (mocked price + FX)
"""
from datetime import date
from decimal import Decimal
from unittest.mock import patch, MagicMock

import pytest

from core.models import TransactionType, AssetClass, Domicile, NormalizedTransaction, TaxSummary
from core.tax_engine import TaxEngine
from core.pipeline import _compute_portfolio_value, _compute_dividend_yield
from tests.conftest import make_trade

ZERO = Decimal("0")


def _engine(cfg: dict) -> TaxEngine:
    return TaxEngine(cfg, tax_year=2025, person_label="Test")


def make_saxo_trade(
    symbol: str,
    txn_type: TransactionType,
    quantity: float = 1.0,
    price_eur: float = 100.0,
    trade_date: date = date(2024, 3, 1),
) -> NormalizedTransaction:
    """SAXO AggregatedAmounts trade: broker='saxo', qty=1 (synthetic convention)."""
    qty = Decimal(str(quantity))
    price = Decimal(str(price_eur))
    sign = Decimal("-1") if txn_type == TransactionType.BUY else Decimal("1")
    amount = sign * qty * price
    return NormalizedTransaction(
        broker="saxo",      # AggregatedAmounts parser
        raw_id=f"saxo_{symbol}_{trade_date}_{txn_type.value}",
        trade_date=trade_date,
        settle_date=None,
        txn_type=txn_type,
        asset_class=AssetClass.STOCK,
        symbol=symbol,
        isin=f"US{symbol}0000001",
        description=f"{symbol} {txn_type.value}",
        country_code="US",
        domicile=Domicile.FOREIGN,
        quantity=qty if txn_type == TransactionType.BUY else -qty,
        price=price,
        price_currency="EUR",
        orig_currency="EUR",
        orig_amount=amount,
        wht_amount_orig=ZERO,
        fx_rate_to_eur=Decimal("1"),
        eur_amount=amount,
        eur_wht=ZERO,
        source_file="test_saxo",
    )


# ── remaining_positions: basic cases ─────────────────────────────────────────

def test_remaining_positions_buy_only(cfg):
    """Unsold buy → appears in remaining_positions with full qty."""
    buy = make_trade("AAPL", "US0378331005", TransactionType.BUY,
                     quantity=10, price_eur=150.0)
    engine = _engine(cfg)
    engine.calculate([buy])
    assert "AAPL" in engine.remaining_positions
    pos = engine.remaining_positions["AAPL"]
    assert pos["qty"] == Decimal("10")
    assert pos["has_synthetic"] is False


def test_remaining_positions_fully_sold(cfg):
    """Fully sold position → not in remaining_positions."""
    buy = make_trade("AAPL", "US0378331005", TransactionType.BUY,
                     quantity=10, price_eur=150.0, trade_date=date(2024, 1, 1))
    sell = make_trade("AAPL", "US0378331005", TransactionType.SELL,
                      quantity=10, price_eur=180.0, trade_date=date(2025, 6, 1))
    engine = _engine(cfg)
    engine.calculate([buy, sell])
    assert "AAPL" not in engine.remaining_positions


def test_remaining_positions_partial_sell(cfg):
    """Partial sell → remaining qty = bought − sold."""
    buy = make_trade("AAPL", "US0378331005", TransactionType.BUY,
                     quantity=10, price_eur=150.0, trade_date=date(2024, 1, 1))
    sell = make_trade("AAPL", "US0378331005", TransactionType.SELL,
                      quantity=4, price_eur=180.0, trade_date=date(2025, 6, 1))
    engine = _engine(cfg)
    engine.calculate([buy, sell])
    pos = engine.remaining_positions["AAPL"]
    assert pos["qty"] == Decimal("6")
    assert pos["has_synthetic"] is False


def test_remaining_positions_multiple_symbols(cfg):
    """Multiple symbols tracked independently."""
    buy_a = make_trade("AAPL", "US0378331005", TransactionType.BUY, 5, 150.0)
    buy_b = make_trade("MSFT", "US5949181045", TransactionType.BUY, 8, 300.0)
    sell_b = make_trade("MSFT", "US5949181045", TransactionType.SELL,
                        8, 320.0, trade_date=date(2025, 9, 1))
    engine = _engine(cfg)
    engine.calculate([buy_a, buy_b, sell_b])
    assert "AAPL" in engine.remaining_positions
    assert "MSFT" not in engine.remaining_positions


# ── synthetic flag ────────────────────────────────────────────────────────────

def test_remaining_positions_saxo_agg_is_synthetic(cfg):
    """SAXO AggregatedAmounts buys (broker='saxo') are marked synthetic."""
    buy = make_saxo_trade("NVDA", TransactionType.BUY, quantity=1, price_eur=500.0)
    engine = _engine(cfg)
    engine.calculate([buy])
    assert "NVDA" in engine.remaining_positions
    assert engine.remaining_positions["NVDA"]["has_synthetic"] is True


def test_remaining_positions_manual_cost_basis_is_synthetic(cfg):
    """manual_cost_basis lots are always synthetic."""
    cfg["manual_cost_basis"] = [{
        "symbol": "SOLV",
        "isin": "US83444M1018",
        "purchase_date": "2024-04-01",
        "quantity": 1,
        "cost_eur": 50.0,
    }]
    engine = _engine(cfg)
    engine.calculate([])
    assert "SOLV" in engine.remaining_positions
    assert engine.remaining_positions["SOLV"]["has_synthetic"] is True


def test_remaining_positions_ib_not_synthetic(cfg):
    """IB trades (broker='ib') are never synthetic."""
    buy = make_trade("META", "US30303M1027", TransactionType.BUY, 3, 400.0)
    engine = _engine(cfg)
    engine.calculate([buy])
    assert engine.remaining_positions["META"]["has_synthetic"] is False


def test_remaining_positions_mixed_lots_synthetic_wins(cfg):
    """Symbol with both synthetic and real lots → has_synthetic=True."""
    cfg["manual_cost_basis"] = [{
        "symbol": "AAPL",
        "isin": "US0378331005",
        "purchase_date": "2023-01-01",
        "quantity": 1,
        "cost_eur": 130.0,
    }]
    real_buy = make_trade("AAPL", "US0378331005", TransactionType.BUY,
                          5, 150.0, trade_date=date(2024, 6, 1))
    engine = _engine(cfg)
    engine.calculate([real_buy])
    pos = engine.remaining_positions["AAPL"]
    assert pos["qty"] == Decimal("6")   # 1 synthetic + 5 real
    assert pos["has_synthetic"] is True


def test_remaining_positions_synthetic_consumed_real_remains(cfg):
    """Synthetic lot fully consumed by sell → only real lots remain → not synthetic."""
    cfg["manual_cost_basis"] = [{
        "symbol": "AAPL",
        "isin": "US0378331005",
        "purchase_date": "2023-01-01",
        "quantity": 1,
        "cost_eur": 130.0,
    }]
    real_buy = make_trade("AAPL", "US0378331005", TransactionType.BUY,
                          5, 150.0, trade_date=date(2024, 6, 1))
    # Sell 1 unit — FIFO consumes the synthetic manual_cost_basis lot first (older date)
    sell = make_trade("AAPL", "US0378331005", TransactionType.SELL,
                      1, 160.0, trade_date=date(2025, 3, 1))
    engine = _engine(cfg)
    engine.calculate([real_buy, sell])
    pos = engine.remaining_positions["AAPL"]
    assert pos["qty"] == Decimal("5")
    assert pos["has_synthetic"] is False  # synthetic lot fully consumed


# ── symbol_meta ───────────────────────────────────────────────────────────────

def test_symbol_meta_populated_from_buys(cfg):
    """symbol_meta contains currency and ISIN from buy transactions."""
    buy = make_trade("AAPL", "US0378331005", TransactionType.BUY, 10, 150.0)
    engine = _engine(cfg)
    engine.calculate([buy])
    assert "AAPL" in engine.symbol_meta
    assert engine.symbol_meta["AAPL"]["currency"] == "EUR"
    assert engine.symbol_meta["AAPL"]["isin"] == "US0378331005"


# ── _compute_portfolio_value ──────────────────────────────────────────────────

def _make_fx(rate: float):
    fx = MagicMock()
    fx.get_rate.return_value = Decimal(str(rate))
    return fx


def test_compute_portfolio_value_basic():
    """Single non-synthetic position: qty × price × fx = EUR value."""
    remaining = {"AAPL": {"qty": Decimal("10"), "has_synthetic": False}}
    symbol_meta = {"AAPL": {"currency": "USD", "isin": "US0378331005"}}
    fx = _make_fx(0.92)  # 1 USD = 0.92 EUR
    config = {"price_cache_dir": "/tmp/nonexistent"}

    with patch("core.pipeline.get_year_end_price", return_value=Decimal("150.0")):
        total, _ = _compute_portfolio_value(remaining, symbol_meta, fx, 2025, config)

    # 10 × 150 × 0.92 = 1380 EUR
    assert total == Decimal("1380.00")


def test_compute_portfolio_value_skips_synthetic():
    """Synthetic positions are excluded from portfolio value."""
    remaining = {
        "AAPL": {"qty": Decimal("10"), "has_synthetic": False},
        "SAXO_POS": {"qty": Decimal("1"), "has_synthetic": True},
    }
    symbol_meta = {
        "AAPL": {"currency": "USD", "isin": "US0378331005"},
        "SAXO_POS": {"currency": "USD", "isin": "US9999999999"},
    }
    fx = _make_fx(1.0)
    config = {"price_cache_dir": "/tmp/nonexistent"}

    with patch("core.pipeline.get_year_end_price", return_value=Decimal("100.0")):
        total, _ = _compute_portfolio_value(remaining, symbol_meta, fx, 2025, config)

    assert total == Decimal("1000.00")  # only AAPL: 10 × 100 × 1.0


def test_compute_portfolio_value_skips_missing_price():
    """Position with no Dec31 price is skipped (no crash)."""
    remaining = {"AAPL": {"qty": Decimal("10"), "has_synthetic": False}}
    symbol_meta = {"AAPL": {"currency": "USD", "isin": "US0378331005"}}
    fx = _make_fx(1.0)
    config = {"price_cache_dir": "/tmp/nonexistent"}

    with patch("core.pipeline.get_year_end_price", return_value=None):
        total, _ = _compute_portfolio_value(remaining, symbol_meta, fx, 2025, config)

    assert total == ZERO


def test_compute_portfolio_value_skips_missing_fx():
    """Position with no FX rate is skipped gracefully."""
    remaining = {"AAPL": {"qty": Decimal("10"), "has_synthetic": False}}
    symbol_meta = {"AAPL": {"currency": "USD", "isin": "US0378331005"}}
    fx = MagicMock()
    fx.get_rate.return_value = None
    config = {"price_cache_dir": "/tmp/nonexistent"}

    with patch("core.pipeline.get_year_end_price", return_value=Decimal("150.0")):
        total, _ = _compute_portfolio_value(remaining, symbol_meta, fx, 2025, config)

    assert total == ZERO


def test_compute_portfolio_value_multiple_positions():
    """Multiple positions summed correctly."""
    remaining = {
        "AAPL": {"qty": Decimal("10"), "has_synthetic": False},
        "MSFT": {"qty": Decimal("5"),  "has_synthetic": False},
    }
    symbol_meta = {
        "AAPL": {"currency": "USD", "isin": "US0378331005"},
        "MSFT": {"currency": "USD", "isin": "US5949181045"},
    }
    fx = _make_fx(1.0)  # EUR = USD for simplicity
    config = {"price_cache_dir": "/tmp/nonexistent"}

    prices = {"AAPL": Decimal("200.0"), "MSFT": Decimal("300.0")}
    with patch("core.pipeline.get_year_end_price", side_effect=lambda sym, *a, **k: prices[sym]):
        total, _ = _compute_portfolio_value(remaining, symbol_meta, fx, 2025, config)

    # AAPL: 10 × 200 = 2000, MSFT: 5 × 300 = 1500 → 3500
    assert total == Decimal("3500.00")


def test_compute_portfolio_value_empty_positions():
    """No positions → returns 0."""
    config = {"price_cache_dir": "/tmp/nonexistent"}
    total, positions = _compute_portfolio_value({}, {}, MagicMock(), 2025, config)
    assert total == ZERO
    assert positions == []


# ── _compute_dividend_yield ───────────────────────────────────────────────────

def _make_summary(portfolio_eur=None, total_dividends_eur=Decimal("0")):
    s = TaxSummary(tax_year=2025, person_label="Test")
    s.portfolio_eur_computed = portfolio_eur
    s.total_dividends_eur = total_dividends_eur
    return s


def test_dividend_yield_basic():
    """Yield = dividends / portfolio × 100, rounded to 2dp."""
    s = _make_summary(
        portfolio_eur=Decimal("100000"),
        total_dividends_eur=Decimal("3500"),
    )
    assert _compute_dividend_yield(s) == 3.5


def test_dividend_yield_rounding():
    """Result is rounded to 2 decimal places."""
    s = _make_summary(
        portfolio_eur=Decimal("100000"),
        total_dividends_eur=Decimal("3333.33"),
    )
    result = _compute_dividend_yield(s)
    assert result == 3.33


def test_dividend_yield_none_when_no_portfolio():
    """No portfolio computed → yield is None."""
    s = _make_summary(portfolio_eur=None, total_dividends_eur=Decimal("1000"))
    assert _compute_dividend_yield(s) is None


def test_dividend_yield_none_when_portfolio_zero():
    """Zero portfolio → yield is None (avoids division by zero)."""
    s = _make_summary(portfolio_eur=ZERO, total_dividends_eur=Decimal("1000"))
    assert _compute_dividend_yield(s) is None


def test_dividend_yield_none_when_no_dividends():
    """Zero dividends → yield is None."""
    s = _make_summary(portfolio_eur=Decimal("100000"), total_dividends_eur=ZERO)
    assert _compute_dividend_yield(s) is None
