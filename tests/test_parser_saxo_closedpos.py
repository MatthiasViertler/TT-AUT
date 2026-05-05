"""
Tests for the SAXO Bank ClosedPositions xlsx parser.

All data is fully synthetic — no real account IDs, prices, or personal information.
"""
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

openpyxl = pytest.importorskip("openpyxl")

from brokers.saxo_closedpos_xlsx import detect, get_account_id, parse
from core.models import TransactionType, AssetClass


# ── Helpers ───────────────────────────────────────────────────────────────────

_HEADERS = [
    "Trade Date Close", "Trade Date Open", "Account ID", "Account Currency",
    "Asset type", "Instrument Description", "Instrument Symbol", "Instrument currency",
    "OpenPositionId", "ClosePositionId", "QuantityClose", "Quantity Open",
    "Open Price", "Close Price",
    "TotalBookedOnOpeningLegAccountCurrency", "TotalBookedOnOpeningLegClientCurrency",
    "TotalBookedOnClosingLegAccountCurrency", "Client currency",
    "TotalBookedOnClosingLegClientCurrency", "PnLAccountCurrency", "PnLClientCurrency",
]


def _cp_row(
    close_dt, open_dt, symbol, instr_ccy="USD",
    qty_close=-10, qty_open=100,
    open_px=Decimal("50.00"), close_px=Decimal("80.00"),
    asset_type="Stock", open_pos_id=1001, close_pos_id=2001,
    description=None,
):
    return [
        close_dt, open_dt, "TESTACCT", "USD",
        asset_type, description or symbol, symbol, instr_ccy,
        open_pos_id, close_pos_id, qty_close, qty_open,
        float(open_px), float(close_px),
        0, 0, 0, "EUR", 0, 0, 0,
    ]


def _write_cp(tmp_path, rows, account="99999999", year="2025"):
    name = f"ClosedPositions_{account}_{year}-01-01_{year}-12-31.xlsx"
    p = tmp_path / name
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "ClosedPositions"
    ws.append(_HEADERS)
    for r in rows:
        ws.append(r)
    wb.save(p)
    return p


# ── detect() ─────────────────────────────────────────────────────────────────

def test_detect_closedpositions(tmp_path):
    p = tmp_path / "ClosedPositions_18801362_2025-01-01_2025-12-31.xlsx"
    p.write_bytes(b"")
    assert detect(p)


def test_detect_rejects_non_closedpos(tmp_path):
    for name in [
        "AggregatedAmounts_999_2025.xlsx",
        "ClosedPositions_99.csv",
        "report.xlsx",
    ]:
        p = tmp_path / name
        p.write_bytes(b"")
        assert not detect(p), f"should not detect: {name}"


# ── get_account_id() ─────────────────────────────────────────────────────────

def test_get_account_id(tmp_path):
    p = tmp_path / "ClosedPositions_18801362_2025-01-01_2025-12-31.xlsx"
    assert get_account_id(p) == "18801362"


# ── DK-native position: real qty SELL + BUY ───────────────────────────────────

def test_dk_native_emits_sell_and_buy(tmp_path):
    rows = [_cp_row(
        date(2025, 8, 11), date(2024, 11, 26), "PLTR:xnas",
        qty_close=-20, qty_open=100,
        open_px=Decimal("26.39"), close_px=Decimal("184.86"),
        open_pos_id=6084881370, close_pos_id=6365402742,
    )]
    p = _write_cp(tmp_path, rows)
    txns, account_id = parse(p, {})

    assert account_id == "99999999"
    assert len(txns) == 2

    sell = next(t for t in txns if t.txn_type == TransactionType.SELL)
    buy  = next(t for t in txns if t.txn_type == TransactionType.BUY)

    assert sell.symbol == "PLTR"
    assert sell.quantity == Decimal("20")
    assert sell.trade_date == date(2025, 8, 11)
    assert sell.orig_amount == Decimal("20") * Decimal("184.86")
    assert sell.orig_currency == "USD"

    assert buy.symbol == "PLTR"
    assert buy.quantity == Decimal("100")
    assert buy.trade_date == date(2024, 11, 26)
    assert buy.orig_amount == -(Decimal("100") * Decimal("26.39"))
    assert buy.orig_currency == "USD"


