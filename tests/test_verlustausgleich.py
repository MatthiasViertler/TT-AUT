"""Tests for Verlustausgleich year-over-year tracking (JSON snapshot save/load)."""
import json
from decimal import Decimal
from pathlib import Path

import pytest

from core.models import TaxSummary
from generators.writer import _load_history, _save_summary_json


def _make_summary(year: int, person: str = "Test",
                  dividends: float = 100.0, gains: float = 200.0,
                  losses: float = 50.0, net: float = 250.0,
                  kest: float = 68.75, wht: float = 15.0,
                  remaining: float = 53.75) -> TaxSummary:
    s = TaxSummary(tax_year=year, person_label=person)
    s.total_dividends_eur = Decimal(str(dividends))
    s.total_gains_eur     = Decimal(str(gains))
    s.total_losses_eur    = Decimal(str(losses))
    s.net_taxable_eur     = Decimal(str(net))
    s.kest_due_eur        = Decimal(str(kest))
    s.wht_creditable_eur  = Decimal(str(wht))
    s.kest_remaining_eur  = Decimal(str(remaining))
    return s


def test_save_summary_json_creates_file(tmp_path):
    s = _make_summary(2024)
    p = tmp_path / "Test_2024_summary.json"
    _save_summary_json(s, p)
    assert p.exists()


def test_save_summary_json_correct_values(tmp_path):
    s = _make_summary(2024, dividends=123.45, gains=678.90)
    p = tmp_path / "Test_2024_summary.json"
    _save_summary_json(s, p)

    data = json.loads(p.read_text())
    assert data["tax_year"] == 2024
    assert data["person_label"] == "Test"
    assert Decimal(data["total_dividends_eur"]) == Decimal("123.45")
    assert Decimal(data["total_gains_eur"]) == Decimal("678.90")


def test_load_history_returns_sorted_years(tmp_path):
    for year in (2023, 2021, 2022):
        s = _make_summary(year)
        _save_summary_json(s, tmp_path / f"Test_{year}_summary.json")

    history = _load_history("Test", tmp_path)
    assert [e["tax_year"] for e in history] == [2021, 2022, 2023]


def test_load_history_filters_by_person(tmp_path):
    _save_summary_json(_make_summary(2024, person="Alice"),
                       tmp_path / "Alice_2024_summary.json")
    _save_summary_json(_make_summary(2024, person="Bob"),
                       tmp_path / "Bob_2024_summary.json")

    alice_hist = _load_history("Alice", tmp_path)
    assert len(alice_hist) == 1
    assert alice_hist[0]["person_label"] == "Alice"

    bob_hist = _load_history("Bob", tmp_path)
    assert len(bob_hist) == 1
    assert bob_hist[0]["person_label"] == "Bob"


def test_load_history_empty_dir(tmp_path):
    assert _load_history("Nobody", tmp_path) == []


def test_load_history_missing_dir():
    assert _load_history("Nobody", Path("/nonexistent/path")) == []


def test_load_history_skips_corrupt_json(tmp_path):
    # Valid file
    _save_summary_json(_make_summary(2024), tmp_path / "Test_2024_summary.json")
    # Corrupt file — should be silently skipped
    (tmp_path / "Test_2023_summary.json").write_text("not valid json")

    history = _load_history("Test", tmp_path)
    assert len(history) == 1
    assert history[0]["tax_year"] == 2024


def test_roundtrip_decimal_precision(tmp_path):
    s = _make_summary(2025, dividends=3808.73, kest=1047.40, wht=431.87, remaining=615.53)
    p = tmp_path / "Test_2025_summary.json"
    _save_summary_json(s, p)

    data = json.loads(p.read_text())
    assert Decimal(data["total_dividends_eur"]) == Decimal("3808.73")
    assert Decimal(data["kest_due_eur"]) == Decimal("1047.40")
    assert Decimal(data["kest_remaining_eur"]) == Decimal("615.53")
