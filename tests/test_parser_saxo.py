"""
Tests for the SAXO xlsx broker parser.

All test data is fully synthetic — no real account IDs, ISINs, amounts, or
personal data from the actual SAXO exports.
"""
import io
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

# Skip entire module if openpyxl is not installed
openpyxl = pytest.importorskip("openpyxl")

from brokers.saxo_xlsx import (
    detect,
    get_account_id,
    parse,
    _parse_date,
    _parse_ccy_string,
    _extract_ccy,
)
from core.models import TransactionType, AssetClass, Domicile


# ── Helpers to build synthetic xlsx files in memory ──────────────────────────

_AGG_HEADERS = [
    "Date", "Booking Account ID", "Account Currency", "Client Currency",
    "Amount Type Name", "Affects Balance", "Asset type",
    "Unified Instrument Code (UIC)", "Underlying Instrument SubType",
    "Instrument Symbol", "Instrument Description",
    "Instrument SubType", "Underlying Instrument AssetType",
    "Underlying Instrument Description", "Underlying Instrument Symbol",
    "Underlying Instrument Uic", "Amount", "Amount Account Currency",
    "Amount Client Currency", "Cost type", "Cost subtype",
]

_DIV_HEADERS = [
    "Account ID", "IBAN", "Client Currency",
    "Instrument", "Instrument Symbol", "Event",
    "Posting Date", "Pay Date", "Holding", "Position type",
    "Dividend unit", "Conversion Rate", "Dividend amount",
    "Withholding tax percent", "Withholding tax amount",
    "Residential tax percent", "Residential tax amount",
    "Fee amount", "Total Tax (EUR)", "Booked Amount (EUR)",
]


