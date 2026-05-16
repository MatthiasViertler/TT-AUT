"""Tests for NMF AE cost-basis step-up — FIFO gain reduction at sell time.

Covers:
  - compute_nmf_cumulative_ae() accumulates prior-year AE correctly
  - TaxEngine applies step-up to FIFO lot cost_per_unit
  - taxable gain is reduced (or loss increased) by cumulative AE
  - proportional split across multiple lots
  - non-NMF symbols are unaffected
"""
import datetime
from decimal import Decimal
from unittest.mock import patch

import pytest

from core.nichtmeldefonds import compute_nmf_cumulative_ae, _get_nmf_purchase_year
from core.tax_engine import TaxEngine
from core.models import (
    NormalizedTransaction, NichtmeldefondsResult,
    TransactionType, AssetClass, Domicile,
)


# ── Shared helpers ────────────────────────────────────────────────────────────

class _FX:
    """Stub FX provider: 1 USD = 0.92 EUR."""
    def get_rate(self, currency, date):
        return Decimal("0.92")


def _txn(raw_id, symbol, txn_type, qty, eur_amount, year=2024, month=6,
         broker="test"):
    # BUY: quantity positive; SELL: quantity negative (engine uses .copy_abs() for matching)
    q = Decimal(str(qty))
    if txn_type == TransactionType.SELL:
        q = -q
    return NormalizedTransaction(
        raw_id=raw_id,
        broker=broker,
        trade_date=datetime.date(year, month, 15),
        settle_date=None,
        txn_type=txn_type,
        asset_class=AssetClass.STOCK,
        symbol=symbol,
        isin="US_FAKE",
        description="",
        country_code="US",
        domicile=Domicile.FOREIGN,
        quantity=q,
        price=None,
        price_currency=None,
        orig_currency="USD",
        orig_amount=Decimal(str(eur_amount)),
        wht_amount_orig=Decimal("0"),
        fx_rate_to_eur=Decimal("1"),
        eur_amount=Decimal(str(eur_amount)),
        eur_wht=Decimal("0"),
        eur_commission=Decimal("0"),
        source_file="test",
    )


def _saxo_buy(symbol, cost_eur, year=2020, raw_id=None):
    """SAXO qty=1 synthetic buy lot."""
    return _txn(raw_id or f"buy_{symbol}_{year}", symbol, TransactionType.BUY, 1, cost_eur,
                year=year, broker="saxo")


def _saxo_sell(symbol, proceeds_eur, year=2026, raw_id=None):
    """SAXO qty=1 synthetic sell."""
    return _txn(raw_id or f"sell_{symbol}_{year}", symbol, TransactionType.SELL, 1, proceeds_eur,
                year=year, broker="saxo")


def _minimal_config(nmf_symbols=None, manual_cost_basis=None):
    return {
        "kest_rate": "0.275",
        "max_creditable_wht": "0.15",
        "wht_treaty_rates": {},
        "nichtmeldefonds": [
            {"symbol": sym, "isin": "US_FAKE", "name": sym, "type": "REIT",
             "currency": "USD"}
            for sym in (nmf_symbols or [])
        ],
        "manual_cost_basis": manual_cost_basis or [],
    }


# ── compute_nmf_cumulative_ae ─────────────────────────────────────────────────

def _fake_nmf_result(ae_total_eur):
    """Minimal NichtmeldefondsResult stub."""
    return NichtmeldefondsResult(
        symbol="O", isin="US_FAKE", name="O Inc", fund_type="REIT",
        currency="USD", shares_held=Decimal("100"),
        price_jan1=Decimal("50"), price_dec31=Decimal("55"),
        fx_dec31=Decimal("0.92"),
        annual_gain_per_share=Decimal("5"),
        ae_90pct_per_share=Decimal("4.5"),
        ae_10pct_per_share=Decimal("5.5"),
        ae_per_share=Decimal("5.5"),
        ae_total_native=Decimal("550"),
        ae_total_eur=Decimal(str(ae_total_eur)),
        kest_due_eur=(Decimal(str(ae_total_eur)) * Decimal("0.275")).quantize(Decimal("0.01")),
        cost_basis_adj_eur=Decimal(str(ae_total_eur)),
    )


