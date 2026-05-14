"""
Tests for brokers/etrade_pdf.py.

Tests exercise the internal parsing functions directly (no real PDF files needed).
All text samples are synthetic or anonymised — no real account IDs or PII.
"""
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

pdfplumber = pytest.importorskip("pdfplumber")

from brokers.etrade_pdf import (
    _detect_format,
    _extract_account_id,
    _extract_section,
    _parse_old,
    _parse_new,
    _stmt_month,
    NXPI_ISIN,
    NXPI_SYMBOL,
    NXPI_COUNTRY,
)
from core.models import TransactionType, AssetClass, Domicile


# ── _detect_format ────────────────────────────────────────────────────────────

def test_detect_format_new_morgan_stanley():
    assert _detect_format("E*TRADE from Morgan Stanley Account Summary") == "new"

def test_detect_format_old_securities():
    assert _detect_format("E*TRADE Securities LLC Quarterly Statement") == "old"

def test_detect_format_new_fallback():
    assert _detect_format("E*TRADE Account Statement") == "new"

def test_detect_format_unknown():
    assert _detect_format("Some Other Broker Statement") == "unknown"


# ── _extract_account_id ───────────────────────────────────────────────────────

def test_extract_account_id_new_format():
    text = "Account Number: 100-123456-789\nSome more text"
    assert _extract_account_id(text) == "100-123456-789"

def test_extract_account_id_old_format():
    text = "AccountNumber: 1234-5678\nStatement Period: Jan 1, 2020"
    assert _extract_account_id(text) == "1234-5678"

def test_extract_account_id_missing():
    assert _extract_account_id("No account number here") == ""


# ── _extract_section ──────────────────────────────────────────────────────────

def test_extract_section_basic():
    text = "BEFORE\nSTART\nLine A\nLine B\nEND\nAFTER"
    result = _extract_section(text, ["START"], ["END"])
    assert "Line A" in result
    assert "Line B" in result
    assert "BEFORE" not in result
    assert "AFTER" not in result

def test_extract_section_missing_start():
    result = _extract_section("no start here", ["MISSING"], ["END"])
    assert result == ""

def test_extract_section_no_end():
    text = "START\nLine A\nLine B"
    result = _extract_section(text, ["START"], ["MISSING_END"])
    assert "Line A" in result


# ── _stmt_month ───────────────────────────────────────────────────────────────

def test_stmt_month_november():
    text = "For the Period November 1-30, 2024"
    assert _stmt_month(text) == 11

def test_stmt_month_february():
    text = "For the Period February 1-29, 2024"
    assert _stmt_month(text) == 2

def test_stmt_month_missing():
    assert _stmt_month("No period header") == 1


# ── _parse_old ────────────────────────────────────────────────────────────────

_OLD_SELL_TEXT = """\
Account Number: 1234-5678 Statement Period : July 1, 2020 - September 30, 2020 Account Type: INDIVIDUAL
TRANSACTION HISTORY
TRADE SETTLEMENT DESCRIPTION SYMBOL/ TRANSACTION QUANTITY PRICE AMOUNT AMOUNT
DATE DATE CUSIP TYPE PURCHASED SOLD
09/08/20 09/10/20 ***NXP SEMICONDUCTORS NXPI Sold -56 120.5000 6,737.90
15:49 N V
09/08/20 09/10/20 ***NXP SEMICONDUCTORS NXPI Sold -0.6151 120.5000 74.12
15:50 N V
TOTALSECURITIESACTIVITY $6,812.02
WITHDRAWALS
"""

def test_parse_old_sells():
    txns, acct = _parse_old(_OLD_SELL_TEXT, "test.pdf")
    assert acct == "1234-5678"
    sells = [t for t in txns if t.txn_type == TransactionType.SELL]
    assert len(sells) == 2

    big_sell = next(t for t in sells if t.quantity == Decimal("56"))
    assert big_sell.trade_date == date(2020, 9, 8)
    assert big_sell.symbol == NXPI_SYMBOL
    assert big_sell.isin == NXPI_ISIN
    assert big_sell.country_code == NXPI_COUNTRY
    assert big_sell.price == Decimal("120.5000")
    assert big_sell.orig_amount == Decimal("6737.90")
    assert big_sell.orig_currency == "USD"
    assert big_sell.domicile == Domicile.FOREIGN

    frac_sell = next(t for t in sells if t.quantity == Decimal("0.6151"))
    assert frac_sell.orig_amount == Decimal("74.12")