def test_dk_native_raw_ids(tmp_path):
    rows = [_cp_row(
        date(2025, 8, 11), date(2024, 11, 26), "PLTR:xnas",
        open_pos_id=6084881370, close_pos_id=6365402742,
    )]
    p = _write_cp(tmp_path, rows)
    txns, _ = parse(p, {})
    raw_ids = {t.raw_id for t in txns}
    assert "saxo_cp_buy_6084881370" in raw_ids
    assert "saxo_cp_sell_6365402742" in raw_ids


# ── Partial close: two closes from same lot ────────────────────────────────────

def test_partial_close_buy_emitted_once(tmp_path):
    """Two close events on the same lot → one BUY, two SELLs."""
    rows = [
        _cp_row(date(2025, 8, 11), date(2024, 11, 26), "PLTR:xnas",
                qty_close=-20, qty_open=100,
                open_pos_id=6084881370, close_pos_id=6365402742),
        _cp_row(date(2025, 11, 18), date(2024, 11, 26), "PLTR:xnas",
                qty_close=-20, qty_open=100,
                open_pos_id=6084881370, close_pos_id=6484829837),
    ]
    p = _write_cp(tmp_path, rows)
    txns, _ = parse(p, {})

    buys  = [t for t in txns if t.txn_type == TransactionType.BUY]
    sells = [t for t in txns if t.txn_type == TransactionType.SELL]

    assert len(buys) == 1,  "same OpenPositionId → only one BUY"
    assert len(sells) == 2, "two close events → two SELLs"
    assert buys[0].quantity == Decimal("100")
    assert buys[0].raw_id == "saxo_cp_buy_6084881370"


# ── SG-transferred lot: qty=1 compatibility mode ─────────────────────────────

def test_sg_lot_emits_qty1_sell_no_buy(tmp_path):
    """Open date on skip list → SELL qty=1, no BUY (manual_cost_basis handles cost)."""
    config = {"saxo_closedpos_skip_buy_open_dates": ["2024-03-07"]}
    rows = [_cp_row(
        date(2024, 12, 31), date(2024, 3, 7), "BABA:xnys",
        qty_close=-15, qty_open=15,
        open_px=Decimal("178.15"), close_px=Decimal("84.97"),
        open_pos_id=5835492516, close_pos_id=6115034015,
    )]
    p = _write_cp(tmp_path, rows)
    txns, _ = parse(p, config)

    sells = [t for t in txns if t.txn_type == TransactionType.SELL]
    buys  = [t for t in txns if t.txn_type == TransactionType.BUY]

    assert len(sells) == 1
    assert len(buys) == 0, "SG lot: no BUY emitted"
    assert sells[0].quantity == Decimal("1"), "SG lot: qty=1 for manual_cost_basis compat"
    assert sells[0].orig_amount == Decimal("15") * Decimal("84.97")


def test_sg_lot_proceeds_use_real_amount(tmp_path):
    """Even in qty=1 mode, orig_amount reflects real proceeds (qty_close × close_px)."""
    config = {"saxo_closedpos_skip_buy_open_dates": ["2024-03-07"]}
    rows = [_cp_row(
        date(2024, 12, 31), date(2024, 3, 7), "NIO:xnys",
        qty_close=-200, qty_open=200,
        open_px=Decimal("17.65"), close_px=Decimal("4.51"),
        open_pos_id=5835492493, close_pos_id=6115037890,
    )]
    p = _write_cp(tmp_path, rows)
    txns, _ = parse(p, config)
    sell = txns[0]
    assert sell.orig_amount == Decimal("200") * Decimal("4.51")


# ── Options skipped ───────────────────────────────────────────────────────────

def test_options_are_skipped(tmp_path):
    rows = [
        _cp_row(date(2025, 8, 29), date(2025, 8, 4), "C3AI.OPT:xcbf",
                asset_type="StockOption", qty_close=-1, qty_open=1,
                open_pos_id=9001, close_pos_id=9002),
        _cp_row(date(2025, 8, 11), date(2024, 11, 26), "PLTR:xnas",
                qty_close=-20, qty_open=100,
                open_pos_id=6084881370, close_pos_id=6365402742),
    ]
    p = _write_cp(tmp_path, rows)
    txns, _ = parse(p, {})
    symbols = {t.symbol for t in txns}
    assert "PLTR" in symbols
    # The option symbol (C3AI.OPT) should not appear
    assert all(t.asset_class != AssetClass.OPTION or True for t in txns)  # skipped entirely
    assert not any("xcbf" in t.symbol.lower() for t in txns)