def _build_agg_xlsx(rows: list[list]) -> Path:
    """Build a synthetic AggregatedAmounts xlsx and return a tmp Path-like object."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Cash Movements"
    ws.append(_AGG_HEADERS)
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    # Write to a temp file using tmp_path (injected via fixture workaround below)
    # We return the buffer so the caller can write it
    return buf


def _build_div_xlsx(rows: list[list]) -> io.BytesIO:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Share Dividends"
    ws.append(_DIV_HEADERS)
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def _write_agg(tmp_path, rows, account="99999999", year="2025"):
    name = f"AggregatedAmounts_{account}_{year}-01-01_{year}-12-31.xlsx"
    p = tmp_path / name
    wb = openpyxl.Workbook()
    ws = wb.active; ws.title = "Cash Movements"
    ws.append(_AGG_HEADERS)
    for r in rows:
        ws.append(r)
    wb.save(p)
    return p


def _write_div(tmp_path, rows, account="99999999", year="2025"):
    name = f"ShareDividends_{account}_{year}-01-01_{year}-12-31.xlsx"
    p = tmp_path / name
    wb = openpyxl.Workbook()
    ws = wb.active; ws.title = "Share Dividends"
    ws.append(_DIV_HEADERS)
    for r in rows:
        ws.append(r)
    wb.save(p)
    return p


def _agg_row(date_str, amt_type, symbol, description, uic, amount_eur,
             asset_type="Stock", subtype="None", acct_ccy="USD"):
    """Build one Cash Movements row (EUR client account)."""
    return [
        date_str, "TESTACCT", acct_ccy, "EUR",
        amt_type, "Yes", asset_type, uic, subtype,
        symbol, description, subtype,
        asset_type, description, symbol, uic,
        amount_eur, amount_eur, amount_eur, " ", " ",
    ]


def _div_row(symbol, description, pay_date, holding,
             div_str, wht_pct, wht_str, fee_str="USD 0.00",
             booked_eur=0.0, event="Cash dividend"):
    """Build one ShareDividends row."""
    return [
        "TESTACCT", "XX0000000000000000", "EUR",
        description, symbol, event,
        pay_date, pay_date, holding, "Settled",
        "USD 1.000000", 0.95,
        div_str, wht_pct, wht_str,
        0, "USD 0.00", fee_str,
        booked_eur, booked_eur,
    ]


# ── detect() ─────────────────────────────────────────────────────────────────

def test_detect_aggregated_amounts(tmp_path):
    p = tmp_path / "AggregatedAmounts_99999999_2025-01-01_2025-12-31.xlsx"
    p.write_bytes(b"")
    assert detect(p)


def test_detect_share_dividends(tmp_path):
    p = tmp_path / "ShareDividends_99999999_2025-01-01_2025-12-31.xlsx"
    p.write_bytes(b"")
    assert detect(p)


def test_detect_rejects_non_saxo(tmp_path):
    for name in ["activity_2025.csv", "report.xlsx", "ShareDividends_99.csv"]:
        p = tmp_path / name
        p.write_bytes(b"")
        assert not detect(p), f"should not detect: {name}"


# ── get_account_id() ─────────────────────────────────────────────────────────

def test_get_account_id_from_agg_filename(tmp_path):
    p = tmp_path / "AggregatedAmounts_12345678_2024-01-01_2024-12-31.xlsx"
    assert get_account_id(p) == "12345678"


def test_get_account_id_from_div_filename(tmp_path):
    p = tmp_path / "ShareDividends_87654321_2025-01-01_2025-12-31.xlsx"
    assert get_account_id(p) == "87654321"


# ── _parse_date() ─────────────────────────────────────────────────────────────

def test_parse_date_dd_mm_yyyy():
    assert _parse_date("21-03-2024") == date(2024, 3, 21)


def test_parse_date_datetime_object():
    from datetime import datetime
    assert _parse_date(datetime(2024, 6, 15)) == date(2024, 6, 15)


def test_parse_date_iso():
    assert _parse_date("2025-07-04") == date(2025, 7, 4)


def test_parse_date_none():
    assert _parse_date(None) is None


# ── _parse_ccy_string() ───────────────────────────────────────────────────────

@pytest.mark.parametrize("s,expected", [
    ("USD 23.00",   Decimal("23.00")),
    ("-USD 3.45",   Decimal("-3.45")),
    ("USD 0.00",    Decimal("0.00")),
    ("EUR 100.50",  Decimal("100.50")),
    ("",            Decimal("0")),
    ("None",        Decimal("0")),
])
def test_parse_ccy_string(s, expected):
    assert _parse_ccy_string(s) == expected


def test_extract_ccy():
    assert _extract_ccy("USD 23.00") == "USD"
    assert _extract_ccy("-EUR 5.00") == "EUR"
    assert _extract_ccy("") is None


# ── AggregatedAmounts — trades ────────────────────────────────────────────────

def test_agg_sell_is_positive_amount(tmp_path):
    """Positive Share Amount → SELL."""
    rows = [_agg_row("15-03-2025", "Share Amount", "XYZ:xnas", "XYZ Corp.", 999, 1500.00)]
    p = _write_agg(tmp_path, rows)
    txns, _ = parse(p, {})
    assert len(txns) == 1
    t = txns[0]
    assert t.txn_type == TransactionType.SELL
    assert t.orig_amount == Decimal("1500.00")
    assert t.symbol == "XYZ"


def test_agg_buy_is_negative_amount(tmp_path):
    """Negative Share Amount → BUY."""
    rows = [_agg_row("15-03-2025", "Share Amount", "ABC:xnys", "ABC Inc.", 888, -2000.00)]
    p = _write_agg(tmp_path, rows)
    txns, _ = parse(p, {})
    assert len(txns) == 1
    assert txns[0].txn_type == TransactionType.BUY
    assert txns[0].orig_amount == Decimal("-2000.00")


def test_agg_commission_added_to_trade(tmp_path):
    """Commission row for same (date, UIC) is added to trade's commission field."""
    rows = [
        _agg_row("10-04-2025", "Share Amount",  "TGT:xnys", "Target Corp.", 555, -1000.00),
        _agg_row("10-04-2025", "Commission",     "TGT:xnys", "Target Corp.", 555, -1.50),
        _agg_row("10-04-2025", "Exchange Fee",   "TGT:xnys", "Target Corp.", 555, -0.03),
    ]
    p = _write_agg(tmp_path, rows)
    txns, _ = parse(p, {})
    assert len(txns) == 1
    assert txns[0].commission == Decimal("1.53")


def test_agg_trade_qty_is_one(tmp_path):
    """SAXO exports have no quantity — parser uses 1 as placeholder."""
    rows = [_agg_row("01-05-2025", "Share Amount", "DEMO:xnas", "Demo Inc.", 777, -500.00)]
    p = _write_agg(tmp_path, rows)
    txns, _ = parse(p, {})
    assert txns[0].quantity == Decimal("1")