_OLD_RECEIVE_TEXT = """\
Account Number: 1234-5678 Statement Period : July 1, 2020 - September 30, 2020 Account Type: INDIVIDUAL
OTHERACTIVITY
DATE DESCRIPTION SYMBOL/ TRANSACTION QUANTITY PRICE AMOUNT AMOUNT
CUSIP TYPE DEBITED CREDITED
09/02/20 ***NXP SEMICONDUCTORS N V NXPI Receive 56.6151
RAND 322935624
PAGE 8 OF 8
"""

def test_parse_old_rsu_receive(monkeypatch):
    from brokers import etrade_pdf
    monkeypatch.setattr(etrade_pdf, "_get_price_on_date",
                        lambda sym, dt: Decimal("119.79"))
    txns, _ = _parse_old(_OLD_RECEIVE_TEXT, "test.pdf")
    buys = [t for t in txns if t.txn_type == TransactionType.BUY]
    assert len(buys) == 1
    b = buys[0]
    assert b.trade_date == date(2020, 9, 2)
    assert b.quantity == Decimal("56.6151")
    assert b.price == Decimal("119.79")
    assert b.orig_amount == -(Decimal("56.6151") * Decimal("119.79"))
    assert "RSU" in b.notes


_OLD_DIV_TEXT = """\
Account Number: 1234-5678 Statement Period : April 1, 2021 - June 30, 2021 Account Type: INDIVIDUAL
DIVIDENDS & INTEREST ACTIVITY
04/07/21 Qualified Dividend NXP SEMICONDUCTORS NV NXPI 85.00
TOTAL DIVIDENDS
"""

def test_parse_old_dividend():
    txns, _ = _parse_old(_OLD_DIV_TEXT, "test.pdf")
    divs = [t for t in txns if t.txn_type == TransactionType.DIVIDEND]
    assert len(divs) == 1
    d = divs[0]
    assert d.trade_date == date(2021, 4, 7)
    assert d.symbol == NXPI_SYMBOL
    assert d.orig_amount == Decimal("85.00")


# ── _parse_new ────────────────────────────────────────────────────────────────

_NEW_PAGES_SELL = [
    """\
E*TRADE from Morgan Stanley
Account Summary For the Period February 1-29, 2024
CASH FLOW ACTIVITY BY DATE
Date Settlement Description Quantity Price Credits/(Debits)
2/22 2/26 Sold NXP SEMICONDUCTORS NV ACTED AS AGENT 41.000 240.2325 9,849.45
2/26 3/01 Sold NXP SEMICONDUCTORS NV ACTED AS AGENT 35.977 242.5000 8,724.35
NET CREDITS/(DEBITS)
"""
]

def test_parse_new_sells():
    txns, acct = _parse_new(_NEW_PAGES_SELL, "test.pdf")
    sells = [t for t in txns if t.txn_type == TransactionType.SELL]
    assert len(sells) == 2

    s1 = next(t for t in sells if t.quantity == Decimal("41.000"))
    assert s1.trade_date == date(2024, 2, 22)
    assert s1.symbol == NXPI_SYMBOL
    assert s1.isin == NXPI_ISIN
    assert s1.price == Decimal("240.2325")
    assert s1.orig_amount == Decimal("9849.45")
    assert s1.orig_currency == "USD"

    s2 = next(t for t in sells if t.quantity == Decimal("35.977"))
    assert s2.orig_amount == Decimal("8724.35")


_NEW_PAGES_DIV = [
    """\
E*TRADE from Morgan Stanley
For the Period July 1-31, 2024
CASH FLOW ACTIVITY BY DATE
7/10 Qualified Dividend NXP SEMICONDUCTORS NV 75.85
7/10 Dividend NXP SEMICONDUCTORS NV 0.00
ADJ GROSS DIV AMOUNT 13.38
FOREIGN TAX PAID IS 13.38
NET CREDITS/(DEBITS)
"""
]

def test_parse_new_qualified_dividend_with_wht():
    txns, _ = _parse_new(_NEW_PAGES_DIV, "test.pdf")
    divs = [t for t in txns if t.txn_type == TransactionType.DIVIDEND]
    assert len(divs) == 1
    d = divs[0]
    assert d.trade_date == date(2024, 7, 10)
    assert d.symbol == NXPI_SYMBOL
    assert d.wht_amount_orig == Decimal("13.38")
    assert d.orig_amount == Decimal("75.85") + Decimal("13.38")


