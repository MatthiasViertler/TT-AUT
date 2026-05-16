"""
Interactive Brokers parser.
Handles IB Activity Statement exports in CSV format.

Supported formats:
1. Flex Query HEADER/DATA: each row prefixed HEADER/DATA, section code in col[1].
   CTRN includes DateTime. Used by default Flex Query exports (e.g. Jessie's files).
2. TT-AUT Export BOS/EOS: BOS/EOS section markers, plain header row after BOS,
   no date in CTRN. Cash transactions matched using per-share netting (Matthias's files).
3. Classic Activity Statement: SectionName/Header/Data rows.

TT-AUT netting: groups CTRN rows by (symbol, per_share_str, currency), nets all dividend
and WHT amounts within each group. Handles reversals, quarterly same-rate dividends,
and Return of Capital (P911-style) naturally without special-casing.
"""

import csv
import logging
import re
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional

from core.models import (
    NormalizedTransaction, TransactionType, AssetClass, Domicile
)

log = logging.getLogger(__name__)


IB_ASSET_CLASS_MAP = {
    "STK": AssetClass.STOCK,
    "ETF": AssetClass.ETF,
    "OPT": AssetClass.OPTION,
    "FUT": AssetClass.OTHER,
    "BOND": AssetClass.BOND,
    "CASH": AssetClass.CASH,
    "FUND": AssetClass.FUND,
}

AT_EXCHANGE_PATTERNS = {"VSE", "WBAG", "XWBO"}

ZERO = Decimal("0")
ISIN_RE = re.compile(r'\b([A-Z]{2}[A-Z0-9]{10})\b')

# Matches "USD 1.51 PER SHARE" or "EUR 0.81683669 PER SHARE" in IB descriptions
PER_SHARE_RE = re.compile(r'([A-Z]{3}\s+\d+(?:\.\d+)?\s+PER\s+SHARE)', re.IGNORECASE)

# Matches "SYMBOL(ISIN) ..." at the start of IB cash-transaction descriptions
# Used as fallback when Symbol/ISIN columns are absent (e.g. ibkr_flex.csv CTRN format)
_DESC_SYMBOL_ISIN_RE = re.compile(r'^([A-Z][A-Z0-9.]+)\(([A-Z]{2}[A-Z0-9]{10})\)\s')

FULL_TYPE_MAP = {
    "Withholding Tax":               "DIVNRA",
    "Dividends":                     "DIV",
    "Payment In Lieu Of A Dividend": "DIV",
    "Broker Interest Received":      "CINT",
    "Deposits/Withdrawals":          "DEP",
}


_CASH_REPORT_SECTION_NAMES = {"Cash Report", "CashReport", "CRTT"}
_CTRN_SECTION_NAMES        = {"Cash Transactions", "CashTransactions", "CTRN"}

# Matches the year at the end of IB interest descriptions: "EUR CREDIT INT FOR MAY-2025"
_INTEREST_YEAR_RE = re.compile(r'\b(\d{4})\b')


def detect(path: Path) -> bool:
    """Return True if this file looks like an IB CSV export."""
    try:
        with open(path, encoding="utf-8-sig", errors="replace") as f:
            head = f.read(512)
        return (head.startswith('"BOF"') or head.startswith('BOF,') or
                "Interactive Brokers" in head or "Statement,Header" in head)
    except Exception:
        return False


def get_account_id(path: Path) -> Optional[str]:
    """Extract account ID from BOF row (Flex Query) or Statement row (classic)."""
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        for line in f:
            parts = line.strip().split(',')
            marker = parts[0].strip('"')
            if marker == "BOF" and len(parts) > 1:
                return parts[1].strip('"')
            if marker == "Statement" and len(parts) > 2:
                for p in parts:
                    p = p.strip('"')
                    if p.startswith('U') and p[1:].isdigit():
                        return p
    return None