def test_cumulative_ae_sums_prior_years():
    """Two prior years of AE are summed; current year excluded."""
    config = _minimal_config(nmf_symbols=["O"],
                             manual_cost_basis=[{"symbol": "O", "purchase_date": "2024-01-01",
                                                 "quantity": 1, "cost_eur": 3000}])
    txns = []
    fx = _FX()

    # _calc_position returns 100 EUR AE per year (2024 → 100, 2025 → 150)
    def fake_calc(entry, year, all_txns, fx, price_cache_dir):
        if year == 2024:
            return _fake_nmf_result(100)
        if year == 2025:
            return _fake_nmf_result(150)
        return None

    with patch("core.nichtmeldefonds._calc_position", side_effect=fake_calc):
        result = compute_nmf_cumulative_ae(config, 2026, txns, fx)

    assert "O" in result
    assert result["O"] == Decimal("250.00")  # 100 + 150, not including 2026


def test_cumulative_ae_excludes_current_year():
    """tax_year itself is NOT included in the step-up (not yet charged)."""
    config = _minimal_config(nmf_symbols=["O"],
                             manual_cost_basis=[{"symbol": "O", "purchase_date": "2025-01-01",
                                                 "quantity": 1, "cost_eur": 3000}])
    txns = []
    fx = _FX()

    def fake_calc(entry, year, all_txns, fx, price_cache_dir):
        return _fake_nmf_result(200)  # would return for any year

    with patch("core.nichtmeldefonds._calc_position", side_effect=fake_calc) as mock:
        result = compute_nmf_cumulative_ae(config, 2026, txns, fx)
        called_years = [call.args[1] for call in mock.call_args_list]

    # purchase_year=2025, tax_year=2026 → only year 2025 should be called
    assert called_years == [2025]
    assert result["O"] == Decimal("200.00")


def test_cumulative_ae_returns_empty_when_no_nmf():
    config = _minimal_config(nmf_symbols=[])
    result = compute_nmf_cumulative_ae(config, 2026, [], _FX())
    assert result == {}


def test_cumulative_ae_symbol_absent_when_all_years_zero():
    """Symbol should not appear in result if all years returned None/zero AE."""
    config = _minimal_config(nmf_symbols=["O"],
                             manual_cost_basis=[{"symbol": "O", "purchase_date": "2025-01-01",
                                                 "quantity": 1, "cost_eur": 3000}])
    with patch("core.nichtmeldefonds._calc_position", return_value=None):
        result = compute_nmf_cumulative_ae(config, 2026, [], _FX())
    assert "O" not in result


# ── _get_nmf_purchase_year ────────────────────────────────────────────────────

def test_purchase_year_from_manual_cost_basis():
    config = _minimal_config(manual_cost_basis=[
        {"symbol": "O", "purchase_date": "2023-06-01", "quantity": 1, "cost_eur": 3000},
        {"symbol": "O", "purchase_date": "2021-03-15", "quantity": 1, "cost_eur": 1000},
    ])
    year = _get_nmf_purchase_year("O", config, [], 2026)
    assert year == 2021  # earliest of the two lots


def test_purchase_year_fallback_to_buy_txn():
    config = _minimal_config()
    txns = [_txn("b1", "EPR", TransactionType.BUY, 100, 5000, year=2022)]
    year = _get_nmf_purchase_year("EPR", config, txns, 2026)
    assert year == 2022


def test_purchase_year_fallback_when_no_data():
    config = _minimal_config()
    year = _get_nmf_purchase_year("UNKNOWN", config, [], 2026)
    assert year == 2026  # returns fallback


# ── TaxEngine FIFO step-up integration ───────────────────────────────────────

