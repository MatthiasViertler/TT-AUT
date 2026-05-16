"""Tests for generators/tax_efficiency.py — AT tax efficiency report."""
import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest

from generators.tax_efficiency import (
    compute_dividend_frequency,
    compute_nmf_embedded_pnl,
    write_tax_efficiency_report,
    _get_cost_eur,
    _get_purchase_year,
    _calc_embedded_pnl,
)
from core.models import (
    NormalizedTransaction, NichtmeldefondsResult,
    TransactionType, AssetClass, Domicile,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

class _FX:
    """Stub FX provider: 1 USD = 0.96 EUR."""
    def get_rate(self, currency, date):
        return Decimal("0.96")


def _div(symbol, year, month):
    return NormalizedTransaction(
        raw_id=f"div_{symbol}_{year}_{month}",
        broker="test",
        trade_date=datetime.date(year, month, 15),
        settle_date=None,
        txn_type=TransactionType.DIVIDEND,
        asset_class=AssetClass.STOCK,
        symbol=symbol,
        isin=None,
        description="",
        country_code="US",
        domicile=Domicile.FOREIGN,
        quantity=None,
        price=None,
        price_currency=None,
        orig_currency="USD",
        orig_amount=Decimal("10"),
        wht_amount_orig=Decimal("1.5"),
        fx_rate_to_eur=Decimal("0.96"),
        eur_amount=Decimal("9.6"),
        eur_wht=Decimal("1.44"),
        eur_commission=Decimal("0"),
        source_file="test",
    )


def _buy(symbol, year, cost_eur=500):
    return NormalizedTransaction(
        raw_id=f"buy_{symbol}_{year}",
        broker="test",
        trade_date=datetime.date(year, 3, 1),
        settle_date=None,
        txn_type=TransactionType.BUY,
        asset_class=AssetClass.STOCK,
        symbol=symbol,
        isin=None,
        description="",
        country_code="US",
        domicile=Domicile.FOREIGN,
        quantity=Decimal("100"),
        price=Decimal(str(cost_eur / 100)),
        price_currency="USD",
        orig_currency="USD",
        orig_amount=-Decimal(str(cost_eur)),
        wht_amount_orig=Decimal("0"),
        fx_rate_to_eur=Decimal("1"),
        eur_amount=-Decimal(str(cost_eur)),
        eur_wht=Decimal("0"),
        eur_commission=Decimal("0"),
        source_file="test",
    )


def _nmf_result(symbol, shares, price_dec31, price_jan1=None, fx=Decimal("0.96")):
    """Build a NichtmeldefondsResult with plausible AE figures."""
    p31 = Decimal(str(price_dec31))
    p1 = Decimal(str(price_jan1)) if price_jan1 else Decimal("0")
    gain = max(Decimal("0"), p31 - p1)
    ae90 = (gain * Decimal("0.9")).quantize(Decimal("0.01"))
    ae10 = (p31 * Decimal("0.1")).quantize(Decimal("0.01"))
    ae_ps = max(ae90, ae10)
    s = Decimal(str(shares))
    ae_nat = (ae_ps * s).quantize(Decimal("0.01"))
    ae_eur = (ae_nat * fx).quantize(Decimal("0.01"))
    kest = (ae_eur * Decimal("0.275")).quantize(Decimal("0.01"))
    return NichtmeldefondsResult(
        symbol=symbol,
        isin="US_FAKE",
        name=f"{symbol} Inc",
        fund_type="REIT",
        currency="USD",
        shares_held=s,
        price_jan1=p1 if p1 > 0 else None,
        price_dec31=p31,
        fx_dec31=fx,
        annual_gain_per_share=gain,
        ae_90pct_per_share=ae90,
        ae_10pct_per_share=ae10,
        ae_per_share=ae_ps,
        ae_total_native=ae_nat,
        ae_total_eur=ae_eur,
        kest_due_eur=kest,
        cost_basis_adj_eur=ae_eur,
    )


# ── dividend frequency ────────────────────────────────────────────────────────

def test_monthly_payer():
    txns = [_div("O", 2024, m) for m in range(1, 13)]  # 12 months
    freq = compute_dividend_frequency(txns)
    assert freq["O"]["category"] == "monthly"
    assert freq["O"]["avg_payments_per_year"] == 12.0


def test_quarterly_payer():
    txns = [_div("BAYN", 2024, m) for m in [3, 6, 9, 12]] + \
           [_div("BAYN", 2023, m) for m in [3, 6, 9, 12]]
    freq = compute_dividend_frequency(txns)
    assert freq["BAYN"]["category"] == "quarterly"
    assert freq["BAYN"]["avg_payments_per_year"] == 4.0
    assert freq["BAYN"]["years_observed"] == 2


def test_annual_payer():
    txns = [_div("OMV", 2024, 5)]
    freq = compute_dividend_frequency(txns)
    assert freq["OMV"]["category"] == "annual"
    assert freq["OMV"]["avg_payments_per_year"] == 1.0


def test_frequency_deduplicates_same_month():
    # Two dividends in the same month (e.g. payment + WHT correction) → counts as one
    t1 = _div("O", 2024, 1)
    t2 = _div("O", 2024, 1)
    t2 = NormalizedTransaction(**{**t2.__dict__, "raw_id": "div_O_2024_1_b"})
    freq = compute_dividend_frequency([t1, t2])
    assert freq["O"]["avg_payments_per_year"] == 1.0  # same month counted once


def test_frequency_empty_transactions():
    assert compute_dividend_frequency([]) == {}


# ── cost and purchase year helpers ────────────────────────────────────────────

def test_get_cost_from_manual_cost_basis():
    config = {
        "manual_cost_basis": [
            {"symbol": "O", "cost_eur": "3000", "purchase_date": "2023-01-01", "quantity": 1},
            {"symbol": "O", "cost_eur": "1500", "purchase_date": "2023-06-01", "quantity": 1},
            {"symbol": "EPR", "cost_eur": "2000", "purchase_date": "2023-01-01", "quantity": 1},
        ]
    }
    assert _get_cost_eur("O", config, []) == Decimal("4500.00")
    assert _get_cost_eur("EPR", config, []) == Decimal("2000.00")


def test_get_cost_fallback_to_buy_transactions():
    txns = [_buy("O", 2023, cost_eur=4000)]
    assert _get_cost_eur("O", {}, txns) == Decimal("4000.00")


def test_get_purchase_year_from_manual_cost_basis():
    config = {
        "manual_cost_basis": [
            {"symbol": "O", "cost_eur": "3000", "purchase_date": "2022-11-01", "quantity": 1},
            {"symbol": "O", "cost_eur": "1500", "purchase_date": "2023-06-01", "quantity": 1},
        ]
    }
    assert _get_purchase_year("O", config, [], 2025) == 2022


def test_get_purchase_year_fallback_to_buy_txns():
    txns = [_buy("EPR", 2021), _buy("EPR", 2023)]
    assert _get_purchase_year("EPR", {}, txns, 2025) == 2021


# ── embedded P&L calculation ──────────────────────────────────────────────────

@patch("generators.tax_efficiency._calc_position")
def test_embedded_pnl_underwater(mock_calc):
    """Position where adjusted cost > current value → embedded loss → KeSt credit."""
    # AE of 50 EUR per year for 2 years = 100 EUR cumulative
    ae_result = NichtmeldefondsResult(
        symbol="O", isin="X", name="O Inc", fund_type="REIT", currency="USD",
        shares_held=Decimal("100"),
        price_jan1=Decimal("40"), price_dec31=Decimal("45"), fx_dec31=Decimal("0.96"),
        ae_total_eur=Decimal("50"),
        ae_per_share=Decimal("5"), ae_total_native=Decimal("500"),
        kest_due_eur=Decimal("13.75"), cost_basis_adj_eur=Decimal("50"),
    )
    mock_calc.return_value = ae_result

    config = {
        "nichtmeldefonds": [{"symbol": "O", "isin": "X", "name": "O Inc",
                             "type": "REIT", "currency": "USD",
                             "shares_held_override": {2024: 100}}],
        "manual_cost_basis": [
            {"symbol": "O", "cost_eur": "6000", "purchase_date": "2023-01-01", "quantity": 1},
        ],
        "price_cache_dir": "/tmp",
    }
    # Current result (2024): price_dec31=45 USD, 100 shares, FX=0.96 → EUR 4320
    nmf_result = _nmf_result("O", shares=100, price_dec31=45, price_jan1=40)

    result = _calc_embedded_pnl("O", config, 2024, [], _FX(), "/tmp", nmf_result)
    assert result is not None
    cost, cum_ae, adj_cost, curr_val, pnl, credit = result

    assert cost == Decimal("6000.00")
    # mock_calc called for 2023 and 2024 (purchase year 2023 to tax_year 2024)
    assert cum_ae == Decimal("100.00")  # 50 EUR × 2 years
    assert adj_cost == Decimal("6100.00")
    # current_val = 100 × 45 × 0.96 = 4320
    assert curr_val == Decimal("4320.00")
    assert pnl == Decimal("-1780.00")   # 4320 - 6100
    assert credit == (Decimal("1780") * Decimal("0.275")).quantize(Decimal("0.01"))


@patch("generators.tax_efficiency._calc_position")
def test_embedded_pnl_above_water(mock_calc):
    """Position where current value > adjusted cost → no credit."""
    ae_result = NichtmeldefondsResult(
        symbol="OHI", isin="X", name="OHI Inc", fund_type="REIT", currency="USD",
        shares_held=Decimal("150"),
        price_jan1=Decimal("25"), price_dec31=Decimal("43"), fx_dec31=Decimal("0.96"),
        ae_total_eur=Decimal("150"),
        ae_per_share=Decimal("10"), ae_total_native=Decimal("1500"),
        kest_due_eur=Decimal("41.25"), cost_basis_adj_eur=Decimal("150"),
    )
    mock_calc.return_value = ae_result

    config = {
        "nichtmeldefonds": [{"symbol": "OHI", "isin": "X", "name": "OHI Inc",
                             "type": "REIT", "currency": "USD",
                             "shares_held_override": {2024: 150}}],
        "manual_cost_basis": [
            {"symbol": "OHI", "cost_eur": "3200", "purchase_date": "2023-01-01", "quantity": 1},
        ],
        "price_cache_dir": "/tmp",
    }
    nmf_result = _nmf_result("OHI", shares=150, price_dec31=43, price_jan1=25)

    result = _calc_embedded_pnl("OHI", config, 2024, [], _FX(), "/tmp", nmf_result)
    assert result is not None
    _, _, _, curr_val, pnl, credit = result
    # curr_val = 150 × 43 × 0.96 = 6192
    assert curr_val == Decimal("6192.00")
    assert pnl > Decimal("0")   # above water
    assert credit == Decimal("0")


def test_embedded_pnl_no_cost_basis():
    """Returns None when no cost basis available."""
    nmf_result = _nmf_result("O", shares=100, price_dec31=45)
    config = {"nichtmeldefonds": [{"symbol": "O", "currency": "USD"}],
              "price_cache_dir": "/tmp"}
    result = _calc_embedded_pnl("O", config, 2024, [], _FX(), "/tmp", nmf_result)
    assert result is None


# ── write_tax_efficiency_report smoke test ─────────────────────────────────────

@patch("generators.tax_efficiency._calc_position")
def test_write_tax_efficiency_report_creates_file(mock_calc, tmp_path):
    mock_calc.return_value = None   # no prior-year results → cumulative AE = 0

    nmf_result = _nmf_result("O", shares=100, price_dec31=45, price_jan1=40)
    config = {
        "nichtmeldefonds": [{"symbol": "O", "isin": "X", "name": "O Inc",
                             "type": "REIT", "currency": "USD",
                             "shares_held_override": {2024: 100}}],
        "manual_cost_basis": [
            {"symbol": "O", "cost_eur": "5000", "purchase_date": "2023-01-01", "quantity": 1},
        ],
        "price_cache_dir": str(tmp_path),
    }
    out_path = tmp_path / "test_tax_efficiency.txt"
    write_tax_efficiency_report(
        config=config,
        tax_year=2024,
        all_transactions=[_div("O", 2024, m) for m in [1, 4, 7, 10]],
        nmf_results=[nmf_result],
        portfolio_positions=[],
        fx=_FX(),
        output_path=out_path,
    )
    assert out_path.exists()
    content = out_path.read_text()
    assert "AT TAX EFFICIENCY REPORT" in content
    assert "NICHTMELDEFONDS" in content
    assert "DIVIDEND PAYMENT FREQUENCY" in content
    assert "quarterly" in content.lower()
    assert "SUMMARY" in content
