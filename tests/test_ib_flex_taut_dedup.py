"""
Tests for TT-AUT / Flex CSV deduplication logic.

When a TT-AUT annual export and a Flex CSV overlap in date range, TT-AUT cash
transactions (dividends) use a different raw_id format than Flex cash transactions
— the existing dedup cannot catch the overlap. The pipeline suppresses TT-AUT
cash rows for any year already covered by a Flex file. Trades are safe in both
formats (same raw_id) and are always parsed.
"""
from datetime import date
from pathlib import Path

import pytest

from brokers.ib_csv import get_ib_file_info, parse
from core.models import TransactionType

from tests.conftest import FIXTURES


# ── get_ib_file_info ──────────────────────────────────────────────────────────

def test_taut_detected_as_not_flex(cfg):
    is_flex, from_date, to_date = get_ib_file_info(FIXTURES / "tt_aut_basic.csv")
    assert is_flex is False


def test_taut_to_date_extracted(cfg):
    _, from_date, to_date = get_ib_file_info(FIXTURES / "tt_aut_basic.csv")
    assert to_date == date(2025, 12, 31)


def test_taut_from_date_extracted(cfg):
    _, from_date, to_date = get_ib_file_info(FIXTURES / "tt_aut_basic.csv")
    assert from_date == date(2025, 1, 1)


def test_flex_detected_as_flex(cfg):
    is_flex, from_date, to_date = get_ib_file_info(FIXTURES / "header_data_basic.csv")
    assert is_flex is True


def test_flex_date_range_extracted(cfg):
    _, from_date, to_date = get_ib_file_info(FIXTURES / "header_data_basic.csv")
    assert from_date == date(2025, 1, 1)
    assert to_date == date(2025, 12, 31)


def test_nonexistent_file_returns_defaults():
    is_flex, from_date, to_date = get_ib_file_info(Path("/nonexistent/file.csv"))
    # Unreadable file defaults to is_flex=True so cash is never suppressed by mistake
    assert is_flex is True
    assert from_date is None
    assert to_date is None


# ── suppress_cash flag ────────────────────────────────────────────────────────

def test_suppress_cash_removes_dividends(cfg):
    txns, _ = parse(FIXTURES / "tt_aut_basic.csv", cfg, suppress_cash=True)
    divs = [t for t in txns if t.txn_type == TransactionType.DIVIDEND]
    assert len(divs) == 0


def test_suppress_cash_keeps_trades(cfg):
    """Trades must always be parsed regardless of suppress_cash."""
    txns_normal, _ = parse(FIXTURES / "tt_aut_basic.csv", cfg, suppress_cash=False)
    txns_suppressed, _ = parse(FIXTURES / "tt_aut_basic.csv", cfg, suppress_cash=True)
    trades_normal = [t for t in txns_normal
                     if t.txn_type in (TransactionType.BUY, TransactionType.SELL)]
    trades_suppressed = [t for t in txns_suppressed
                         if t.txn_type in (TransactionType.BUY, TransactionType.SELL)]
    assert trades_normal == trades_suppressed


def test_suppress_cash_false_includes_dividends(cfg):
    txns, _ = parse(FIXTURES / "tt_aut_basic.csv", cfg, suppress_cash=False)
    divs = [t for t in txns if t.txn_type == TransactionType.DIVIDEND]
    assert len(divs) > 0


def test_suppress_cash_flex_file(cfg):
    """suppress_cash also works on Flex-format files (used if ever needed)."""
    txns, _ = parse(FIXTURES / "header_data_basic.csv", cfg, suppress_cash=True)
    divs = [t for t in txns if t.txn_type == TransactionType.DIVIDEND]
    assert len(divs) == 0
