"""
Tests for per-symbol portfolio holdings table.

Covers:
1. _compute_symbol_dividends — sums correctly, filters by year, DIVIDEND type only
2. _build_symbol_info — resolves name/type from nmf config and mf_results; ETF suffix
3. Sort order: value, yield, alpha — verify order with mixed positions
4. Synthetic positions appear after non-synthetic regardless of sort
5. Sold positions (dividend but no remaining lot) appear at the very end
6. portfolio_pct sums to ~100% for non-synthetic non-sold positions
7. yield_pct is None for zero-value positions, correct for valued positions
"""
from datetime import date
from decimal import Decimal
from unittest.mock import patch, MagicMock

import pytest

from core.models import (
    NormalizedTransaction, TransactionType, AssetClass, Domicile,
    MeldefondsResult, PortfolioPosition, TaxSummary,
)
from core.pipeline import (
    _compute_symbol_dividends,
    _build_symbol_info,
    _compute_portfolio_value,
)
from tests.conftest import make_dividend, make_trade

ZERO = Decimal("0")


# ── _compute_symbol_dividends ─────────────────────────────────────────────────

def test_symbol_divs_sums_correctly():
    """Multiple dividends for same symbol sum correctly."""
    txns = [
        make_dividend("AAPL", "US0378331005", gross_eur=100.0, wht_eur=15.0,
                      trade_date=date(2025, 3, 1)),
        make_dividend("AAPL", "US0378331005", gross_eur=120.0, wht_eur=18.0,
                      trade_date=date(2025, 6, 1)),
    ]
    result = _compute_symbol_dividends(txns, 2025)
    assert "AAPL" in result
    assert result["AAPL"] == Decimal("220.0")


def test_symbol_divs_multiple_symbols():
    """Different symbols are tracked independently."""
    txns = [
        make_dividend("AAPL", "US0378331005", gross_eur=100.0, wht_eur=15.0,
                      trade_date=date(2025, 3, 1)),
        make_dividend("MSFT", "US5949181045", gross_eur=50.0, wht_eur=7.5,
                      trade_date=date(2025, 5, 1)),
    ]
    result = _compute_symbol_dividends(txns, 2025)
    assert result["AAPL"] == Decimal("100.0")
    assert result["MSFT"] == Decimal("50.0")


def test_symbol_divs_filters_by_year():
    """Dividends from other years are excluded."""
    txns = [
        make_dividend("AAPL", "US0378331005", gross_eur=100.0, wht_eur=15.0,
                      trade_date=date(2025, 3, 1)),
        make_dividend("AAPL", "US0378331005", gross_eur=200.0, wht_eur=30.0,
                      trade_date=date(2024, 12, 31)),  # prior year
    ]
    result = _compute_symbol_dividends(txns, 2025)
    assert result["AAPL"] == Decimal("100.0")


def test_symbol_divs_only_dividend_type():
    """Non-DIVIDEND transactions are ignored."""
    buy = make_trade("AAPL", "US0378331005", TransactionType.BUY, 10, 150.0,
                     trade_date=date(2025, 3, 1))
    div = make_dividend("AAPL", "US0378331005", gross_eur=100.0, wht_eur=15.0,
                        trade_date=date(2025, 6, 1))
    result = _compute_symbol_dividends([buy, div], 2025)
    assert result["AAPL"] == Decimal("100.0")


def test_symbol_divs_empty_transactions():
    """No transactions → empty dict."""
    result = _compute_symbol_dividends([], 2025)
    assert result == {}


# ── _build_symbol_info ────────────────────────────────────────────────────────

def test_build_symbol_info_from_nmf_config():
    """Nichtmeldefonds entries resolved from config."""
    config = {
        "nichtmeldefonds": [
            {"symbol": "O", "name": "Realty Income Corp", "type": "REIT", "currency": "USD"},
            {"symbol": "ARCC", "name": "Ares Capital Corp", "type": "BDC", "currency": "USD"},
        ]
    }
    info = _build_symbol_info(config, [], [])
    assert info["O"]["name"] == "Realty Income Corp"
    assert info["O"]["type"] == "REIT"
    assert info["O"]["currency"] == "USD"
    assert info["ARCC"]["type"] == "BDC"