def parse(path: Path, config: dict) -> tuple[list[NormalizedTransaction], Optional[str]]:
    """Parse an IB CSV Activity Statement into normalized transactions.

    Returns (transactions, account_id).

    Supports three IB CSV formats:
    - TT-AUT Export BOS/EOS: plain header/data rows within BOS/EOS markers
    - Flex Query HEADER/DATA: row-prefixed section rows
    - Classic Activity Statement: SectionName/Header/Data rows
    """
    log.info(f"IB parser: reading {path.name}")

    account_id = get_account_id(path)

    SECTION_CODE_MAP = {
        "TRNT": "Trades",
        "CTRN": "Cash Transactions",
    }

    sections: dict[str, list[dict]] = {}
    current_headers: list[str] = []
    current_section: str = ""
    bof_end_date: Optional[date] = None

    # BOS/EOS state for TT-AUT format: None | "header_next" | "data"
    bos_state: Optional[str] = None
    bos_section: str = ""

    with open(path, encoding="utf-8-sig", errors="replace") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            marker = row[0].strip()
            col1   = row[1].strip() if len(row) > 1 else ""

            # BOF: extract year-end date (col[5]) — used as fallback date for TT-AUT CTRN
            if marker == "BOF":
                if len(row) > 5:
                    try:
                        bof_end_date = _parse_ib_date(row[5].strip())
                    except Exception:
                        pass
                continue

            # TT-AUT BOS/EOS section markers
            if marker == "BOS":
                bos_section = SECTION_CODE_MAP.get(col1, col1)
                sections.setdefault(bos_section, [])
                bos_state = "header_next"
                continue

            if marker == "EOS":
                bos_state = None
                bos_section = ""
                continue

            # In BOS/EOS mode: next row after BOS = header, then plain data rows
            if bos_state == "header_next":
                current_headers = [c.strip() for c in row]
                current_section = bos_section
                bos_state = "data"
                continue

            if bos_state == "data":
                record = dict(zip(current_headers, [c.strip() for c in row]))
                sections[bos_section].append(record)
                continue

            # Flex Query HEADER/DATA format
            if marker == "HEADER":
                section_code = col1
                current_section = SECTION_CODE_MAP.get(section_code, section_code)
                current_headers = [c.strip() for c in row[2:]]
                sections.setdefault(current_section, [])

            elif marker == "DATA" and current_section:
                record = dict(zip(current_headers, [c.strip() for c in row[2:]]))
                sections[current_section].append(record)

            # Classic Activity Statement format
            elif col1 == "Header":
                current_section = marker
                current_headers = [c.strip() for c in row[2:]]
                sections.setdefault(current_section, [])

            elif col1 == "Data" and current_section:
                record = dict(zip(current_headers, [c.strip() for c in row[2:]]))
                sections[current_section].append(record)

    transactions: list[NormalizedTransaction] = []

    cash_txns = _parse_cash_transactions(
        sections.get("Cash Transactions", []), config, str(path), bof_end_date
    )
    transactions.extend(cash_txns)

    trade_txns = _parse_trades(
        sections.get("Trades", []), config, str(path)
    )
    transactions.extend(trade_txns)

    log.info(f"IB parser: {len(transactions)} transactions parsed from {path.name} "
             f"(account: {account_id})")
    return transactions, account_id


# ── Cash Transactions ─────────────────────────────────────────────────────────

def _parse_cash_transactions(
    rows: list[dict],
    config: dict,
    source: str,
    fallback_date: Optional[date] = None,
) -> list[NormalizedTransaction]:
    """Route to dated or netted parser based on whether CTRN rows have a date field."""
    if not rows:
        return []

    has_dates = any(
        row.get("Date/Time") or row.get("DateTime") or row.get("Date")
        for row in rows[:10]
    )

    action_map = config.get("ib_action_map", {})

    if has_dates:
        raw = _parse_cash_rows_dated(rows, config, source, action_map)
        return _match_wht_to_dividends(raw)
    else:
        return _parse_cash_rows_netted(rows, config, source, fallback_date, action_map)


def _parse_cash_rows_dated(
    rows: list[dict],
    config: dict,
    source: str,
    action_map: dict,
) -> list[NormalizedTransaction]:
    """Parse CTRN rows that have a Date/Time field (Flex Query format)."""
    results = []

    for row in rows:
        raw_type   = row.get("Type", "").strip()
        short_code = FULL_TYPE_MAP.get(raw_type, raw_type)
        mapped     = action_map.get(short_code, "unknown")
        if mapped not in config.get("taxable_types", []):
            continue

        try:
            trade_date = _parse_ib_date(row.get("Date/Time", row.get("Date", "")))
        except Exception:
            log.warning(f"IB: Skipping row with unparseable date: {row}")
            continue

        currency    = (row.get("CurrencyPrimary") or row.get("Currency") or "").strip()
        amount      = _parse_decimal(row.get("Amount", "0"))
        symbol      = row.get("Symbol", "").strip()
        isin        = (row.get("ISIN") or "").strip() or _extract_isin(row.get("Description", ""))
        description = row.get("Description", "").strip()
        symbol = _normalize_de_symbol(symbol, isin or None)
        country_code = _country_from_isin(isin) if isin else _country_from_description(description)
        domicile     = _classify_domicile(isin, country_code, row.get("Exchange", ""))

        txn_type = TransactionType(mapped)

        wht_amount = ZERO
        if txn_type == TransactionType.DIVIDEND_WHT:
            # IB WHT: negative amount = withheld; negate → positive stored value.
            # Refund rows (positive amount) produce negative stored value → reduces total WHT.
            wht_amount = -amount
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


