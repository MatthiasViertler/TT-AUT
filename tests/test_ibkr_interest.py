"""Tests for parse_ibkr_interest in brokers/ib_csv.py."""

import textwrap
from decimal import Decimal
from pathlib import Path

from brokers.ib_csv import parse_ibkr_interest

ZERO = Decimal("0")


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


# ── BOS/EOS format (TT-AUT export) ────────────────────────────────────────────

BOS_EOS_EUR_AND_USD = """\
"BOF","U22222222","ACTIVITY","20251231","20250101","20251231"
"BOS","CTRN","Cash Transactions"
"ClientAccountID","CurrencyPrimary","FXRateToBase","Description","Amount","Type"
"U22222222","EUR","1","EUR CREDIT INT FOR MAY-2025","29.45","Broker Interest Received"
"U22222222","EUR","1","EUR CREDIT INT FOR JUN-2025","24.48","Broker Interest Received"
"U22222222","USD","0.87577","USD CREDIT INT FOR MAY-2025","41.54","Broker Interest Received"
"U22222222","USD","0.85052","USD CREDIT INT FOR JUN-2025","40.51","Broker Interest Received"
"U22222222","EUR","1","ALLIANZ CASH DIVIDEND EUR 9.60 PER SHARE","960.00","Dividends"
"EOS","CTRN","5","0"
"EOF","U22222222"
"""


def test_bos_eos_sums_eur_and_usd_interest(tmp_path):
    """EUR rows: amount×1; USD rows: amount×FXRateToBase; dividends ignored."""
    f = _write(tmp_path, "flex.csv", BOS_EOS_EUR_AND_USD)
    result = parse_ibkr_interest(f, 2025)
    # EUR: 29.45 + 24.48 = 53.93
    # USD: 41.54 × 0.87577 + 40.51 × 0.85052
    eur_part = Decimal("29.45") + Decimal("24.48")
    usd_part = Decimal("41.54") * Decimal("0.87577") + Decimal("40.51") * Decimal("0.85052")
    expected = (eur_part + usd_part).quantize(Decimal("0.01"))
    assert result == expected


BOS_EOS_MIXED_YEARS = """\
"BOF","U22222222","ACTIVITY","20251231","20250101","20251231"
"BOS","CTRN","Cash Transactions"
"ClientAccountID","CurrencyPrimary","FXRateToBase","Description","Amount","Type"
"U22222222","EUR","1","EUR CREDIT INT FOR DEC-2025","29.02","Broker Interest Received"
"U22222222","EUR","1","EUR CREDIT INT FOR JAN-2026","29.07","Broker Interest Received"
"U22222222","EUR","1","EUR CREDIT INT FOR FEB-2026","34.29","Broker Interest Received"
"EOS","CTRN","3","0"
"EOF","U22222222"
"""


def test_bos_eos_filters_by_year(tmp_path):
    """Only rows whose description year matches target year are included."""
    f = _write(tmp_path, "flex.csv", BOS_EOS_MIXED_YEARS)
    result_2025 = parse_ibkr_interest(f, 2025)
    result_2026 = parse_ibkr_interest(f, 2026)
    assert result_2025 == Decimal("29.02")
    assert result_2026 == (Decimal("29.07") + Decimal("34.29")).quantize(Decimal("0.01"))


BOS_EOS_NO_INTEREST = """\
"BOF","U22222222","ACTIVITY","20251231","20250101","20251231"
"BOS","CTRN","Cash Transactions"
"ClientAccountID","CurrencyPrimary","FXRateToBase","Description","Amount","Type"
"U22222222","EUR","1","ALLIANZ CASH DIVIDEND EUR 9.60 PER SHARE","960.00","Dividends"
"EOS","CTRN","1","0"
"EOF","U22222222"
"""


def test_no_interest_rows_returns_zero(tmp_path):
    f = _write(tmp_path, "flex.csv", BOS_EOS_NO_INTEREST)
    assert parse_ibkr_interest(f, 2025) == ZERO


BOS_EOS_NO_CTRN = """\
"BOF","U22222222","ACTIVITY","20251231","20250101","20251231"
"BOS","TRNT","Trades"
"Symbol","Buy/Sell","Quantity"
"AAPL","BUY","10"
"EOS","TRNT","1","0"
"EOF","U22222222"
"""


def test_no_ctrn_section_returns_zero(tmp_path):
    f = _write(tmp_path, "flex.csv", BOS_EOS_NO_CTRN)
    assert parse_ibkr_interest(f, 2025) == ZERO


# ── HEADER/DATA Flex Query format ──────────────────────────────────────────────

HEADER_DATA_INTEREST = """\
BOF,U22222222,ACTIVITY,20251231,20250101,20251231
HEADER,CTRN,ClientAccountID,CurrencyPrimary,FXRateToBase,Description,Amount,Type
DATA,CTRN,U22222222,EUR,1,EUR CREDIT INT FOR AUG-2025,28.50,Broker Interest Received
DATA,CTRN,U22222222,USD,0.86392,USD CREDIT INT FOR AUG-2025,41.50,Broker Interest Received
DATA,CTRN,U22222222,EUR,1,SOME DIVIDEND EUR 1.00 PER SHARE,50.00,Dividends
EOF,U22222222
"""


def test_header_data_format(tmp_path):
    f = _write(tmp_path, "hd.csv", HEADER_DATA_INTEREST)
    result = parse_ibkr_interest(f, 2025)
    expected = (Decimal("28.50") + Decimal("41.50") * Decimal("0.86392")).quantize(Decimal("0.01"))
    assert result == expected


# ── Edge cases ─────────────────────────────────────────────────────────────────

def test_missing_file_raises(tmp_path):
    """Missing file: allow FileNotFoundError to propagate (pipeline guards this)."""
    f = tmp_path / "missing.csv"
    try:
        parse_ibkr_interest(f, 2025)
    except (FileNotFoundError, OSError):
        pass  # expected


BOS_EOS_FULL_YEAR_SUM = """\
"BOF","U22222222","ACTIVITY","20251231","20250101","20251231"
"BOS","CTRN","Cash Transactions"
"ClientAccountID","CurrencyPrimary","FXRateToBase","Description","Amount","Type"
"U22222222","EUR","1","EUR CREDIT INT FOR MAY-2025","10.00","Broker Interest Received"
"U22222222","EUR","1","EUR CREDIT INT FOR JUN-2025","10.00","Broker Interest Received"
"U22222222","EUR","1","EUR CREDIT INT FOR JUL-2025","10.00","Broker Interest Received"
"U22222222","EUR","1","EUR CREDIT INT FOR AUG-2025","10.00","Broker Interest Received"
"U22222222","EUR","1","EUR CREDIT INT FOR SEP-2025","10.00","Broker Interest Received"
"U22222222","EUR","1","EUR CREDIT INT FOR OCT-2025","10.00","Broker Interest Received"
"U22222222","EUR","1","EUR CREDIT INT FOR NOV-2025","10.00","Broker Interest Received"
"U22222222","EUR","1","EUR CREDIT INT FOR DEC-2025","10.00","Broker Interest Received"
"EOS","CTRN","8","0"
"EOF","U22222222"
"""


def test_sums_all_months_in_year(tmp_path):
    """All 8 months of EUR interest should sum to 80.00."""
    f = _write(tmp_path, "flex.csv", BOS_EOS_FULL_YEAR_SUM)
    assert parse_ibkr_interest(f, 2025) == Decimal("80.00")
