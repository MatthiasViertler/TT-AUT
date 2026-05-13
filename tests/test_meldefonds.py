"""
Tests for core/meldefonds.py — OeKB-registered fund AE/WA calculation.

Covers: dataset lookup, share count inference, KZ routing (936/937),
WA credit, distributing vs accumulating, ISIN-fallback matching,
zero-AE handling, and missing-data warnings.
"""

import sys
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.meldefonds import _reset_cache, calculate_meldefonds, _parse_date
from core.models import (
    AssetClass, Domicile, MeldefondsResult, NormalizedTransaction, TransactionType,
)
from tests.conftest import make_trade


# ── helpers ───────────────────────────────────────────────────────────────────

class _FakeFX:
    """Minimal FX stub: always returns the given rate for any currency/date."""
    def __init__(self, rate: float = 1.10):
        self.rate = Decimal(str(rate))

    def get_rate(self, currency: str, d: date) -> Decimal:
        return self.rate


def _make_dataset(**kwargs) -> dict:
    """Build a minimal oekb_ae.yaml dataset dict with one fund entry."""
    return kwargs


def _run(dataset: dict, config_extra: dict, transactions, tax_year: int = 2024,
         fx_rate: float = 1.10) -> list[MeldefondsResult]:
    """
    Write dataset to a temp file, build config, and call calculate_meldefonds.
    Resets the module-level cache before each call.
    """
    _reset_cache()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(dataset, f)
        tmp_path = f.name

    config = {"meldefonds_data_file": tmp_path, **config_extra}
    return calculate_meldefonds(config, tax_year, transactions, _FakeFX(fx_rate))


VWRL_ISIN = "IE00B3RBWM25"
VWCE_ISIN = "IE00BK5BQT80"

_VWRL_ENTRY = {
    "symbol": "VWRL",
    "name": "Vanguard FTSE All-World UCITS ETF (Distributing)",
    "type": "ETF",
    "currency": "USD",
    "domicile": "IE",
    "ertragsverwendung": "ausschüttend",
    "data": {
        2024: {
            "ae_per_share": 0.10,
            "wa_per_share": 0.02,
            "ak_korrektur_per_share": 0.05,
            "meldedatum": "2025-01-15",
        }
    },
}

_VWCE_ENTRY = {
    "symbol": "VWCE",
    "name": "Vanguard FTSE All-World UCITS ETF (Accumulating)",
    "type": "ETF",
    "currency": "USD",
    "domicile": "IE",
    "ertragsverwendung": "thesaurierend",
    "data": {
        2024: {
            "ae_per_share": 0.3618,
            "wa_per_share": 0.0,
            "ak_korrektur_per_share": 0.3618,
            "meldedatum": "2025-01-15",
        }
    },
}


def _buy(symbol: str, isin: str, qty: float, d: date = date(2023, 1, 1)) -> NormalizedTransaction:
    return make_trade(symbol, isin, TransactionType.BUY, qty, 80.0, trade_date=d)


def _sell(symbol: str, isin: str, qty: float, d: date = date(2024, 6, 1)) -> NormalizedTransaction:
    return make_trade(symbol, isin, TransactionType.SELL, qty, 90.0, trade_date=d)


# ── basic AE calculation ──────────────────────────────────────────────────────

def test_vwrl_basic_ae():
    """AE = ae_per_share × shares × FX; KeSt = 27.5% × AE; WA reduces net."""
    dataset = {VWRL_ISIN: _VWRL_ENTRY}
    txns = [_buy("VWRL", VWRL_ISIN, 100)]
    config = {"meldefonds": [{"isin": VWRL_ISIN, "symbol": "VWRL"}]}

    results = _run(dataset, config, txns, tax_year=2024, fx_rate=1.10)

    assert len(results) == 1
    r = results[0]
    assert r.isin == VWRL_ISIN
    assert r.symbol == "VWRL"
    assert r.shares_held == Decimal("100")

    # AE: 0.10 USD/sh × 100 × 1.10 FX = 11.00 EUR
    assert r.ae_total_eur == Decimal("11.00")
    # WA: 0.02 USD/sh × 100 × 1.10 = 2.20 EUR
    assert r.wa_total_eur == Decimal("2.20")
    # KeSt gross: 27.5% × 11.00 = 3.025 → 3.03 EUR
    assert r.kest_gross_eur == Decimal("3.03")
    # KeSt net: 3.03 - 2.20 = 0.83 EUR
    assert r.kest_net_eur == Decimal("0.83")


