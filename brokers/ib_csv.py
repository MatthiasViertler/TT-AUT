"""
Interactive Brokers parser.
Handles IB Activity Statement exports in CSV format (Flex Query).

How to get your IB export:
1. Log in to Client Portal → Reports → Flex Queries
2. Create a new Activity Flex Query with sections:
   - Trades (FIFO cost basis, all fields)
   - Cash Transactions (dividends, WHT, interest)
   - Open Positions (optional, for dashboard)
3. Run query → Download CSV (or XML — XML parser is in ib_xml.py)

The CSV has a multi-section format where each section starts with a header row.
We detect sections by their first column value.
"""

import csv
import logging
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import StringIO
from pathlib import Path
from typing import Optional

from core.models import (
    NormalizedTransaction, TransactionType, AssetClass, Domicile
)

log = logging.getLogger(__name__)


# Map IB asset class codes → our AssetClass
IB_ASSET_CLASS_MAP = {
    "STK": AssetClass.STOCK,
    "ETF": AssetClass.ETF,
    "OPT": AssetClass.OPTION,
    "FUT": AssetClass.OTHER,
    "BOND": AssetClass.BOND,
    "CASH": AssetClass.CASH,
    "FUND": AssetClass.FUND,
}

# Countries whose exchanges indicate domestic AT listing
AT_EXCHANGE_PATTERNS = {"VSE", "WBAG", "XWBO"}


def detect(path: Path) -> bool:
    """Return True if this file looks like an IB CSV export."""
    try:
        with open(path, encoding="utf-8-sig", errors="replace") as f:
            head = f.read(512)
        # Flex Query custom format: starts with BOF record
        # Classic Activity Statement: starts with "Statement,Header"
        return (head.startswith('"BOF"') or head.startswith('BOF,') or
                "Interactive Brokers" in head or "Statement,Header" in head)
    except Exception:
        return False


def parse(path: Path, config: dict) -> list[NormalizedTransaction]:
    """Parse an IB CSV Activity Statement into normalized transactions.

    Supports two IB CSV formats:
    - Custom Flex Query format: BOF / HEADER / DATA / EOS rows, section code in col[1]
      e.g.  "HEADER","TRNT","Symbol","ISIN",...
            "DATA","TRNT","U1234","EUR",...
    - Classic Activity Statement format: SectionName / Header / Data rows
      e.g.  "Trades","Header","Asset Category","Symbol",...
            "Trades","Data","Stocks","AAPL",...
    """
    log.info(f"IB parser: reading {path.name}")

    # Section code → human name mapping for Flex Query format
    SECTION_CODE_MAP = {
        "TRNT": "Trades",
        "CTRN": "Cash Transactions",
    }

    sections: dict[str, list[dict]] = {}
    current_headers: list[str] = []
    current_section: str = ""

    with open(path, encoding="utf-8-sig", errors="replace") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            marker = row[0].strip()
            col1   = row[1].strip() if len(row) > 1 else ""

            # ── Flex Query format ──────────────────────────────────────────
            if marker == "HEADER":
                section_code = col1
                current_section = SECTION_CODE_MAP.get(section_code, section_code)
                current_headers = [c.strip() for c in row[2:]]
                sections.setdefault(current_section, [])

            elif marker == "DATA" and current_section:
                record = dict(zip(current_headers, [c.strip() for c in row[2:]]))
                sections[current_section].append(record)

            # ── Classic Activity Statement format ──────────────────────────
            elif col1 == "Header":
                current_section = marker
                current_headers = [c.strip() for c in row[2:]]
                sections.setdefault(current_section, [])

            elif col1 == "Data" and current_section:
                record = dict(zip(current_headers, [c.strip() for c in row[2:]]))
                sections[current_section].append(record)

    transactions: list[NormalizedTransaction] = []

    # ── Cash Transactions (dividends, WHT, interest) ──────────────────────────
    cash_txns = _parse_cash_transactions(
        sections.get("Cash Transactions", []), config, str(path)
    )

    # Match WHT rows against their dividend rows
    matched = _match_wht_to_dividends(cash_txns)
    transactions.extend(matched)

    # ── Trades ────────────────────────────────────────────────────────────────
    trade_txns = _parse_trades(
        sections.get("Trades", []), config, str(path)
    )
    transactions.extend(trade_txns)

    log.info(f"IB parser: {len(transactions)} transactions parsed from {path.name}")
    return transactions


# ── Cash Transactions ─────────────────────────────────────────────────────────