def test_build_symbol_info_from_meldefonds_acc():
    """Accumulating ETF gets '(acc)' suffix."""
    mf = MeldefondsResult(
        isin="IE00BK5BQT80",
        symbol="VWCE",
        name="Vanguard FTSE All-World",
        fund_type="ETF",
        currency="USD",
        ertragsverwendung="thesaurierend",
        kz="937",
        shares_held=Decimal("10"),
        ae_per_share=Decimal("1.5"),
        wa_per_share=Decimal("0"),
        fx_rate=Decimal("1"),
    )
    info = _build_symbol_info({}, [mf], [])
    assert info["VWCE"]["name"] == "Vanguard FTSE All-World (acc)"
    assert info["VWCE"]["type"] == "ETF"


def test_build_symbol_info_from_meldefonds_dist():
    """Distributing ETF gets '(dist)' suffix."""
    mf = MeldefondsResult(
        isin="IE00B3RBWM25",
        symbol="VWRL",
        name="Vanguard FTSE All-World ETF",
        fund_type="ETF",
        currency="USD",
        ertragsverwendung="ausschüttend",
        kz="937",
        shares_held=Decimal("5"),
        ae_per_share=Decimal("0"),
        wa_per_share=Decimal("0"),
        fx_rate=Decimal("1"),
    )
    info = _build_symbol_info({}, [mf], [])
    assert info["VWRL"]["name"] == "Vanguard FTSE All-World ETF (dist)"


def test_build_symbol_info_non_etf_no_suffix():
    """Non-ETF Meldefonds fund does not get acc/dist suffix."""
    mf = MeldefondsResult(
        isin="AT0000123456",
        symbol="ATFUND",
        name="Austrian Fund",
        fund_type="FUND",
        currency="EUR",
        ertragsverwendung="thesaurierend",
        kz="936",
        shares_held=Decimal("10"),
        ae_per_share=Decimal("1"),
        wa_per_share=Decimal("0"),
        fx_rate=Decimal("1"),
    )
    info = _build_symbol_info({}, [mf], [])
    assert info["ATFUND"]["name"] == "Austrian Fund"


def test_build_symbol_info_unknown_symbol():
    """Symbols not in config or mf_results are not present (caller uses defaults)."""
    info = _build_symbol_info({}, [], [])
    assert "AAPL" not in info


# ── _compute_portfolio_value: sort order ─────────────────────────────────────

def _make_fx(rate: float = 1.0):
    fx = MagicMock()
    fx.get_rate.return_value = Decimal(str(rate))
    return fx


def _make_remaining(symbols_and_vals: list[tuple[str, float]]) -> tuple[dict, dict]:
    """Build (remaining_positions, symbol_meta) from list of (symbol, eur_value) tuples."""
    remaining = {}
    symbol_meta = {}
    for sym, val in symbols_and_vals:
        remaining[sym] = {"qty": Decimal(str(val)), "has_synthetic": False}
        symbol_meta[sym] = {"currency": "USD"}
    return remaining, symbol_meta


def test_sort_by_value_default():
    """Default sort=value: positions sorted by EUR value descending."""
    remaining = {
        "LOW": {"qty": Decimal("1"), "has_synthetic": False},
        "HIGH": {"qty": Decimal("10"), "has_synthetic": False},
        "MID": {"qty": Decimal("5"), "has_synthetic": False},
    }
    symbol_meta = {
        "LOW": {"currency": "USD"},
        "HIGH": {"currency": "USD"},
        "MID": {"currency": "USD"},
    }
    prices = {"LOW": Decimal("10"), "HIGH": Decimal("100"), "MID": Decimal("50")}
    config = {"price_cache_dir": "/tmp/nonexistent"}

    with patch("core.pipeline.get_year_end_price", side_effect=lambda sym, *a, **k: prices[sym]):
        total, positions = _compute_portfolio_value(remaining, symbol_meta, _make_fx(), 2025, config)

    syms = [p.symbol for p in positions]
    # HIGH=1000 > MID=250 > LOW=10
    assert syms == ["HIGH", "MID", "LOW"]