def test_vwce_thesaurierend_full_ae():
    """Accumulating fund: full AE declared; no WA."""
    dataset = {VWCE_ISIN: _VWCE_ENTRY}
    txns = [_buy("VWCE", VWCE_ISIN, 50)]
    config = {"meldefonds": [{"isin": VWCE_ISIN, "symbol": "VWCE"}]}

    results = _run(dataset, config, txns, tax_year=2024, fx_rate=1.05)

    assert len(results) == 1
    r = results[0]
    # AE: 0.3618 × 50 × 1.05 = 18.9945 → 19.00 EUR
    expected_ae = (Decimal("0.3618") * Decimal("50") * Decimal("1.05")).quantize(Decimal("0.01"))
    assert r.ae_total_eur == expected_ae
    assert r.wa_total_eur == Decimal("0.00")
    assert r.kest_net_eur == r.kest_gross_eur   # no WA credit


# ── KZ routing ───────────────────────────────────────────────────────────────

def test_foreign_isin_routes_to_kz_937():
    """IE-domicile ISIN → KZ 937 (ausländisch)."""
    dataset = {VWRL_ISIN: _VWRL_ENTRY}
    txns = [_buy("VWRL", VWRL_ISIN, 10)]
    results = _run(dataset, {"meldefonds": [{"isin": VWRL_ISIN}]}, txns)
    assert results[0].kz == "937"


def test_at_isin_routes_to_kz_936():
    """AT-domicile fund → KZ 936 (inländisch)."""
    at_isin = "AT0000A0E9W5"
    entry = {**_VWRL_ENTRY, "domicile": "AT"}
    dataset = {at_isin: entry}
    txns = [_buy("ATFUND", at_isin, 20)]
    results = _run(dataset, {"meldefonds": [{"isin": at_isin, "symbol": "ATFUND"}]}, txns)
    assert results[0].kz == "936"


# ── distributing vs accumulating ─────────────────────────────────────────────

def test_ausschuettend_and_thesaurierend_same_formula():
    """Same AE formula regardless of ertragsverwendung."""
    ae = 0.20
    entry_dist = {**_VWRL_ENTRY, "ertragsverwendung": "ausschüttend",
                  "data": {2024: {"ae_per_share": ae, "wa_per_share": 0.0,
                                  "ak_korrektur_per_share": ae, "meldedatum": "2025-01-15"}}}
    entry_acc  = {**_VWRL_ENTRY, "ertragsverwendung": "thesaurierend",
                  "data": {2024: {"ae_per_share": ae, "wa_per_share": 0.0,
                                  "ak_korrektur_per_share": ae, "meldedatum": "2025-01-15"}}}

    txns = [_buy("VWRL", VWRL_ISIN, 100)]

    r_dist = _run({VWRL_ISIN: entry_dist}, {"meldefonds": [{"isin": VWRL_ISIN}]}, txns)[0]
    r_acc  = _run({VWRL_ISIN: entry_acc},  {"meldefonds": [{"isin": VWRL_ISIN}]}, txns)[0]

    assert r_dist.ae_total_eur == r_acc.ae_total_eur
    assert r_dist.kest_gross_eur == r_acc.kest_gross_eur
    assert r_dist.ertragsverwendung == "ausschüttend"
    assert r_acc.ertragsverwendung == "thesaurierend"


# ── share count inference ─────────────────────────────────────────────────────

def test_shares_from_transaction_history():
    """Buys and partial sells are accumulated correctly."""
    txns = [
        _buy("VWRL", VWRL_ISIN, 100, date(2022, 3, 1)),
        _buy("VWRL", VWRL_ISIN,  50, date(2023, 6, 1)),
        _sell("VWRL", VWRL_ISIN, 30, date(2024, 3, 1)),
    ]
    dataset = {VWRL_ISIN: _VWRL_ENTRY}
    results = _run(dataset, {"meldefonds": [{"isin": VWRL_ISIN}]}, txns)
    assert results[0].shares_held == Decimal("120")  # 100 + 50 - 30


def test_future_buys_excluded():
    """Transactions after tax_year are not counted."""
    txns = [
        _buy("VWRL", VWRL_ISIN, 100, date(2024, 6, 1)),
        _buy("VWRL", VWRL_ISIN,  50, date(2025, 1, 15)),  # after 2024 → excluded
    ]
    dataset = {VWRL_ISIN: _VWRL_ENTRY}
    results = _run(dataset, {"meldefonds": [{"isin": VWRL_ISIN}]}, txns, tax_year=2024)
    assert results[0].shares_held == Decimal("100")


def test_isin_fallback_matching():
    """If ticker not found, fall back to ISIN-based matching."""
    txns = [
        make_trade("VWRL.L", VWRL_ISIN, TransactionType.BUY, 75, 80.0,
                   trade_date=date(2024, 3, 1))
    ]
    dataset = {VWRL_ISIN: _VWRL_ENTRY}
    # Config has wrong symbol → ISIN fallback should pick up VWRL.L transactions
    results = _run(dataset, {"meldefonds": [{"isin": VWRL_ISIN, "symbol": "WRONG"}]}, txns)
    assert results[0].shares_held == Decimal("75")


