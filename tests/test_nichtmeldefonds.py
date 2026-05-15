"""Tests for core/nichtmeldefonds.py — pauschal AE calculation."""
import datetime
from decimal import Decimal
from unittest.mock import patch

import pytest

from core.nichtmeldefonds import calculate_nichtmeldefonds, _net_shares_at_year_end
from core.models import NormalizedTransaction, TransactionType, AssetClass, Domicile


def _buy(symbol, qty, year=2023):
    return NormalizedTransaction(
        raw_id=f"buy_{symbol}_{year}",
        broker="test",
        trade_date=datetime.date(year, 6, 1),
        settle_date=None,
        txn_type=TransactionType.BUY,
        asset_class=AssetClass.STOCK,
        symbol=symbol,
        isin=None,
        description="",
        country_code="US",
        domicile=Domicile.FOREIGN,
        quantity=Decimal(str(qty)),
        price=Decimal("10"),
        price_currency="USD",
        orig_currency="USD",
        orig_amount=Decimal(str(qty)) * Decimal("10"),
        wht_amount_orig=Decimal("0"),
        fx_rate_to_eur=Decimal("1"),
        eur_amount=Decimal(str(qty)) * Decimal("10"),
        eur_wht=Decimal("0"),
        eur_commission=Decimal("0"),
        source_file="test",
    )


def _sell(symbol, qty, year=2024):
    return NormalizedTransaction(
        raw_id=f"sell_{symbol}_{year}",
        broker="test",
        trade_date=datetime.date(year, 6, 1),
        settle_date=None,
        txn_type=TransactionType.SELL,
        asset_class=AssetClass.STOCK,
        symbol=symbol,
        isin=None,
        description="",
        country_code="US",
        domicile=Domicile.FOREIGN,
        quantity=-Decimal(str(qty)),
        price=Decimal("10"),
        price_currency="USD",
        orig_currency="USD",
        orig_amount=Decimal(str(qty)) * Decimal("10"),
        wht_amount_orig=Decimal("0"),
        fx_rate_to_eur=Decimal("1"),
        eur_amount=Decimal(str(qty)) * Decimal("10"),
        eur_wht=Decimal("0"),
        eur_commission=Decimal("0"),
        source_file="test",
    )


# ---------------------------------------------------------------------------
# _net_shares_at_year_end
# ---------------------------------------------------------------------------

def test_net_shares_simple():
    txns = [_buy("O", 100, 2022), _buy("O", 50, 2023)]
    assert _net_shares_at_year_end(txns, "O", 2024) == Decimal("150")


def test_net_shares_excludes_future_buys():
    txns = [_buy("O", 100, 2023), _buy("O", 50, 2025)]
    assert _net_shares_at_year_end(txns, "O", 2024) == Decimal("100")


def test_net_shares_after_partial_sell():
    txns = [_buy("O", 100, 2022), _sell("O", 30, 2024)]
    assert _net_shares_at_year_end(txns, "O", 2024) == Decimal("70")


def test_net_shares_floor_zero():
    txns = [_buy("O", 10, 2022), _sell("O", 15, 2024)]
    assert _net_shares_at_year_end(txns, "O", 2024) == Decimal("0")


# ---------------------------------------------------------------------------
# shares_held_override
# ---------------------------------------------------------------------------

class _FX:
    def get_rate(self, currency, date):
        return Decimal("0.96")  # ~EUR/USD Dec 2024


@patch("core.nichtmeldefonds.get_year_end_price")
def test_shares_held_override_used(mock_price):
    mock_price.return_value = Decimal("50")
    config = {
        "nichtmeldefonds": [{
            "symbol": "O",
            "isin": "US7561091049",
            "name": "Realty Income",
            "type": "REIT",
            "currency": "USD",
            "shares_held_override": {2024: 150},
        }],
        "price_cache_dir": "/tmp",
    }
    # No BUY transactions — without override, shares=0 and result would be None
    results = calculate_nichtmeldefonds(config, 2024, [], _FX())
    assert len(results) == 1
    assert results[0].shares_held == Decimal("150")


@patch("core.nichtmeldefonds.get_year_end_price")
def test_shares_held_override_per_year(mock_price):
    mock_price.return_value = Decimal("50")
    config = {
        "nichtmeldefonds": [{
            "symbol": "ARCC",
            "isin": "US04010L1035",
            "name": "Ares Capital",
            "type": "BDC",
            "currency": "USD",
            "shares_held_override": {2024: 110, 2025: 118},
        }],
        "price_cache_dir": "/tmp",
    }
    r24 = calculate_nichtmeldefonds(config, 2024, [], _FX())
    r25 = calculate_nichtmeldefonds(config, 2025, [], _FX())
    assert r24[0].shares_held == Decimal("110")
    assert r25[0].shares_held == Decimal("118")


@patch("core.nichtmeldefonds.get_year_end_price")
def test_shares_held_override_falls_back_to_transactions(mock_price):
    mock_price.return_value = Decimal("50")
    config = {
        "nichtmeldefonds": [{
            "symbol": "O",
            "isin": "US7561091049",
            "name": "Realty Income",
            "type": "REIT",
            "currency": "USD",
            "shares_held_override": {2025: 150},  # only 2025 — 2024 should fall back
        }],
        "price_cache_dir": "/tmp",
    }
    txns = [_buy("O", 75, 2022)]
    r24 = calculate_nichtmeldefonds(config, 2024, txns, _FX())
    r25 = calculate_nichtmeldefonds(config, 2025, txns, _FX())
    assert r24[0].shares_held == Decimal("75")   # from transactions
    assert r25[0].shares_held == Decimal("150")  # from override


# ---------------------------------------------------------------------------
# AE calculation correctness
# ---------------------------------------------------------------------------

@patch("core.nichtmeldefonds.get_year_end_price")
def test_ae_uses_10pct_minimum_when_price_dropped(mock_price):
    # Price fell: 90% rule gives 0, 10% minimum applies
    mock_price.side_effect = lambda sym, cur, year, cache: (
        Decimal("50") if year == 2024 else Decimal("55")  # fell from 55 to 50
    )
    config = {
        "nichtmeldefonds": [{
            "symbol": "O", "isin": "X", "name": "O", "type": "REIT", "currency": "USD",
            "shares_held_override": {2024: 100},
        }],
        "price_cache_dir": "/tmp",
    }
    results = calculate_nichtmeldefonds(config, 2024, [], _FX())
    r = results[0]
    # AE per share = max(90%×0, 10%×50) = 5.00
    assert r.ae_per_share == Decimal("5.00")
    assert r.ae_total_native == Decimal("500.00")
    assert r.kest_due_eur == (Decimal("500.00") * Decimal("0.96") * Decimal("0.275")).quantize(Decimal("0.01"))


@patch("core.nichtmeldefonds.get_year_end_price")
def test_ae_uses_90pct_when_large_gain(mock_price):
    # Price rose significantly: 90% rule exceeds 10% minimum
    mock_price.side_effect = lambda sym, cur, year, cache: (
        Decimal("100") if year == 2024 else Decimal("50")  # doubled
    )
    config = {
        "nichtmeldefonds": [{
            "symbol": "O", "isin": "X", "name": "O", "type": "REIT", "currency": "USD",
            "shares_held_override": {2024: 10},
        }],
        "price_cache_dir": "/tmp",
    }
    results = calculate_nichtmeldefonds(config, 2024, [], _FX())
    r = results[0]
    # AE per share = max(90%×50, 10%×100) = max(45, 10) = 45
    assert r.ae_per_share == Decimal("45.00")
    assert r.ae_total_native == Decimal("450.00")