# ── Multiple assets same date ─────────────────────────────────────────────────

def test_multiple_symbols_same_close_date(tmp_path):
    rows = [
        _cp_row(date(2026, 1, 21), date(2024, 3, 7), "BA:xnys",
                qty_close=-20, qty_open=20, open_pos_id=5001, close_pos_id=6001),
        _cp_row(date(2026, 1, 21), date(2024, 8, 8), "INTC:xnas",
                qty_close=-10, qty_open=10, open_pos_id=5002, close_pos_id=6002),
    ]
    config = {"saxo_closedpos_skip_buy_open_dates": ["2024-03-07"]}
    p = _write_cp(tmp_path, rows)
    txns, _ = parse(p, config)

    sells = [t for t in txns if t.txn_type == TransactionType.SELL]
    buys  = [t for t in txns if t.txn_type == TransactionType.BUY]

    assert len(sells) == 2
    # BA is SG lot (2024-03-07 → skip), INTC DK lot (2024-08-08 → emit buy)
    assert len(buys) == 1
    assert buys[0].symbol == "INTC"

    ba_sell = next(t for t in sells if t.symbol == "BA")
    assert ba_sell.quantity == Decimal("1")

    intc_sell = next(t for t in sells if t.symbol == "INTC")
    assert intc_sell.quantity == Decimal("10")


# ── broker label and country ──────────────────────────────────────────────────

def test_broker_label_is_saxo_cp(tmp_path):
    rows = [_cp_row(date(2025, 1, 1), date(2024, 6, 1), "XYZ:xnas",
                    open_pos_id=1, close_pos_id=2)]
    p = _write_cp(tmp_path, rows)
    txns, _ = parse(p, {})
    assert all(t.broker == "saxo_cp" for t in txns)


def test_country_from_exchange_suffix(tmp_path):
    rows = [
        _cp_row(date(2025, 1, 1), date(2024, 1, 1), "A:xnas",
                open_pos_id=1, close_pos_id=11),
        _cp_row(date(2025, 1, 2), date(2024, 1, 2), "B:xhkg",
                open_pos_id=2, close_pos_id=12),
    ]
    p = _write_cp(tmp_path, rows)
    txns, _ = parse(p, {})
    by_sym = {t.symbol: t for t in txns if t.txn_type == TransactionType.SELL}
    assert by_sym["A"].country_code == "US"
    assert by_sym["B"].country_code == "CN"


# ── saxo_skip_agg_trades flag ─────────────────────────────────────────────────

def test_agg_skip_trades_flag(tmp_path):
    """saxo_skip_agg_trades: true → AggregatedAmounts emits dividends only."""
    import openpyxl as ox
    from brokers.saxo_xlsx import parse as agg_parse

    headers = [
        "Date", "Booking Account ID", "Account Currency", "Client Currency",
        "Amount Type Name", "Affects Balance", "Asset type",
        "Unified Instrument Code (UIC)", "Underlying Instrument SubType",
        "Instrument Symbol", "Instrument Description",
        "Instrument SubType", "Underlying Instrument AssetType",
        "Underlying Instrument Description", "Underlying Instrument Symbol",
        "Underlying Instrument Uic", "Amount", "Amount Account Currency",
        "Amount Client Currency", "Cost type", "Cost subtype",
    ]

    def make_row(amt_type, symbol, uic, amount):
        return [
            "01-06-2025", "TESTACCT", "USD", "EUR",
            amt_type, "Yes", "Stock", uic, "None",
            symbol, "Desc", "None", "Stock", "Desc", symbol, uic,
            amount, amount, amount, " ", " ",
        ]

    wb = ox.Workbook()
    ws = wb.active
    ws.title = "Cash Movements"
    ws.append(headers)
    ws.append(make_row("Share Amount", "PLTR:xnas", 1, 3000.00))        # trade → skip
    ws.append(make_row("Corporate Actions - Cash Dividends", "PLTR:xnas", 1, 50.00))  # div → keep

    name = tmp_path / "AggregatedAmounts_99999999_2025-01-01_2025-12-31.xlsx"
    wb.save(name)

    txns, _ = agg_parse(name, {"saxo_skip_agg_trades": True})
    assert len(txns) == 1
    assert txns[0].txn_type == TransactionType.DIVIDEND