def test_sort_by_alpha():
    """holdings_sort=alpha: sorted alphabetically."""
    remaining = {
        "ZEBRA": {"qty": Decimal("5"), "has_synthetic": False},
        "ALPHA": {"qty": Decimal("3"), "has_synthetic": False},
        "MIKE": {"qty": Decimal("4"), "has_synthetic": False},
    }
    symbol_meta = {
        "ZEBRA": {"currency": "USD"},
        "ALPHA": {"currency": "USD"},
        "MIKE": {"currency": "USD"},
    }
    config = {"price_cache_dir": "/tmp/nonexistent", "freedom_dashboard": {"holdings_sort": "alpha"}}

    with patch("core.pipeline.get_year_end_price", return_value=Decimal("100")):
        total, positions = _compute_portfolio_value(remaining, symbol_meta, _make_fx(), 2025, config)

    syms = [p.symbol for p in positions]
    assert syms == ["ALPHA", "MIKE", "ZEBRA"]


def test_sort_by_yield():
    """holdings_sort=yield: sorted by yield% descending."""
    remaining = {
        "LOW_YIELD": {"qty": Decimal("10"), "has_synthetic": False},
        "HIGH_YIELD": {"qty": Decimal("10"), "has_synthetic": False},
    }
    symbol_meta = {
        "LOW_YIELD": {"currency": "USD"},
        "HIGH_YIELD": {"currency": "USD"},
    }
    # Both have same price (100), so eur_value = 1000 each
    # Div: LOW=20, HIGH=100 → yields 2% and 10%
    divs = {"LOW_YIELD": Decimal("20"), "HIGH_YIELD": Decimal("100")}
    config = {"price_cache_dir": "/tmp/nonexistent", "freedom_dashboard": {"holdings_sort": "yield"}}

    with patch("core.pipeline.get_year_end_price", return_value=Decimal("100")):
        total, positions = _compute_portfolio_value(
            remaining, symbol_meta, _make_fx(), 2025, config, symbol_divs=divs
        )

    syms = [p.symbol for p in positions]
    assert syms == ["HIGH_YIELD", "LOW_YIELD"]


# ── Synthetic positions always after non-synthetic ────────────────────────────

def test_synthetic_always_last_regardless_of_sort():
    """Synthetic positions come after all non-synthetic, regardless of sort key."""
    remaining = {
        "REAL": {"qty": Decimal("5"), "has_synthetic": False},
        "SYNTH": {"qty": Decimal("1"), "has_synthetic": True},
    }
    symbol_meta = {
        "REAL": {"currency": "USD"},
        "SYNTH": {"currency": "USD"},
    }
    config = {"price_cache_dir": "/tmp/nonexistent"}

    with patch("core.pipeline.get_year_end_price", return_value=Decimal("100")):
        total, positions = _compute_portfolio_value(remaining, symbol_meta, _make_fx(), 2025, config)

    assert positions[0].symbol == "REAL"
    assert positions[1].symbol == "SYNTH"
    assert positions[1].is_synthetic is True


# ── Sold positions at the very end ────────────────────────────────────────────

def test_sold_positions_appear_at_end():
    """Symbols with dividends but no remaining lot appear as fund_type=Sold at end."""
    remaining = {
        "HELD": {"qty": Decimal("10"), "has_synthetic": False},
    }
    symbol_meta = {"HELD": {"currency": "USD"}}
    divs = {
        "HELD": Decimal("50"),
        "SOLD_SYM": Decimal("30"),  # dividend but no remaining lot
    }
    config = {"price_cache_dir": "/tmp/nonexistent"}

    with patch("core.pipeline.get_year_end_price", return_value=Decimal("100")):
        total, positions = _compute_portfolio_value(
            remaining, symbol_meta, _make_fx(), 2025, config, symbol_divs=divs
        )

    assert len(positions) == 2
    assert positions[0].symbol == "HELD"
    assert positions[1].symbol == "SOLD_SYM"
    assert positions[1].fund_type == "Sold"
    assert positions[1].eur_value == ZERO
    assert positions[1].dividends_eur == Decimal("30")


