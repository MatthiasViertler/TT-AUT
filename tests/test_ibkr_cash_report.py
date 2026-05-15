"""Tests for parse_ibkr_cash_report in brokers/ib_csv.py."""

import textwrap
from decimal import Decimal
from pathlib import Path

from brokers.ib_csv import parse_ibkr_cash_report


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


# ── BOS/EOS format ─────────────────────────────────────────────────────────────

BOS_EOS_WITH_CASH = """\
"BOF","U22222222","ACTIVITY","20251231","20251231","20251231"
"BOS","CRTT","Cash Report; trade date basis"
"CurrencyPrimary","EndingCash","EndingCashSecurities","EndingCashCommodities"
"BASE_SUMMARY","82830.652878898","82830.652878898","0"
"DKK","1722.8","1722.8","0"
"EUR","29106.053595","29106.053595","0"
"GBP","1134.359993086","1134.359993086","0"
"USD","60904.32839153","60904.32839153","0"
"EOS","CRTT","5","175698.194858514"
"EOF","U22222222"
"""

BOS_EOS_NO_CASH = """\
"BOF","U22222222","ACTIVITY","20251231","20251231","20251231"
"BOS","TRNT","Trades"
"Symbol","AssetClass","Buy/Sell","Quantity","TradePrice","Proceeds","CurrencyPrimary"
"AAPL","STK","SELL","100","150.00","15000","USD"
"EOS","TRNT","1","15000"
"EOF","U22222222"
"""


def test_bos_eos_parses_base_summary(tmp_path):
    f = _write(tmp_path, "flex.csv", BOS_EOS_WITH_CASH)
    result = parse_ibkr_cash_report(f)
    assert result == Decimal("82830.652878898")


def test_bos_eos_returns_none_when_no_crtt(tmp_path):
    f = _write(tmp_path, "flex.csv", BOS_EOS_NO_CASH)
    assert parse_ibkr_cash_report(f) is None


def test_nonexistent_file_returns_none(tmp_path):
    f = tmp_path / "missing.csv"
    # parse_ibkr_cash_report will fail to open; should propagate or handle gracefully
    # In practice the pipeline only calls it for paths that exist — but test defensively
    try:
        result = parse_ibkr_cash_report(f)
        # If it doesn't raise, it must return None
        assert result is None
    except (FileNotFoundError, OSError):
        pass  # also acceptable — file doesn't exist


# ── HEADER/DATA Flex Query format ──────────────────────────────────────────────

HEADER_DATA_WITH_CASH = """\
BOF,U22222222,ACTIVITY,20251231,20251231,20251231
HEADER,CRTT,CurrencyPrimary,EndingCash,EndingCashSecurities,EndingCashCommodities
DATA,CRTT,BASE_SUMMARY,55000.00,55000.00,0
DATA,CRTT,USD,40000.00,40000.00,0
DATA,CRTT,EUR,15000.00,15000.00,0
EOF,U22222222
"""


def test_header_data_parses_base_summary(tmp_path):
    f = _write(tmp_path, "flex_hd.csv", HEADER_DATA_WITH_CASH)
    result = parse_ibkr_cash_report(f)
    assert result == Decimal("55000.00")


# ── Classic Activity Statement format ─────────────────────────────────────────

CLASSIC_WITH_CASH = """\
Statement,Header,Field Name,Field Value
Cash Report,Header,CurrencyPrimary,EndingCash,EndingCashSecurities,EndingCashCommodities
Cash Report,Data,BASE_SUMMARY,12345.67,12345.67,0
Cash Report,Data,USD,10000.00,10000.00,0
Cash Report,Data,EUR,2345.67,2345.67,0
"""


def test_classic_parses_base_summary(tmp_path):
    f = _write(tmp_path, "classic.csv", CLASSIC_WITH_CASH)
    result = parse_ibkr_cash_report(f)
    assert result == Decimal("12345.67")


# ── Edge cases ─────────────────────────────────────────────────────────────────

BOS_EOS_ZERO_CASH = """\
"BOF","U22222222"
"BOS","CRTT","Cash Report; trade date basis"
"CurrencyPrimary","EndingCash","EndingCashSecurities","EndingCashCommodities"
"BASE_SUMMARY","0","0","0"
"EUR","0","0","0"
"EOS","CRTT","2","0"
"""


def test_zero_base_summary_returns_none(tmp_path):
    """Zero cash balance → None (treated as unavailable, not a real value)."""
    f = _write(tmp_path, "zero.csv", BOS_EOS_ZERO_CASH)
    assert parse_ibkr_cash_report(f) is None


BOS_EOS_NO_BASE_SUMMARY = """\
"BOF","U22222222"
"BOS","CRTT","Cash Report; trade date basis"
"CurrencyPrimary","EndingCash","EndingCashSecurities","EndingCashCommodities"
"USD","60000.00","60000.00","0"
"EUR","20000.00","20000.00","0"
"EOS","CRTT","2","80000.00"
"""


def test_no_base_summary_row_returns_none(tmp_path):
    """If BASE_SUMMARY row is absent, return None (don't guess from individual currencies)."""
    f = _write(tmp_path, "no_base.csv", BOS_EOS_NO_BASE_SUMMARY)
    assert parse_ibkr_cash_report(f) is None