def _run_engine(buy_txns, sell_txns, step_up, tax_year=2026, config_extra=None):
    """Run TaxEngine with given step-up dict; return MatchedTrade for the sell."""
    all_txns = buy_txns + sell_txns
    config = _minimal_config()
    if config_extra:
        config.update(config_extra)
    engine = TaxEngine(config, tax_year, "test", nmf_ae_step_up=step_up)
    summary = engine.calculate(all_txns)
    return summary


def test_step_up_reduces_gain_single_lot():
    """Single SAXO qty=1 lot: cumulative AE reduces taxable gain."""
    # Buy at 3000, sell at 3200 → nominal gain 200
    # Cumulative AE step-up = 400 → adjusted cost = 3400 → loss of 200
    buy = [_saxo_buy("O", 3000, year=2020)]
    sell = [_saxo_sell("O", 3200, year=2026)]
    step_up = {"O": Decimal("400")}

    summary = _run_engine(buy, sell, step_up)

    # Adjusted cost = 3000 + 400 = 3400; proceeds = 3200 → net loss = 200
    assert summary.total_gains_eur == Decimal("0")
    assert abs(summary.total_losses_eur - Decimal("200")) < Decimal("1")


def test_step_up_reduces_gain_to_zero():
    """Step-up exactly matching the gain results in zero net gain or small rounding."""
    buy = [_saxo_buy("O", 3000, year=2020)]
    sell = [_saxo_sell("O", 3200, year=2026)]
    step_up = {"O": Decimal("200")}  # exactly offsets the 200 gain

    summary = _run_engine(buy, sell, step_up)
    assert summary.total_gains_eur == Decimal("0")
    assert summary.total_losses_eur == Decimal("0")


def test_step_up_does_not_affect_non_nmf_symbol():
    """Symbols not in nmf_ae_step_up are unaffected."""
    buy = [_txn("b1", "AAPL", TransactionType.BUY, 10, 1500, year=2024)]
    sell = [_txn("s1", "AAPL", TransactionType.SELL, 10, 2000, year=2026)]
    step_up = {"O": Decimal("500")}  # O has step-up, not AAPL

    summary = _run_engine(buy, sell, step_up)
    assert abs(summary.total_gains_eur - Decimal("500")) < Decimal("1")


def test_step_up_no_adjustment_when_dict_empty():
    """Empty step-up dict → same result as no step-up passed."""
    buy = [_saxo_buy("O", 3000, year=2020)]
    sell = [_saxo_sell("O", 3500, year=2026)]

    summary_no_adj = _run_engine(buy, sell, {})
    summary_adj = _run_engine(buy, sell, {"O": Decimal("0")})

    assert summary_no_adj.total_gains_eur == summary_adj.total_gains_eur


def test_step_up_proportional_across_two_lots():
    """Two synthetic lots: step-up split proportionally by cost fraction."""
    # Lot A: cost 1000 (25%), Lot B: cost 3000 (75%)
    # Total AE step-up: 400 → A gets 100, B gets 300
    lot_a = _saxo_buy("O", 1000, year=2020, raw_id="buy_O_2020")
    lot_b = _saxo_buy("O", 3000, year=2021, raw_id="buy_O_2021")

    # Sell lot A first (FIFO) for 1050 → adjusted cost = 1000+100 = 1100 → loss 50
    sell_a = _saxo_sell("O", 1050, year=2026, raw_id="sell_O_2026_a")

    step_up = {"O": Decimal("400")}
    all_txns = [lot_a, lot_b, sell_a]
    config = _minimal_config()
    engine = TaxEngine(config, 2026, "test", nmf_ae_step_up=step_up)
    summary = engine.calculate(all_txns)

    # FIFO picks lot_a (earlier), adjusted cost = 1000 + 100 = 1100
    # Proceeds = 1050 → net loss = 50
    assert summary.total_gains_eur == Decimal("0")
    assert abs(summary.total_losses_eur - Decimal("50")) < Decimal("2")