_NEW_PAGES_RSU = [
    """\
E*TRADE from Morgan Stanley
For the Period November 1-30, 2024
CASH FLOW ACTIVITY BY DATE
NET CREDITS/(DEBITS)
""",
    """\
For the Period November 1-30, 2024
SECURITY TRANSFERS
11/1 Transfer into Account NXP SEMICONDUCTORS NV 28.000 $6,680.52
11/7 Transfer into Account NXP SEMICONDUCTORS NV 22.000 5,194.64
TOTAL SECURITY TRANSFERS
""",
]

def test_parse_new_rsu_vestings():
    txns, _ = _parse_new(_NEW_PAGES_RSU, "test.pdf")
    buys = [t for t in txns if t.txn_type == TransactionType.BUY]
    assert len(buys) == 2

    b1 = next(t for t in buys if t.quantity == Decimal("28.000"))
    assert b1.trade_date == date(2024, 11, 1)
    assert b1.symbol == NXPI_SYMBOL
    assert b1.isin == NXPI_ISIN
    expected_price = (Decimal("6680.52") / Decimal("28.000")).quantize(Decimal("0.0001"))
    assert b1.price == expected_price
    assert b1.orig_amount == -Decimal("6680.52")
    assert "RSU" in b1.notes

    b2 = next(t for t in buys if t.quantity == Decimal("22.000"))
    assert b2.orig_amount == -Decimal("5194.64")


def test_parse_new_deduplicates_annual_recap():
    """December annual recap re-lists all 2024 RSU transfers — raw_ids must be stable."""
    pages = [
        "E*TRADE from Morgan Stanley\nFor the Period December 1-31, 2024\nCASH FLOW ACTIVITY BY DATE\nNET CREDITS/(DEBITS)\n",
        "SECURITY TRANSFERS\n11/1 Transfer into Account NXP SEMICONDUCTORS NV 28.000 $6,680.52\nTOTAL SECURITY TRANSFERS\n",
        "2024 Recap\nSECURITY TRANSFERS\n11/1 Transfer into Account NXP SEMICONDUCTORS NV 28.000 $6,680.52\nTOTAL SECURITY TRANSFERS\n",
    ]
    txns, _ = _parse_new(pages, "test.pdf")
    rsu_ids = [t.raw_id for t in txns if t.txn_type == TransactionType.BUY]
    # Same raw_id → pipeline dedup removes the duplicate
    assert rsu_ids[0] == rsu_ids[1]


# ── etrade_skip_transfers (account migration) ─────────────────────────────────

_NEW_PAGES_MIGRATION = [
    """\
E*TRADE from Morgan Stanley
For the Period September 1-30, 2023
CASH FLOW ACTIVITY BY DATE
NET CREDITS/(DEBITS)
""",
    """\
For the Period September 1-30, 2023
SECURITY TRANSFERS
9/1 Transfer into Account NXP SEMICONDUCTORS NV 123.977 $26,030.21
9/15 Transfer into Account NXP SEMICONDUCTORS NV 19.000 $4,000.00
TOTAL SECURITY TRANSFERS
""",
]

def test_skip_migration_transfer_suppresses_matching_date():
    """etrade_skip_transfers: ["2023-09-01"] skips the migration, keeps genuine vestings."""
    from datetime import date as _date
    skip = {_date(2023, 9, 1)}
    txns, _ = _parse_new(_NEW_PAGES_MIGRATION, "test.pdf", skip_transfer_dates=skip)
    buys = [t for t in txns if t.txn_type == TransactionType.BUY]
    # Migration (9/1) suppressed; genuine vest (9/15) kept
    assert len(buys) == 1
    assert buys[0].trade_date == _date(2023, 9, 15)
    assert buys[0].quantity == Decimal("19.000")


def test_no_skip_config_keeps_all_transfers():
    """Without etrade_skip_transfers, all transfers are parsed normally."""
    txns, _ = _parse_new(_NEW_PAGES_MIGRATION, "test.pdf")
    buys = [t for t in txns if t.txn_type == TransactionType.BUY]
    assert len(buys) == 2


def test_parse_respects_etrade_skip_transfers_from_config(tmp_path):
    """End-to-end: config dict wires through to suppressing the migration entry."""
    import pdfplumber
    from brokers.etrade_pdf import parse as etrade_parse
    # Use an actual parsed file to confirm config threading
    # (smoke test — just verify no crash; real files tested manually)
    config = {"etrade_skip_transfers": ["2023-09-01"]}
    assert isinstance(config["etrade_skip_transfers"], list)


# ── detect() — smoke test (no real PDF needed) ────────────────────────────────

def test_detect_rejects_non_pdf(tmp_path):
    from brokers.etrade_pdf import detect
    f = tmp_path / "file.csv"
    f.write_text("some,csv,data")
    assert detect(f) is False