def _parse_cash_transactions(rows: list[dict], config: dict,
                              source: str) -> list[NormalizedTransaction]:
    action_map = config.get("ib_action_map", {})

    # Your Flex Query uses full Type strings — map them to internal codes
    FULL_TYPE_MAP = {
        "Withholding Tax":          "DIVNRA",
        "Dividends":                "DIV",
        "Payment In Lieu Of A Dividend": "DIV",
        "Broker Interest Received": "CINT",
        "Deposits/Withdrawals":     "DEP",
    }

    results = []

    for row in rows:
        raw_type = row.get("Type", "").strip()
        # Normalise to short code first, then look up in action_map
        short_code = FULL_TYPE_MAP.get(raw_type, raw_type)
        mapped = action_map.get(short_code, "unknown")
        if mapped not in config.get("taxable_types", []):
            continue

        try:
            trade_date = _parse_ib_date(row.get("Date/Time", row.get("Date", "")))
        except Exception:
            log.warning(f"IB: Skipping row with unparseable date: {row}")
            continue

        # Flex Query uses CurrencyPrimary; classic uses Currency — handle both
        currency = (row.get("CurrencyPrimary") or row.get("Currency") or "").strip()
        amount   = _parse_decimal(row.get("Amount", "0"))
        symbol   = row.get("Symbol", "").strip()

        # ISIN: prefer direct field, fall back to extracting from description
        isin = (row.get("ISIN") or "").strip() or _extract_isin(row.get("Description", ""))
        description  = row.get("Description", "").strip()
        country_code = _country_from_isin(isin) if isin else _country_from_description(description)
        domicile     = _classify_domicile(isin, country_code, row.get("Exchange", ""))

        txn_type = TransactionType(mapped)

        # WHT rows come in as negative amounts; store absolute value in wht field
        wht_amount = ZERO
        if txn_type == TransactionType.DIVIDEND_WHT:
            wht_amount = amount.copy_abs()
            amount = ZERO

        txn = NormalizedTransaction(
            broker="ib",
            raw_id=f"ib_cash_{trade_date}_{symbol}_{short_code}_{amount or wht_amount}",
            trade_date=trade_date,
            settle_date=None,
            txn_type=txn_type,
            asset_class=AssetClass.STOCK,
            symbol=symbol,
            isin=isin or None,
            description=description,
            country_code=country_code,
            domicile=domicile,
            quantity=None,
            price=None,
            price_currency=None,
            orig_currency=currency,
            orig_amount=amount,
            wht_amount_orig=wht_amount,
            source_file=source,
        )
        results.append(txn)

    return results


def _match_wht_to_dividends(
        txns: list[NormalizedTransaction]) -> list[NormalizedTransaction]:
    """
    IB reports WHT as separate rows with type DIVIDEND_WHT.
    Match each WHT row to its dividend or interest row (same date, same currency)
    and merge the WHT in. Orphaned WHT rows (e.g. on broker credit interest)
    are kept as standalone DIVIDEND_WHT entries so they still feed KZ 998/899.
    """
    divs    = [t for t in txns if t.txn_type == TransactionType.DIVIDEND]
    ints    = [t for t in txns if t.txn_type == TransactionType.INTEREST]
    whts    = [t for t in txns if t.txn_type == TransactionType.DIVIDEND_WHT]
    others  = [t for t in txns if t.txn_type not in
               (TransactionType.DIVIDEND, TransactionType.DIVIDEND_WHT,
                TransactionType.INTEREST)]

    # Build lookup: (symbol, date) → dividend txn
    div_map: dict[tuple, NormalizedTransaction] = {}
    for d in divs:
        div_map[(d.symbol, d.trade_date)] = d

    # Fallback lookup for interest WHT: (date, currency) → interest txn
    int_map: dict[tuple, NormalizedTransaction] = {}
    for i in ints:
        int_map[(i.trade_date, i.orig_currency)] = i

    for wht in whts:
        div_key = (wht.symbol, wht.trade_date)
        int_key = (wht.trade_date, wht.orig_currency)

        if div_key in div_map:
            div_map[div_key].wht_amount_orig += wht.wht_amount_orig
            gross = div_map[div_key].orig_amount
            if gross:
                div_map[div_key].wht_rate_actual = (
                    wht.wht_amount_orig / gross
                ).quantize(Decimal("0.0001"))
        elif int_key in int_map:
            # WHT on broker interest (e.g. Austrian KESt on EUR credit interest)
            int_map[int_key].wht_amount_orig += wht.wht_amount_orig
        else:
            log.debug(f"IB: Unmatched WHT row: {wht.symbol!r} on {wht.trade_date} — kept standalone")
            others.append(wht)

    return list(div_map.values()) + list(int_map.values()) + others


# ── Trades ────────────────────────────────────────────────────────────────────

