"""
Tests for the Flex Query HEADER/DATA format parser (Jessie's IBKR exports).
"""
from decimal import Decimal

from brokers.ib_csv import parse
from core.models import TransactionType

from tests.conftest import FIXTURES


def _parse(filename: str, cfg: dict):
    txns, acct = parse(FIXTURES / filename, cfg)
    return txns, acct


def test_account_id_extracted(cfg):
    _, acct = _parse("header_data_basic.csv", cfg)
    assert acct == "U88888888"


def test_fr_dividend_parsed(cfg):
    txns, _ = _parse("header_data_basic.csv", cfg)
    divs = [t for t in txns if t.symbol == "MC" and t.txn_type == TransactionType.DIVIDEND]
    assert len(divs) == 1
    assert divs[0].orig_amount == Decimal("75.00")


def test_fr_wht_matched(cfg):
    txns, _ = _parse("header_data_basic.csv", cfg)
    div = next(t for t in txns if t.symbol == "MC")
    assert div.wht_amount_orig == Decimal("18.75")
    assert div.country_code == "FR"


def test_us_dividend_parsed(cfg):
    txns, _ = _parse("header_data_basic.csv", cfg)
    divs = [t for t in txns if t.symbol == "MMM" and t.txn_type == TransactionType.DIVIDEND]
    assert len(divs) == 1
    assert divs[0].orig_amount == Decimal("14.60")
    assert divs[0].orig_currency == "USD"
    assert divs[0].country_code == "US"


def test_us_wht_matched(cfg):
    txns, _ = _parse("header_data_basic.csv", cfg)
    div = next(t for t in txns if t.symbol == "MMM")
    assert div.wht_amount_orig == Decimal("2.19")


def test_dividend_date_parsed(cfg):
    txns, _ = _parse("header_data_basic.csv", cfg)
    from datetime import date
    div = next(t for t in txns if t.symbol == "MC")
    assert div.trade_date == date(2025, 4, 28)