def test_agg_exchange_code_sets_country(tmp_path):
    """Exchange suffix → correct country code."""
    cases = [
        ("AA:xnas", "AA Corp.", 1, "US"),
        ("BB:xhkg", "BB Ltd.",  2, "CN"),
        ("CC:xlon", "CC Plc.",  3, "GB"),
        ("DD:xcse", "DD A/S",   4, "DK"),
    ]
    for sym, desc, uic, expected_country in cases:
        rows = [_agg_row("01-06-2025", "Share Amount", sym, desc, uic, 100.0)]
        p = _write_agg(tmp_path, rows, account=str(uic))
        txns, _ = parse(p, {})
        assert txns[0].country_code == expected_country, f"{sym} → {txns[0].country_code}"


def test_agg_custody_fee_skipped(tmp_path):
    """Custody fees are not tax events and must not appear in output."""
    rows = [
        _agg_row("01-04-2025", "Custody Fee", None, None, 0, -15.00, "Cash"),
        _agg_row("01-04-2025", "VAT",         None, None, 0,  -3.75, "Cash"),
    ]
    p = _write_agg(tmp_path, rows)
    txns, _ = parse(p, {})
    assert txns == []


def test_agg_account_id_from_filename(tmp_path):
    rows = [_agg_row("01-01-2025", "Share Amount", "ZZ:xnas", "ZZ Inc.", 321, 200.0)]
    p = _write_agg(tmp_path, rows, account="55551234")
    _, acct = parse(p, {})
    assert acct == "55551234"


# ── AggregatedAmounts — dividends ─────────────────────────────────────────────

def test_agg_dividend_with_wht(tmp_path):
    rows = [
        _agg_row("15-04-2025", "Corporate Actions - Cash Dividends",
                 "KO:xnys", "Coca-Cola Co.", 307, 30.00),
        _agg_row("15-04-2025", "Corporate Actions - Withholding Tax",
                 "KO:xnys", "Coca-Cola Co.", 307, -4.50),
    ]
    p = _write_agg(tmp_path, rows)
    txns, _ = parse(p, {})
    assert len(txns) == 1
    t = txns[0]
    assert t.txn_type == TransactionType.DIVIDEND
    assert t.orig_amount == Decimal("30.00")
    assert t.wht_amount_orig == Decimal("4.50")
    assert t.symbol == "KO"


def test_agg_dividend_no_wht(tmp_path):
    rows = [_agg_row("20-05-2025", "Corporate Actions - Cash Dividends",
                     "BTI:xnys", "BAT Plc.", 888, 80.00)]
    p = _write_agg(tmp_path, rows)
    txns, _ = parse(p, {})
    assert txns[0].wht_amount_orig == Decimal("0")


def test_agg_sgd_account_uses_sgd_currency(tmp_path):
    """2020-style SG account: client currency = SGD → orig_currency = SGD."""
    # Build rows where Account Currency = Client Currency = SGD
    def sgd_row(amt_type, uic, amount):
        return [
            "2020-03-01", "SGACCT", "SGD", "SGD",
            amt_type, "Yes", "Stock", uic, "None",
            None, "Test Corp.", "None",
            "Stock", "Test Corp.", None, uic,
            amount, amount, amount, " ", " ",
        ]
    rows = [sgd_row("Share Amount", 9999, -5000.0)]
    p = _write_agg(tmp_path, rows, account="SG12345")
    txns, _ = parse(p, {})
    assert len(txns) == 1
    assert txns[0].orig_currency == "SGD"


def test_agg_2020_uic_symbol_fallback(tmp_path):
    """When Instrument Symbol is None (2020 SG format), symbol = UIC{n}."""
    def sgd_row(uic, amount):
        return [
            "2020-01-09", "SGACCT", "SGD", "SGD",
            "Share Amount", "Yes", "Stock", uic, "None",
            None, "Advanced Micro Devices Inc.", "None",
            "Stock", "Advanced Micro Devices Inc.", None, uic,
            amount, amount, amount, " ", " ",
        ]
    rows = [sgd_row(1422226, -4000.0)]
    p = _write_agg(tmp_path, rows, account="SG12345")
    txns, _ = parse(p, {})
    assert txns[0].symbol == "UIC1422226"


# ── ShareDividends ────────────────────────────────────────────────────────────

def test_div_basic_cash_dividend(tmp_path):
    rows = [_div_row("HD:xnys", "Home Depot Inc.", date(2025, 3, 20), 8,
                     "USD 18.00", 0.15, "-USD 2.70", booked_eur=14.50)]
    p = _write_div(tmp_path, rows)
    txns, _ = parse(p, {})
    assert len(txns) == 1
    t = txns[0]
    assert t.txn_type == TransactionType.DIVIDEND
    assert t.symbol == "HD"
    assert t.orig_amount == Decimal("18.00")
    assert t.wht_amount_orig == Decimal("2.70")
    assert t.orig_currency == "USD"
    assert t.trade_date == date(2025, 3, 20)