def test_sold_positions_after_synthetic():
    """Sold positions appear after synthetic positions (category order: real < synth < sold)."""
    remaining = {
        "SYNTH": {"qty": Decimal("1"), "has_synthetic": True},
        "REAL":  {"qty": Decimal("5"), "has_synthetic": False},
    }
    symbol_meta = {
        "SYNTH": {"currency": "USD"},
        "REAL":  {"currency": "USD"},
    }
    divs = {
        "SOLD_SYM": Decimal("25"),
    }
    config = {"price_cache_dir": "/tmp/nonexistent"}

    with patch("core.pipeline.get_year_end_price", return_value=Decimal("100")):
        total, positions = _compute_portfolio_value(
            remaining, symbol_meta, _make_fx(), 2025, config, symbol_divs=divs
        )

    types = [p.fund_type for p in positions]
    fund_types_no_sold = [t for t in types if t != "Sold"]
    sold_types = [t for t in types if t == "Sold"]
    # All sold appear after all non-sold
    last_non_sold_idx = max(i for i, t in enumerate(types) if t != "Sold")
    first_sold_idx = min(i for i, t in enumerate(types) if t == "Sold")
    assert first_sold_idx > last_non_sold_idx


# ── portfolio_pct ─────────────────────────────────────────────────────────────

def test_portfolio_pct_sums_to_100():
    """portfolio_pct for non-synthetic, non-sold positions sums to ~100%."""
    remaining = {
        "AAPL": {"qty": Decimal("10"), "has_synthetic": False},
        "MSFT": {"qty": Decimal("5"),  "has_synthetic": False},
    }
    symbol_meta = {
        "AAPL": {"currency": "USD"},
        "MSFT": {"currency": "USD"},
    }
    prices = {"AAPL": Decimal("200"), "MSFT": Decimal("200")}
    config = {"price_cache_dir": "/tmp/nonexistent"}

    with patch("core.pipeline.get_year_end_price", side_effect=lambda sym, *a, **k: prices[sym]):
        total, positions = _compute_portfolio_value(remaining, symbol_meta, _make_fx(), 2025, config)

    valued = [p for p in positions if p.portfolio_pct is not None]
    total_pct = sum(p.portfolio_pct for p in valued)
    assert abs(total_pct - 100.0) < 0.1


def test_portfolio_pct_none_for_synthetic():
    """Synthetic positions have portfolio_pct=None."""
    remaining = {"SYNTH": {"qty": Decimal("1"), "has_synthetic": True}}
    symbol_meta = {"SYNTH": {"currency": "USD"}}
    config = {"price_cache_dir": "/tmp/nonexistent"}

    with patch("core.pipeline.get_year_end_price", return_value=Decimal("100")):
        total, positions = _compute_portfolio_value(remaining, symbol_meta, _make_fx(), 2025, config)

    assert positions[0].portfolio_pct is None


def test_portfolio_pct_none_for_sold():
    """Sold positions have portfolio_pct=None."""
    divs = {"SOLD": Decimal("50")}
    config = {"price_cache_dir": "/tmp/nonexistent"}

    with patch("core.pipeline.get_year_end_price", return_value=Decimal("100")):
        total, positions = _compute_portfolio_value({}, {}, _make_fx(), 2025, config, symbol_divs=divs)

    assert positions[0].fund_type == "Sold"
    assert positions[0].portfolio_pct is None


# ── yield_pct ─────────────────────────────────────────────────────────────────

def test_yield_pct_none_for_zero_value():
    """yield_pct is None when eur_value is zero (e.g. synthetic or price missing)."""
    remaining = {"AAPL": {"qty": Decimal("10"), "has_synthetic": False}}
    symbol_meta = {"AAPL": {"currency": "USD"}}
    divs = {"AAPL": Decimal("100")}
    config = {"price_cache_dir": "/tmp/nonexistent"}

    # Price missing → eur_value = 0
    with patch("core.pipeline.get_year_end_price", return_value=None):
        total, positions = _compute_portfolio_value(
            remaining, symbol_meta, _make_fx(), 2025, config, symbol_divs=divs
        )

    assert positions[0].yield_pct is None


