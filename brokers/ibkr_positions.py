"""
IBKR Flex Open Positions parser.

Reads a Flex Query report containing an "Open Positions" section and returns
per-symbol position data (quantity + Dec-31 mark price + currency).

This is used instead of FIFO-reconstructed positions × yfinance when an
Open Positions report is available, giving accurate prices for European stocks
and other tickers that yfinance can't resolve.

Setup: create a second Flex Query in IBKR configured to return "Open Positions"
as of Dec 31 (or whatever date you need).  Set positions_query_id in config:

  ibkr_flex:
    token: "your_token"
    query_id: 123456           # Activity Statement
    positions_query_id: 234567  # Open Positions

Supports the same three IB CSV formats as brokers/ib_csv.py:
  - HEADER/DATA Flex Query format  (col[0] = HEADER or DATA, col[1] = section code)
  - BOS/EOS TT-AUT format          (marker BOS/EOS with section name in col[1])
  - Classic Activity Statement     (col[1] = Header / Data)
"""

import csv
import logging
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

ZERO = Decimal("0")

# All section name spellings IBKR uses across report types
_OPEN_POS_NAMES = {"Open Positions", "OpenPositions", "OPENPOS", "OpenPos", "POST"}

# Column name alternatives for each field (IBKR uses slightly different names
# depending on the Flex Query type and format version)
_COL_SYMBOL   = ("Symbol",)
_COL_ISIN     = ("ISIN", "SecurityID")
_COL_QTY      = ("Position", "Qty", "Quantity")
_COL_PRICE    = ("MarkPrice", "Mark Price", "ClosePrice", "Close Price", "LastPrice")
_COL_CURRENCY = ("CurrencyPrimary", "Currency", "Ccy")
_COL_ASSET    = ("AssetClass", "Asset Class", "SubCategory")
_COL_DETAIL   = ("LevelOfDetail", "Level of Detail", "Detail")
_COL_ISIN_TYPE = ("SecurityIDType",)

# Skip these asset classes (options, futures, cash, bonds)
_SKIP_ASSET = {"OPT", "FUT", "CASH", "BOND", "FOP", "WAR"}

# Skip summary/aggregate rows (only keep per-security rows)
_SKIP_DETAIL = {"CURRENCY", "ACCOUNT", "TOTAL"}


def parse_ibkr_positions(path: Path) -> dict[str, dict]:
    """Parse an IBKR Flex Open Positions report.

    Returns:
        {symbol: {"qty": Decimal, "price": Decimal, "currency": str, "isin": str}}

    Only includes STK/ETF/FUND positions with qty > 0 and price > 0.
    Positions sharing a symbol (e.g. same stock in multiple lot rows) are summed.
    """
    rows = _read_open_positions_section(path)
    positions: dict[str, dict] = {}

    for row in rows:
        asset = _get(row, *_COL_ASSET).upper()
        if asset in _SKIP_ASSET:
            continue

        detail = _get(row, *_COL_DETAIL).upper()
        if detail in _SKIP_DETAIL:
            continue

        symbol = _get(row, *_COL_SYMBOL)
        if not symbol:
            continue

        qty_str   = _get(row, *_COL_QTY)
        price_str = _get(row, *_COL_PRICE)
        currency  = _get(row, *_COL_CURRENCY) or "USD"

        # Resolve ISIN: prefer explicit ISIN column; fall back to SecurityID if type=ISIN
        isin = _get(row, "ISIN")
        if not isin:
            sec_id   = _get(row, "SecurityID")
            sec_type = _get(row, "SecurityIDType").upper()
            if sec_type == "ISIN" and sec_id:
                isin = sec_id

        try:
            qty = Decimal(qty_str)
        except (InvalidOperation, ValueError):
            log.debug("ibkr-pos: skip %s — unparseable qty %r", symbol, qty_str)
            continue

        try:
            price = Decimal(price_str)
        except (InvalidOperation, ValueError):
            log.debug("ibkr-pos: skip %s — unparseable price %r", symbol, price_str)
            continue

        if qty <= ZERO or price <= ZERO:
            continue

        if symbol in positions:
            # Multiple lot rows for same symbol → sum quantities; price is the same
            positions[symbol]["qty"] += qty
        else:
            positions[symbol] = {
                "qty": qty,
                "price": price,
                "currency": currency,
                "isin": isin,
            }
        log.debug("ibkr-pos: %s qty=%s price=%s %s", symbol, qty, price, currency)

    log.info("ibkr-pos: loaded %d positions from %s", len(positions), path.name)
    return positions


def _get(row: dict, *keys: str, default: str = "") -> str:
    """Return the first matching key from row, stripped; default if none found."""
    for k in keys:
        if k in row:
            return row[k].strip()
    return default


def _read_open_positions_section(path: Path) -> list[dict]:
    """Read all rows from the 'Open Positions' section of an IB Flex CSV file."""
    rows: list[dict] = []
    headers: list[str] = []
    in_section = False
    bos_state: Optional[str] = None

    with open(path, encoding="utf-8-sig", errors="replace") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            marker = row[0].strip()
            col1   = row[1].strip() if len(row) > 1 else ""

            if marker == "BOF":
                continue

            # ── BOS/EOS format ────────────────────────────────────────────────
            if marker == "BOS":
                if col1 in _OPEN_POS_NAMES:
                    in_section = True
                    bos_state = "header_next"
                continue

            if marker == "EOS":
                if in_section:
                    in_section = False
                    bos_state = None
                    headers = []
                continue

            if bos_state == "header_next":
                headers = [c.strip() for c in row]
                bos_state = "data"
                continue

            if bos_state == "data" and in_section:
                rows.append(dict(zip(headers, [c.strip() for c in row])))
                continue

            # ── HEADER/DATA Flex Query format ─────────────────────────────────
            if marker == "HEADER":
                if col1 in _OPEN_POS_NAMES:
                    headers = [c.strip() for c in row[2:]]
                    in_section = True
                elif in_section:
                    in_section = False
                continue

            if marker == "DATA" and in_section:
                rows.append(dict(zip(headers, [c.strip() for c in row[2:]])))
                continue

            # ── Classic Activity Statement format ─────────────────────────────
            if col1 == "Header":
                if marker in _OPEN_POS_NAMES:
                    headers = [c.strip() for c in row[2:]]
                    in_section = True
                elif in_section:
                    in_section = False
                continue

            if col1 == "Data" and in_section:
                rows.append(dict(zip(headers, [c.strip() for c in row[2:]])))

    log.debug("ibkr-pos: %d raw rows read from Open Positions section", len(rows))
    return rows