def test_div_split_reinvestment_rows_merged(tmp_path):
    """Two rows for same (symbol, pay_date, holding) are combined."""
    rows = [
        # WHT-only row
        _div_row("ARCC:xnas", "Ares Capital Corp.", date(2025, 3, 31), 110,
                 "USD 0.00", 0.15, "-USD 8.00", event="Dividend reinvestment"),
        # Gross-only row
        _div_row("ARCC:xnas", "Ares Capital Corp.", date(2025, 3, 31), 110,
                 "USD 9.50", 0,    "USD 0.00",  event="Dividend reinvestment"),
    ]
    p = _write_div(tmp_path, rows)
    txns, _ = parse(p, {})
    assert len(txns) == 1
    t = txns[0]
    assert t.orig_amount  == Decimal("9.50")
    assert t.wht_amount_orig == Decimal("8.00")


def test_div_adr_fee_in_commission(tmp_path):
    """ADR/depository fees go into commission, not wht_amount_orig."""
    rows = [_div_row("BTI:xnys", "British American Tobacco - ADR",
                     date(2025, 2, 7), 160,
                     "USD 116.87", 0, "USD 0.00",
                     fee_str="-USD 1.60", booked_eur=111.50)]
    p = _write_div(tmp_path, rows)
    txns, _ = parse(p, {})
    t = txns[0]
    assert t.wht_amount_orig == Decimal("0")
    assert t.commission == Decimal("1.60")


def test_div_zero_gross_zero_wht_skipped(tmp_path):
    """Rows with no financial content are skipped."""
    rows = [_div_row("XX:xnas", "Unknown Corp.", date(2025, 5, 1), 10,
                     "USD 0.00", 0, "USD 0.00")]
    p = _write_div(tmp_path, rows)
    txns, _ = parse(p, {})
    assert txns == []


def test_div_domicile_is_foreign(tmp_path):
    rows = [_div_row("KO:xnys", "Coca-Cola Co.", date(2025, 4, 1), 30,
                     "USD 30.00", 0.15, "-USD 4.50")]
    p = _write_div(tmp_path, rows)
    txns, _ = parse(p, {})
    assert txns[0].domicile == Domicile.FOREIGN


def test_div_sorted_by_date(tmp_path):
    """Output is chronological, not alphabetical by symbol."""
    rows = [
        _div_row("ZZ:xnas", "ZZ Corp.", date(2025, 1, 10), 10, "USD 5.00", 0, "USD 0.00"),
        _div_row("AA:xnas", "AA Corp.", date(2025, 3, 15), 10, "USD 10.00", 0, "USD 0.00"),
        _div_row("MM:xnas", "MM Corp.", date(2025, 2, 20), 10, "USD 8.00",  0, "USD 0.00"),
    ]
    p = _write_div(tmp_path, rows)
    txns, _ = parse(p, {})
    dates = [t.trade_date for t in txns]
    assert dates == sorted(dates)


def test_div_multiple_payments_same_symbol(tmp_path):
    """Same symbol with different pay dates → separate transactions."""
    rows = [
        _div_row("KO:xnys", "Coca-Cola Co.", date(2025, 1, 1),  10, "USD 5.00", 0.15, "-USD 0.75"),
        _div_row("KO:xnys", "Coca-Cola Co.", date(2025, 4, 1),  10, "USD 5.10", 0.15, "-USD 0.77"),
        _div_row("KO:xnys", "Coca-Cola Co.", date(2025, 7, 1),  12, "USD 5.10", 0.15, "-USD 0.77"),
        _div_row("KO:xnys", "Coca-Cola Co.", date(2025, 10, 1), 12, "USD 5.25", 0.15, "-USD 0.79"),
    ]
    p = _write_div(tmp_path, rows)
    txns, _ = parse(p, {})
    assert len(txns) == 4


# ── broker = "saxo" label ─────────────────────────────────────────────────────

def test_broker_label(tmp_path):
    rows = [_agg_row("10-06-2025", "Share Amount", "TEST:xnas", "Test Corp.", 1, 100.0)]
    p = _write_agg(tmp_path, rows)
    txns, _ = parse(p, {})
    assert txns[0].broker == "saxo"