def _parse_cash_rows_netted(
    rows: list[dict],
    config: dict,
    source: str,
    fallback_date: Optional[date],
    action_map: dict,
) -> list[NormalizedTransaction]:
    """
    TT-AUT format: no dates in CTRN. Net by (symbol, per_share_str, currency).

    Reversals cancel out in the net. Quarterly same-rate dividends sum correctly.
    Return of Capital groups (any description contains "Return of Capital") are skipped.
    WHT rows (negative amounts in IB) are negated to get positive withheld amounts.
    """
    if fallback_date is None:
        log.warning(f"IB: No BOF date available for {source} — cannot parse undated CTRN rows")
        return []

    # Warn once if Symbol/ISIN columns are absent from the CTRN section.
    # This means the Flex Query was set up without those fields. The parser falls
    # back to extracting them from description strings, so output is still correct,
    # but adding the fields avoids the fallback entirely.
    # Fix: IBKR → Reports → Flex Queries → edit query → Cash Transactions section
    #      → add Symbol and ISIN to the field list.
    if rows:
        sample_keys = rows[0].keys()
        missing = [c for c in ("Symbol", "ISIN") if c not in sample_keys]
        if missing:
            print(
                f"  [warn]   {Path(source).name} CTRN: column(s) {missing} absent from Flex Query — "
                f"extracting from description (fallback works, but consider adding "
                f"Symbol + ISIN to your Cash Transactions section in IBKR Flex Query settings)"
            )

    groups: dict[tuple, dict] = defaultdict(lambda: {
        "divs": [],
        "whts": [],
        "isin": "",
        "currency": "",
        "all_descriptions": [],
        "short_code": "",
        "mapped": "",
    })

    for row in rows:
        raw_type   = row.get("Type", "").strip()
        short_code = FULL_TYPE_MAP.get(raw_type, raw_type)
        mapped     = action_map.get(short_code, "unknown")
        if mapped not in config.get("taxable_types", []):
            continue

        amount      = _parse_decimal(row.get("Amount", "0"))
        symbol      = row.get("Symbol", "").strip()
        description = row.get("Description", "").strip()
        currency    = (row.get("CurrencyPrimary") or row.get("Currency") or "").strip()
        isin        = (row.get("ISIN") or "").strip()

        # Fallback: extract symbol and ISIN from description when row columns absent.
        # Handles ibkr_flex.csv CTRN format whose headers lack Symbol/ISIN columns.
        if not symbol or not isin:
            m = _DESC_SYMBOL_ISIN_RE.match(description)
            if m:
                if not symbol:
                    symbol = m.group(1)
                if not isin:
                    isin = m.group(2)

        symbol = _normalize_de_symbol(symbol, isin or None)
        per_share = _extract_per_share(description) or description[:60]
        key = (symbol, per_share, currency)
        grp = groups[key]

        if not grp["currency"]:
            grp["currency"] = currency
        if not grp["isin"] and isin:
            grp["isin"] = isin
        grp["all_descriptions"].append(description)

        if mapped == "dividend_wht":
            grp["whts"].append(amount)
        else:
            grp["divs"].append(amount)
            if not grp["short_code"]:
                grp["short_code"] = short_code
                grp["mapped"] = mapped

    results = []

    for (symbol, per_share, currency), grp in groups.items():
        # Skip Return of Capital — treat as cost basis adjustment, not taxable income
        if any("return of capital" in d.lower() for d in grp["all_descriptions"]):
            net_roc = sum(grp["divs"], ZERO)
            log.warning(
                f"IB: {symbol} '{per_share}' flagged as Return of Capital "
                f"(net {net_roc:.2f} {currency}) — skipping; adjusts cost basis, not taxable"
            )
            continue

        net_div  = sum(grp["divs"], ZERO)
        # WHT amounts in TT-AUT are negative (withheld) or positive (refund)
        net_wht  = sum(grp["whts"], ZERO)
        wht_held = -net_wht   # positive = net withheld, negative = net refund

        # Skip fully-reversed or zero groups
        if net_div == ZERO and wht_held <= ZERO:
            continue

        isin        = grp["isin"]
        country_code = _country_from_isin(isin) if isin else None
        domicile    = _classify_domicile(isin, country_code, "")
        description = next((d for d in grp["all_descriptions"] if d), per_share)

        if net_div != ZERO:
            mapped     = grp["mapped"]
            short_code = grp["short_code"]
            if not mapped:
                continue
            txn_type    = TransactionType(mapped)
            orig_amount = net_div
        else:
            # WHT with no matching dividend — keep as standalone
            short_code  = "DIVNRA"
            txn_type    = TransactionType.DIVIDEND_WHT
            orig_amount = ZERO

        wht_rate: Optional[Decimal] = None
        if net_div > ZERO and wht_held > ZERO:
            wht_rate = (wht_held / net_div).quantize(Decimal("0.0001"))

        txn = NormalizedTransaction(
            broker="ib",
            raw_id=f"ib_cash_{fallback_date}_{symbol}_{short_code}_{per_share}",
            trade_date=fallback_date,
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
            orig_amount=orig_amount,
            wht_amount_orig=max(ZERO, wht_held),
            wht_rate_actual=wht_rate,
            source_file=source,
        )
        results.append(txn)

    return results


