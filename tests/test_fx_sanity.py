"""
Tests for FX rate sanity check (>20% day-over-day deviation triggers a log warning).
"""
import json
import logging
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from core.fx import FXRateProvider


def _provider_with_cache(rates_by_date: dict, year: int = 2025) -> FXRateProvider:
    """Build a FXRateProvider with a pre-seeded cache, no live fetch."""
    with tempfile.TemporaryDirectory() as d:
        cache_dir = Path(d)
        cache_file = cache_dir / f"DKK_{year}.json"
        cache_file.write_text(json.dumps(rates_by_date))
        prov = FXRateProvider(cache_dir=str(cache_dir), fetch_live=False)
        yield prov


@pytest.fixture
def provider_normal():
    """Two consecutive days with <20% deviation."""
    rates = {
        "2025-05-12": "0.134000",
        "2025-05-13": "0.135000",   # +0.75% — normal
    }
    yield from _provider_with_cache(rates)


@pytest.fixture
def provider_spike():
    """Two consecutive days with >20% deviation (simulated data error)."""
    rates = {
        "2025-05-12": "0.134000",
        "2025-05-13": "0.170000",   # +26.9% — anomalous
    }
    yield from _provider_with_cache(rates)


def test_normal_rate_no_warning(provider_normal, caplog):
    with caplog.at_level(logging.WARNING, logger="core.fx"):
        provider_normal.get_rate("DKK", date(2025, 5, 13))
    assert not any("sanity" in r.message.lower() for r in caplog.records)


def test_spike_rate_warns(provider_spike, caplog):
    with caplog.at_level(logging.WARNING, logger="core.fx"):
        provider_spike.get_rate("DKK", date(2025, 5, 13))
    assert any("sanity" in r.message.lower() for r in caplog.records)


def test_spike_warning_contains_currency(provider_spike, caplog):
    with caplog.at_level(logging.WARNING, logger="core.fx"):
        provider_spike.get_rate("DKK", date(2025, 5, 13))
    assert any("DKK" in r.message for r in caplog.records if "sanity" in r.message.lower())


def test_no_prior_day_no_warning(caplog):
    """Only one rate in cache — no prior day to compare against, no warning."""
    rates = {"2025-05-13": "0.134000"}
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "DKK_2025.json").write_text(json.dumps(rates))
        prov = FXRateProvider(cache_dir=d, fetch_live=False)
        with caplog.at_level(logging.WARNING, logger="core.fx"):
            prov.get_rate("DKK", date(2025, 5, 13))
    assert not any("sanity" in r.message.lower() for r in caplog.records)


def test_eur_skips_check(caplog):
    """EUR always returns 1.0 and never triggers the sanity check."""
    prov = FXRateProvider(cache_dir="/tmp", fetch_live=False)
    with caplog.at_level(logging.WARNING, logger="core.fx"):
        rate = prov.get_rate("EUR", date(2025, 5, 13))
    assert rate == Decimal("1.0")
    assert not any("sanity" in r.message.lower() for r in caplog.records)