def test_no_shares_returns_none():
    """Position with zero shares at year-end → no result."""
    txns = [
        _buy("VWRL",  VWRL_ISIN, 50, date(2023, 1, 1)),
        _sell("VWRL", VWRL_ISIN, 50, date(2024, 3, 1)),  # fully sold
    ]
    dataset = {VWRL_ISIN: _VWRL_ENTRY}
    results = _run(dataset, {"meldefonds": [{"isin": VWRL_ISIN}]}, txns)
    assert len(results) == 0


# ── missing data / edge cases ─────────────────────────────────────────────────

def test_isin_not_in_dataset_returns_empty():
    """ISIN missing from oekb_ae.yaml → no result, warning logged."""
    txns = [_buy("XYZ", "IE00XXXXXXXX", 10)]
    results = _run({}, {"meldefonds": [{"isin": "IE00XXXXXXXX", "symbol": "XYZ"}]}, txns)
    assert results == []


def test_no_year_data_returns_empty():
    """Year not in dataset data dict → no result."""
    entry = {**_VWRL_ENTRY, "data": {2023: _VWRL_ENTRY["data"][2024]}}  # only 2023, not 2024
    dataset = {VWRL_ISIN: entry}
    txns = [_buy("VWRL", VWRL_ISIN, 50)]
    results = _run(dataset, {"meldefonds": [{"isin": VWRL_ISIN}]}, txns, tax_year=2024)
    assert results == []


def test_zero_ae_produces_warning():
    """AE=0 is valid (ausschüttend often 0) but produces a warning string."""
    entry = {**_VWRL_ENTRY, "data": {2024: {"ae_per_share": 0.0, "wa_per_share": 0.0,
                                             "ak_korrektur_per_share": 0.0,
                                             "meldedatum": "2025-01-15"}}}
    dataset = {VWRL_ISIN: entry}
    txns = [_buy("VWRL", VWRL_ISIN, 100)]
    results = _run(dataset, {"meldefonds": [{"isin": VWRL_ISIN}]}, txns)
    assert len(results) == 1
    assert results[0].ae_total_eur == Decimal("0.00")
    assert results[0].warning != ""  # warning is set


def test_wa_never_exceeds_kest_gross():
    """WA cannot make KeSt negative — kest_net clamped to 0."""
    entry = {**_VWRL_ENTRY, "data": {2024: {"ae_per_share": 0.10, "wa_per_share": 9.99,
                                             "ak_korrektur_per_share": 0.0,
                                             "meldedatum": "2025-01-15"}}}
    dataset = {VWRL_ISIN: entry}
    txns = [_buy("VWRL", VWRL_ISIN, 10)]
    results = _run(dataset, {"meldefonds": [{"isin": VWRL_ISIN}]}, txns)
    assert results[0].kest_net_eur == Decimal("0.00")


def test_multiple_positions():
    """Two different ISINs both computed independently."""
    dataset = {VWRL_ISIN: _VWRL_ENTRY, VWCE_ISIN: _VWCE_ENTRY}
    txns = [_buy("VWRL", VWRL_ISIN, 100), _buy("VWCE", VWCE_ISIN, 50)]
    config = {"meldefonds": [{"isin": VWRL_ISIN}, {"isin": VWCE_ISIN}]}
    results = _run(dataset, config, txns)
    assert len(results) == 2
    isins = {r.isin for r in results}
    assert VWRL_ISIN in isins and VWCE_ISIN in isins


def test_ak_korrektur_negative_for_distributing():
    """Negative ak_korrektur (distributions exceeded AE) stored correctly."""
    entry = {**_VWRL_ENTRY, "data": {2024: {"ae_per_share": 0.0, "wa_per_share": 0.0,
                                             "ak_korrektur_per_share": -0.0988,
                                             "meldedatum": "2025-01-15"}}}
    dataset = {VWRL_ISIN: entry}
    txns = [_buy("VWRL", VWRL_ISIN, 100)]
    results = _run(dataset, {"meldefonds": [{"isin": VWRL_ISIN}]}, txns)
    assert results[0].ak_korrektur_eur < Decimal("0")


# ── helper tests ─────────────────────────────────────────────────────────────

def test_parse_date_valid():
    assert _parse_date("2025-01-15") == date(2025, 1, 15)


def test_parse_date_invalid():
    assert _parse_date("not-a-date") is None
    assert _parse_date("") is None
    assert _parse_date(None) is None