def _extract_per_share(description: str) -> str:
    """Extract the 'CUR X.XX PER SHARE' token from an IB cash transaction description."""
    m = PER_SHARE_RE.search(description)
    return m.group(1).upper() if m else ""


def _normalize_de_symbol(symbol: str, isin: Optional[str]) -> str:
    """Strip the trailing 'd' suffix IB appends to German-exchange listings.

    IB adds a lowercase 'd' to tickers for stocks traded on German exchanges
    (e.g. ALVd, VNAd, BAYNd). The same stock can appear with or without the
    suffix in different exports, breaking FIFO matching. Strip it when the
    ISIN confirms this is a German-domiciled stock (DE prefix).
    """
    if isin and isin.startswith("DE") and symbol.endswith("d") and len(symbol) > 1:
        return symbol[:-1]
    return symbol


def _match_wht_to_dividends(
        txns: list[NormalizedTransaction]) -> list[NormalizedTransaction]:
    """
    For dated (Flex Query) format: match each WHT row to its dividend or interest row
    by (symbol, date) and merge the WHT in. Orphaned WHT rows are kept standalone.
    """
    divs   = [t for t in txns if t.txn_type == TransactionType.DIVIDEND]
    ints   = [t for t in txns if t.txn_type == TransactionType.INTEREST]
    whts   = [t for t in txns if t.txn_type == TransactionType.DIVIDEND_WHT]
    others = [t for t in txns if t.txn_type not in
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
    opt_skipped = 0

    for row in rows:
        asset_class_raw = row.get("AssetClass", row.get("Asset Class", "")).strip().upper()

        # Skip FX cash conversion rows — not taxable equity trades
        if asset_class_raw == "CASH":
            continue

        # Skip options — derivatives KZ (982/993/893–896) deferred intentionally
        if asset_class_raw == "OPT":
            opt_skipped += 1
            continue

        action = row.get("Buy/Sell", "").strip().upper()
        if action not in ("BUY", "SELL"):
            continue

        try:
            trade_date = _parse_ib_date(
                row.get("DateTime") or row.get("Date/Time") or row.get("TradeDate", "")
            )
        except Exception:
            continue

        currency   = (row.get("CurrencyPrimary") or row.get("Currency") or "").strip()
        quantity   = _parse_decimal(row.get("Quantity", "0"))
        price      = _parse_decimal(row.get("TradePrice") or row.get("T. Price") or "0")
        proceeds   = _parse_decimal(row.get("Proceeds", "0"))
        commission = _parse_decimal(
            row.get("IBCommission") or row.get("Comm/Fee") or "0"
        ).copy_abs()
        symbol      = row.get("Symbol", "").strip()
        isin        = (row.get("ISIN") or "").strip() or None
        description = row.get("Description", "").strip()
        exchange    = row.get("Exchange", "").strip()

        symbol = _normalize_de_symbol(symbol, isin)

        country_code = _country_from_isin(isin) if isin else None
        domicile     = _classify_domicile(isin, country_code, exchange)
        asset_class  = IB_ASSET_CLASS_MAP.get(asset_class_raw, AssetClass.OTHER)

        # Capture IB's FIFO PnL for SELL cross-check (HEADER/DATA format only)
        broker_fifo_pnl_eur = None
        if action == "SELL":
            raw_pnl = row.get("FifoPnlRealized", "").strip()
            if raw_pnl and raw_pnl not in ("", "0"):
                try:
                    fx = _parse_decimal(row.get("FXRateToBase", "1") or "1")
                    broker_fifo_pnl_eur = _parse_decimal(raw_pnl) * fx
                except Exception:
                    pass

        txn = NormalizedTransaction(
            broker="ib",
            raw_id=f"ib_trade_{trade_date}_{symbol}_{action}_{proceeds}_{quantity}_{row.get('CostBasis','0')}",
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
            broker_fifo_pnl_eur=broker_fifo_pnl_eur,
            source_file=source,
        )
        results.append(txn)

    if opt_skipped:
        print(f"  [warn]   IB: {opt_skipped} OPT row(s) skipped in {Path(source).name} "
              f"— derivatives KZ (982/993) not yet implemented")

    return results


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_ib_date(s: str) -> date:
    if not s:
        raise ValueError("Empty date string")
    # IB Flex uses semicolon as date/time separator e.g. "2025-01-02;07:43:28"
    # Classic format uses comma e.g. "2025-01-02, 07:43:28"
    s = s.strip().replace(";", " ").split(",")[0].strip()
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


# ── Cash Report ───────────────────────────────────────────────────────────────

def parse_ibkr_cash_report(path: Path) -> Optional[Decimal]:
    """Parse the CRTT (Cash Report) section and return total cash in base currency.

    Uses the BASE_SUMMARY row which IB pre-converts to the account's base currency
    (assumes EUR; for non-EUR-base accounts the returned value would need FX).
    Returns None if no Cash Report section is found or BASE_SUMMARY is absent.
    """
    rows = _read_cash_report_section(path)
    for row in rows:
        if row.get("CurrencyPrimary", "").strip() == "BASE_SUMMARY":
            try:
                val = Decimal(row.get("EndingCash", "").strip())
            except InvalidOperation:
                log.warning("ibkr-cash: unparseable BASE_SUMMARY EndingCash in %s", path.name)
                return None
            if val > ZERO:
                log.info("ibkr-cash: %s EUR cash from %s", val, path.name)
                return val
    return None


def parse_ibkr_interest(path: Path, year: int) -> Decimal:
    """Parse the CTRN section and return total cash interest income for the given year in EUR.

    Identifies 'Broker Interest Received' rows and extracts the year from the description
    (e.g. 'EUR CREDIT INT FOR MAY-2025' → 2025).  Non-EUR amounts are converted using
    IB's FXRateToBase column (same base-currency assumption as parse_ibkr_cash_report).
    Returns ZERO if no interest rows are found for the given year.
    """
    total = sum((amt for _, amt in _iter_interest_rows(path, year)), ZERO)
    if total > ZERO:
        log.info("ibkr-interest: EUR %.2f interest for %d from %s", total, year, path.name)
    return total


def _iter_interest_rows(path: Path, year: int):
    """Yield ((currency, description), eur_amount) for each interest row in target year.

    Used by the pipeline for cross-file deduplication: the same monthly payment
    appears identically in multiple IB export files (flex query + annual TT-AUT
    exports).  Callers deduplicate by the returned key before summing.
    """
    for row in _read_ctrn_section(path):
        if row.get("Type", "").strip() != "Broker Interest Received":
            continue
        desc = row.get("Description", "")
        m = _INTEREST_YEAR_RE.search(desc)
        if not m or int(m.group(1)) != year:
            continue
        currency = row.get("CurrencyPrimary", "").strip()
        try:
            amount = Decimal(row.get("Amount", "0").strip().replace(",", ""))
            fx     = Decimal(row.get("FXRateToBase", "1").strip().replace(",", "") or "1")
        except InvalidOperation:
            log.warning("ibkr-interest: unparseable row in %s: %s", path.name, row)
            continue
        if amount > ZERO:
            yield (currency, desc), (amount * fx).quantize(Decimal("0.01"))


def _read_cash_report_section(path: Path) -> list[dict]:
    return _read_ibkr_section(path, _CASH_REPORT_SECTION_NAMES)


def _read_ctrn_section(path: Path) -> list[dict]:
    return _read_ibkr_section(path, _CTRN_SECTION_NAMES)


def _read_ibkr_section(path: Path, section_names: set) -> list[dict]:
    """Read all rows from a named section of an IB Flex CSV file.

    Supports BOS/EOS (TT-AUT), HEADER/DATA (Flex Query), and Classic formats.
    """
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

            # ── BOS/EOS format ────────────────────────────────────────────────
            if marker == "BOS":
                if col1 in section_names:
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
                if col1 in section_names:
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
                if marker in section_names:
                    headers = [c.strip() for c in row[2:]]
                    in_section = True
                elif in_section:
                    in_section = False
                continue

            if col1 == "Data" and in_section:
                rows.append(dict(zip(headers, [c.strip() for c in row[2:]])))

    return rows