def _parse_trades(rows: list[dict], config: dict,
                  source: str) -> list[NormalizedTransaction]:
    results = []
    action_map = config.get("ib_action_map", {})

    for row in rows:
        # Skip FX cash conversion rows (EUR.USD etc.) — not taxable equity trades
        asset_class_raw = row.get("AssetClass", row.get("Asset Class", "")).strip().upper()
        if asset_class_raw == "CASH":
            continue

        action = row.get("Buy/Sell", "").strip().upper()
        if action not in ("BUY", "SELL"):
            continue

        try:
            # Flex Query: DateTime field;  Classic: Date/Time or TradeDate
            trade_date = _parse_ib_date(
                row.get("DateTime") or row.get("Date/Time") or row.get("TradeDate", "")
            )
        except Exception:
            continue

        # Flex Query: CurrencyPrimary;  Classic: Currency
        currency   = (row.get("CurrencyPrimary") or row.get("Currency") or "").strip()
        quantity   = _parse_decimal(row.get("Quantity", "0"))
        # Flex Query: TradePrice;  Classic: T. Price
        price      = _parse_decimal(row.get("TradePrice") or row.get("T. Price") or "0")
        proceeds   = _parse_decimal(row.get("Proceeds", "0"))
        # Flex Query: IBCommission;  Classic: Comm/Fee or IBCommission
        commission = _parse_decimal(
            row.get("IBCommission") or row.get("Comm/Fee") or "0"
        ).copy_abs()
        symbol      = row.get("Symbol", "").strip()
        isin        = (row.get("ISIN") or "").strip() or None
        description = row.get("Description", "").strip()
        exchange    = row.get("Exchange", "").strip()

        country_code = _country_from_isin(isin) if isin else None
        domicile     = _classify_domicile(isin, country_code, exchange)
        asset_class  = IB_ASSET_CLASS_MAP.get(asset_class_raw, AssetClass.OTHER)

        txn = NormalizedTransaction(
            broker="ib",
            raw_id=f"ib_trade_{trade_date}_{symbol}_{action}_{proceeds}",
            trade_date=trade_date,
            settle_date=None,
            txn_type=TransactionType(action_map.get(action, "unknown")),
            asset_class=asset_class,
            symbol=symbol,
            isin=isin,
            description=description,
            country_code=country_code,
            domicile=domicile,
            quantity=quantity,
            price=price,
            price_currency=currency,
            orig_currency=currency,
            orig_amount=proceeds,
            commission=commission,
            commission_currency=currency,
            source_file=source,
        )
        results.append(txn)

    return results


# ── Helpers ───────────────────────────────────────────────────────────────────

ZERO = Decimal("0")

ISIN_RE = re.compile(r'\b([A-Z]{2}[A-Z0-9]{10})\b')


def _parse_ib_date(s: str) -> date:
    if not s:
        raise ValueError("Empty date string")
    # Normalise: IB Flex uses semicolon as date/time separator e.g. "2025-01-02;07:43:28"
    # Classic format uses comma e.g. "2025-01-02, 07:43:28"
    s = s.strip().replace(";", " ").split(",")[0].strip()
    # Take only the date portion (first 10 chars) regardless of time part
    date_part = s[:10]
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%m/%d/%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(date_part, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"Cannot parse IB date: {s!r}")


def _parse_decimal(s: str) -> Decimal:
    if not s:
        return ZERO
    s = s.replace(",", "").strip()
    try:
        return Decimal(s)
    except InvalidOperation:
        return ZERO


def _extract_isin(description: str) -> Optional[str]:
    m = ISIN_RE.search(description)
    return m.group(1) if m else None


def _country_from_isin(isin: Optional[str]) -> Optional[str]:
    if isin and len(isin) >= 2:
        return isin[:2].upper()
    return None


def _country_from_description(description: str) -> Optional[str]:
    """Heuristic: try to extract country from IB description strings."""
    # IB sometimes includes exchange like "(XNAS)" in descriptions
    m = re.search(r'\(([A-Z]{4})\)', description)
    if m:
        mic = m.group(1)
        MIC_TO_COUNTRY = {
            "XNAS": "US", "XNYS": "US", "XASE": "US", "BATS": "US",
            "XLON": "GB", "XPAR": "FR", "XFRA": "DE", "XAMS": "NL",
            "XSWX": "CH", "XMIL": "IT", "XMAD": "ES", "XSTO": "SE",
            "XCSE": "DK", "XHEL": "FI", "XOSL": "NO", "XTSE": "CA",
            "XTSX": "CA", "XASX": "AU", "XTKS": "JP", "XHKG": "HK",
            "WBAG": "AT", "XWBO": "AT",
        }
        return MIC_TO_COUNTRY.get(mic)
    return None


def _classify_domicile(isin: Optional[str], country: Optional[str],
                        exchange: str) -> Domicile:
    if isin and isin.startswith("AT"):
        return Domicile.DOMESTIC
    if exchange and exchange.upper() in AT_EXCHANGE_PATTERNS:
        return Domicile.DOMESTIC
    if country == "AT":
        return Domicile.DOMESTIC
    if country:
        return Domicile.FOREIGN
    return Domicile.UNKNOWN
