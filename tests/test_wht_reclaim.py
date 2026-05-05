"""
Tests for WHT reclaim calculations.

Ground truth for 2025 DE is confirmed against the IBKR German Tax Report
(report ID 126354004/20251231, Line 7 = EUR 3,808.73).
"""
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from core.models import TransactionType
from generators.wht_reclaim import write_wht_reclaim_report
from tests.conftest import make_dividend

ZERO = Decimal("0")


# ── helpers ───────────────────────────────────────────────────────────────────

def _run_report(transactions, cfg_override: dict | None = None) -> str:
    """Run the reclaim report and return its text content."""
    base_cfg = {
        "max_creditable_wht": 0.15,
        "wht_treaty_rates": {"DE": 0.15, "DK": 0.15, "FR": 0.15},
        "at_residency_start_year": 2024,
    }
    if cfg_override:
        base_cfg.update(cfg_override)
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
        out = Path(f.name)
    write_wht_reclaim_report(transactions, base_cfg, 2025, "Test", out)
    text = out.read_text(encoding="utf-8")
    out.unlink()
    return text


# ── basic calculation ─────────────────────────────────────────────────────────

def test_de_excess_calculated():
    """DE gross 100, WHT 26.375 → creditable 15, excess 11.375."""
    txn = make_dividend("ALV", "DE0008404005", gross_eur=100.0, wht_eur=26.375)
    text = _run_report([txn])
    assert "Germany" in text
    assert "11.38" in text or "11.37" in text  # rounding tolerance


def test_no_excess_below_threshold():
    """WHT exactly at treaty rate → no excess → country absent from report."""
    txn = make_dividend("ALV", "DE0008404005", gross_eur=100.0, wht_eur=15.0)
    text = _run_report([txn])
    # No reclaimable amount → report should be empty (function returns early)
    assert text == "" or "Germany" not in text


def test_sub_cent_threshold_suppressed():
    """Excess ≤ 0.05 is treated as rounding noise and suppressed."""
    txn = make_dividend("ALV", "DE0008404005", gross_eur=100.0, wht_eur=15.04)
    # excess = 15.04 - 15% × 100 = 0.04 → below threshold
    text = _run_report([txn])
    assert text == "" or "Germany" not in text


def test_residency_filter_excludes_pre_2024():
    """Dividends before at_residency_start_year must be excluded."""
    txn_before = make_dividend("ALV", "DE0008404005", gross_eur=500.0, wht_eur=131.875,
                               trade_date=date(2023, 5, 1))
    txn_after  = make_dividend("ALV", "DE0008404005", gross_eur=500.0, wht_eur=131.875,
                               trade_date=date(2024, 5, 1))
    # Only 2024 dividend should appear
    text = _run_report([txn_before, txn_after])
    assert "2023" not in text
    assert "2024" in text


def test_dk_excess_uses_treaty_rate():
    """DK: 27% withheld, 15% creditable → 12% excess."""
    txn = make_dividend("NOV", "DK0062498333", gross_eur=100.0, wht_eur=27.0,
                        country_code="DK")
    text = _run_report([txn])
    assert "Denmark" in text
    assert "12.00" in text


def test_nl_no_excess_at_15pct():
    """NL: 15% WHT = treaty rate → no excess → not in report."""
    txn = make_dividend("SHELL", "NL0000235190", gross_eur=100.0, wht_eur=15.0,
                        country_code="NL")
    text = _run_report([txn])
    assert text == "" or "Netherlands" not in text


# ── 2025 DE ground truth (confirmed against IBKR German Tax Report) ──────────
# Source: report 126354004/20251231, "Dividends subjected to German WHT" section.
# All amounts in EUR; WHT includes base WHT + Solidarity surcharge as withheld by IB.

DE_2025_DIVIDENDS = [
    # (symbol, isin, gross_eur, wht_eur)   date is illustrative; year matters for residency
    ("ALV",  "DE0008404005", 1539.99, 406.17),   # 385.00 + 21.17 Soli
    ("BAS",  "DE000BASF111",  360.00,  94.95),   # 90.00 + 4.95
    ("BAYN", "DE000BAY0017",   16.50,   4.35),   # 4.12 + 0.23
    ("BMW",  "DE0005190003",  215.00,  56.71),   # 53.75 + 2.96
    ("P911", "DE000PAG9113",   40.84,  10.77),   # 10.21 + 0.56
    ("FRE",  "DE0005785604",   71.00,  18.73),   # 17.75 + 0.98
    ("HNR1", "DE0008402215",  180.00,  47.48),   # (140+40) gross, (35+10+1.93+0.55) WHT
    ("IFX",  "DE0006231004",  140.00,  36.92),   # 35.00 + 1.92
    ("MBG",  "DE0007100000",  430.00, 113.41),   # 107.50 + 5.91
    ("MUV2", "DE0008430026",  400.00, 105.50),   # 100.00 + 5.50
    ("SIE",  "DE0007236101",  104.00,  26.06),   # 24.70 + 1.36
    ("SHL",  "DE000SHL1006",   57.00,  15.03),   # 14.25 + 0.78
    ("VOW3", "DE0007664039",  254.40,  67.10),   # 63.60 + 3.50
]

EXPECTED_DE_2025_GROSS  = Decimal("3808.73")
EXPECTED_DE_2025_WHT    = Decimal("1003.18")   # 950.88 base + 52.30 Soli
EXPECTED_DE_2025_CREDIT = Decimal("571.31")    # 15% × 3808.73
EXPECTED_DE_2025_EXCESS = Decimal("431.87")    # 1003.18 - 571.31


@pytest.fixture
def de_2025_txns():
    return [
        make_dividend(sym, isin, gross, wht, trade_date=date(2025, 5, 13))
        for sym, isin, gross, wht in DE_2025_DIVIDENDS
    ]


def test_de_2025_gross_total(de_2025_txns):
    actual = sum(t.eur_amount for t in de_2025_txns)
    assert actual == EXPECTED_DE_2025_GROSS


def test_de_2025_wht_total(de_2025_txns):
    actual = sum(t.eur_wht for t in de_2025_txns)
    assert actual == EXPECTED_DE_2025_WHT


def test_de_2025_reclaim_in_report(de_2025_txns):
    text = _run_report(de_2025_txns)
    assert "431.87" in text


def test_de_2025_report_contains_all_stocks(de_2025_txns):
    text = _run_report(de_2025_txns)
    for sym, *_ in DE_2025_DIVIDENDS:
        assert sym in text, f"{sym} missing from WHT reclaim report"