def test_yield_pct_correct_for_valued_position():
    """yield_pct = dividends / eur_value × 100, rounded to 2dp."""
    remaining = {"AAPL": {"qty": Decimal("10"), "has_synthetic": False}}
    symbol_meta = {"AAPL": {"currency": "USD"}}
    # Price=100, FX=1.0 → eur_value = 1000
    # Dividends = 50 → yield = 5.0%
    divs = {"AAPL": Decimal("50")}
    config = {"price_cache_dir": "/tmp/nonexistent"}

    with patch("core.pipeline.get_year_end_price", return_value=Decimal("100")):
        total, positions = _compute_portfolio_value(
            remaining, symbol_meta, _make_fx(1.0), 2025, config, symbol_divs=divs
        )

    assert positions[0].yield_pct == pytest.approx(5.0, rel=0.01)


def test_yield_pct_none_for_no_dividends():
    """yield_pct is None when dividends_eur is zero."""
    remaining = {"AAPL": {"qty": Decimal("10"), "has_synthetic": False}}
    symbol_meta = {"AAPL": {"currency": "USD"}}
    config = {"price_cache_dir": "/tmp/nonexistent"}

    with patch("core.pipeline.get_year_end_price", return_value=Decimal("100")):
        total, positions = _compute_portfolio_value(
            remaining, symbol_meta, _make_fx(1.0), 2025, config
        )

    assert positions[0].yield_pct is None


# ── return total stays Decimal ────────────────────────────────────────────────

def test_compute_portfolio_value_returns_tuple():
    """_compute_portfolio_value returns (Decimal, list) tuple."""
    config = {"price_cache_dir": "/tmp/nonexistent"}
    result = _compute_portfolio_value({}, {}, MagicMock(), 2025, config)
    assert isinstance(result, tuple)
    assert len(result) == 2
    total, positions = result
    assert isinstance(total, Decimal)
    assert isinstance(positions, list)


def test_compute_portfolio_value_total_correct():
    """Total returned matches sum of non-synthetic EUR values."""
    remaining = {
        "AAPL": {"qty": Decimal("10"), "has_synthetic": False},
        "SYNTH": {"qty": Decimal("1"), "has_synthetic": True},
    }
    symbol_meta = {
        "AAPL": {"currency": "USD"},
        "SYNTH": {"currency": "USD"},
    }
    config = {"price_cache_dir": "/tmp/nonexistent"}

    with patch("core.pipeline.get_year_end_price", return_value=Decimal("100")):
        total, positions = _compute_portfolio_value(remaining, symbol_meta, _make_fx(1.0), 2025, config)

    # AAPL: 10 × 100 × 1 = 1000; SYNTH: skipped (synthetic, eur_value=0)
    assert total == Decimal("1000.00")
    aapl = next(p for p in positions if p.symbol == "AAPL")
    assert aapl.eur_value == Decimal("1000.00")
    synth = next(p for p in positions if p.symbol == "SYNTH")
    assert synth.eur_value == ZERO


# ── PortfolioPosition dataclass ───────────────────────────────────────────────

def test_portfolio_position_dataclass():
    """PortfolioPosition dataclass has expected fields."""
    from core.models import PortfolioPosition
    pos = PortfolioPosition(
        symbol="TEST",
        name="Test Corp",
        fund_type="Stock",
        currency="USD",
        qty=Decimal("10"),
        is_synthetic=False,
        eur_value=Decimal("1000"),
        dividends_eur=Decimal("50"),
        yield_pct=5.0,
        portfolio_pct=25.0,
    )
    assert pos.symbol == "TEST"
    assert pos.fund_type == "Stock"
    assert pos.yield_pct == 5.0
    assert pos.portfolio_pct == 25.0


# ── TaxSummary.portfolio_positions field ─────────────────────────────────────

def test_tax_summary_has_portfolio_positions_field():
    """TaxSummary has portfolio_positions field that defaults to empty list."""
    s = TaxSummary(tax_year=2025, person_label="Test")
    assert hasattr(s, "portfolio_positions")
    assert s.portfolio_positions == []
