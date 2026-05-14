"""
E*TRADE PDF statement parser.

Two format generations:

  Old (2020-2021): E*TRADE Securities LLC, quarterly
    - "SECURITIES PURCHASED OR SOLD": Sold/Bought rows with qty + price
    - "OTHER ACTIVITY": Receive rows (RSU vestings, net qty after sell-to-cover, no price)
    - "DIVIDENDS & INTEREST ACTIVITY": dividend rows

  New (2024+): E*TRADE from Morgan Stanley, monthly
    - "CASH FLOW ACTIVITY BY DATE": Sold/Bought rows + Dividend rows
    - "SECURITY TRANSFERS" (page 8 / December annual recap): Transfer into Account rows
      (RSU vestings, net qty + FMV amount)

RSU cost basis:
  Old format: yfinance close price on vesting date (no price in "Receive" row)
  New format: amount / qty from Security Transfers entry

Sell-to-cover shares do NOT appear in these statements — NXP payroll withholds them
off-statement. Only net-issued shares appear as Transfer into Account / Receive.
So the FIFO queue only sees net shares on the buy side, which is consistent with no
matching sell-to-cover rows on the sell side.

NXPI metadata (hardcoded — the only stock in this account):
  Full name: NXP SEMICONDUCTORS NV
  ISIN: NL0009538784 (Netherlands)
  WHT source country: NL, treaty rate 15 %
"""

import logging
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional

from core.models import AssetClass, Domicile, NormalizedTransaction, TransactionType

log = logging.getLogger(__name__)
ZERO = Decimal("0")

# ── Constants ────────────────────────────────────────────────────────────────
NXPI_ISIN        = "NL0009538784"
NXPI_SYMBOL      = "NXPI"
NXPI_DESCRIPTION = "NXP SEMICONDUCTORS NV"
NXPI_COUNTRY     = "NL"
NL_WHT_RATE      = Decimal("0.15")

BROKER_ID_OLD = "etrade"
BROKER_ID_NEW = "etrade"

# Account number patterns (extracted from statement text — never hardcoded)
# Old format: "NNNN-NNNN"   New format: "NNN-NNNNNN-NNN"
_ACCOUNT_RE = re.compile(r"\b(\d{3,4}-\d{4,8}-\d{3}|\d{4}-\d{4})\b")


# ── Detection ────────────────────────────────────────────────────────────────

def detect(path: Path) -> bool:
    if path.suffix.lower() != ".pdf":
        return False
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            if not pdf.pages:
                return False
            # Old format (2020-2021): "E*TRADE Securities" is CID-encoded on page 1 but
            # appears in plain text on later pages. Check first + last 2 pages.
            pages = pdf.pages
            sample = list(pages[:1]) + list(pages[-2:]) if len(pages) > 2 else list(pages)
            for page in sample:
                text = page.extract_text() or ""
                if "E*TRADE" in text or "ETRADE" in text:
                    return True
        return False
    except Exception:
        return False


# ── Entry point ───────────────────────────────────────────────────────────────

def parse(path: Path, config: dict) -> tuple[list[NormalizedTransaction], str | None]:
    try:
        import pdfplumber
    except ImportError:
        raise ImportError("pdfplumber is required for E*Trade PDFs. "
                          "Run: pip install pdfplumber")

    with pdfplumber.open(path) as pdf:
        pages_text = [p.extract_text() or "" for p in pdf.pages]

    full_text = "\n".join(pages_text)
    fmt = _detect_format(full_text)
    source = path.name

    skip_dates = {date.fromisoformat(d) for d in config.get("etrade_skip_transfers", [])}

    if fmt == "old":
        txns, account_id = _parse_old(full_text, source)
    elif fmt == "new":
        txns, account_id = _parse_new(pages_text, source, skip_dates)
    else:
        log.warning(f"[etrade] Unrecognised E*TRADE statement format: {path.name}")
        return [], None

    log.info(f"[etrade] {path.name}: {len(txns)} transactions (format={fmt}, acct={account_id})")
    return txns, account_id


# ── Format detection ──────────────────────────────────────────────────────────

def _detect_format(text: str) -> str:
    if "Morgan Stanley" in text:
        return "new"
    if "E*TRADE Securities" in text:
        return "old"
    if "E*TRADE" in text or "ETRADE" in text:
        return "new"   # default to new if ambiguous
    return "unknown"


# ══════════════════════════════════════════════════════════════════════════════
# OLD FORMAT (2020-2021, E*TRADE Securities LLC, quarterly)
# ══════════════════════════════════════════════════════════════════════════════

# Trade date: MM/DD/YY  e.g.  09/08/20
_OLD_DATE_RE = re.compile(r"\b(\d{2}/\d{2}/\d{2})\b")

# Securities Purchased or Sold row:
#   09/08/20 09/10/20 ***NXP SEMICONDUCTORS NXPI Sold -56 120.5000 6,737.90
# or Bought:
#   01/15/21 01/19/21 ***SOME CORP       TICK  Bought  100  50.1200  5,012.00
_OLD_TRADE_RE = re.compile(
    r"^(\d{2}/\d{2}/\d{2})"     # trade date
    r"\s+\d{2}/\d{2}/\d{2}"     # settlement date (discarded)
    r"\s+\*{0,3}(.+?)\s+"       # description (non-greedy)
    r"(\w+)\s+"                  # symbol
    r"(Sold|Bought)\s+"          # transaction type
    r"([-\d.]+)\s+"              # quantity (negative for sells)
    r"([\d.]+)\s+"               # price
    r"([\d,]+\.\d+)$",           # amount (sold or purchased — only one column is non-empty)
    re.MULTILINE,
)

# Other Activity (RSU vesting) row:
#   09/02/20 ***NXP SEMICONDUCTORS N V NXPI Receive 56.6151
_OLD_RECEIVE_RE = re.compile(
    r"^(\d{2}/\d{2}/\d{2})"     # date
    r"\s+\*{0,3}.+?"             # description
    r"\s+(\w+)\s+Receive\s+"     # symbol
    r"([\d.]+)",                 # quantity
    re.MULTILINE,
)

# Dividend row (old format):
#   01/15/21  Dividend  NXP SEMICONDUCTORS NV  NXPI  85.00
# or just interest on cash — we skip those (no symbol = cash interest)
_OLD_DIV_RE = re.compile(
    r"^(\d{2}/\d{2}/\d{2})\s+"
    r"(?:Dividend|Qualified Dividend)\s+"
    r"(.+?)\s+"
    r"(\w+)\s+"         # symbol
    r"([\d,]+\.\d+)$",
    re.MULTILINE,
)


def _parse_old(text: str, source: str) -> tuple[list[NormalizedTransaction], str]:
    txns: list[NormalizedTransaction] = []

    # ── Determine statement year(s) from period header ─────────────────────
    # "July 1, 2020 - September 30, 2020"  →  year map from MM/DD/YY dates
    # We convert 2-digit years using the century pivot: YY <= 30 → 2000+YY else 1900+YY
    def _parse_old_date(s: str) -> date:
        m, d, y2 = s.split("/")
        yr = 2000 + int(y2) if int(y2) <= 30 else 1900 + int(y2)
        return date(yr, int(m), int(d))

    account_id = _extract_account_id(text)

    # ── Securities Purchased or Sold ───────────────────────────────────────
    # Only parse rows that fall between "TRANSACTION HISTORY" and "WITHDRAWALS"
    txn_section = _extract_section(text,
                                   start_markers=["TRANSACTION HISTORY"],
                                   end_markers=["WITHDRAWALS", "OTHER ACTIVITY",
                                                "DIVIDENDS & INTEREST"])
    for m in _OLD_TRADE_RE.finditer(txn_section):
        trade_date_str, desc, symbol, txn_type, qty_str, price_str, amount_str = m.groups()
        try:
            trade_date = _parse_old_date(trade_date_str)
            qty = abs(Decimal(qty_str))
            price = Decimal(price_str)
            amount = Decimal(amount_str.replace(",", ""))
        except (InvalidOperation, ValueError) as e:
            log.warning(f"[etrade-old] Skipping unparseable trade row: {m.group()!r} ({e})")
            continue

        t = TransactionType.SELL if txn_type == "Sold" else TransactionType.BUY
        raw_id = f"etrade_old_{trade_date.isoformat()}_{symbol}_{txn_type}_{qty}"
        txns.append(NormalizedTransaction(
            broker=BROKER_ID_OLD,
            raw_id=raw_id,
            trade_date=trade_date,
            settle_date=None,
            txn_type=t,
            asset_class=AssetClass.STOCK,
            symbol=symbol,
            isin=NXPI_ISIN if symbol == NXPI_SYMBOL else None,
            description=desc.strip(),
            country_code=NXPI_COUNTRY if symbol == NXPI_SYMBOL else None,
            domicile=Domicile.FOREIGN,
            quantity=qty,
            price=price,
            price_currency="USD",
            orig_currency="USD",
            orig_amount=amount if t == TransactionType.SELL else -amount,
            source_file=source,
        ))

    # ── Other Activity — RSU vestings (Receive) ────────────────────────────
    other_section = _extract_section(text,
                                     start_markers=["OTHER ACTIVITY", "OTHERACTIVITY"],
                                     end_markers=["PAGE ", "\f"])
    for m in _OLD_RECEIVE_RE.finditer(other_section):
        vest_date_str, symbol, qty_str = m.groups()
        if symbol != NXPI_SYMBOL:
            continue
        try:
            vest_date = _parse_old_date(vest_date_str)
            qty = Decimal(qty_str)
        except (InvalidOperation, ValueError) as e:
            log.warning(f"[etrade-old] Skipping RSU receive row: {m.group()!r} ({e})")
            continue

        price = _get_price_on_date(NXPI_SYMBOL, vest_date)
        if price is None:
            log.warning(f"[etrade] Could not fetch NXPI price for {vest_date}; "
                        "RSU vesting cost basis set to 0 — update via manual_cost_basis")
            price = ZERO

        raw_id = f"etrade_old_rsu_{vest_date.isoformat()}_{qty}"
        txns.append(NormalizedTransaction(
            broker=BROKER_ID_OLD,
            raw_id=raw_id,
            trade_date=vest_date,
            settle_date=None,
            txn_type=TransactionType.BUY,
            asset_class=AssetClass.STOCK,
            symbol=NXPI_SYMBOL,
            isin=NXPI_ISIN,
            description=NXPI_DESCRIPTION,
            country_code=NXPI_COUNTRY,
            domicile=Domicile.FOREIGN,
            quantity=qty,
            price=price,
            price_currency="USD",
            orig_currency="USD",
            orig_amount=-(qty * price),
            source_file=source,
            notes="RSU vest (net shares after sell-to-cover)",
        ))

    # ── Dividends ──────────────────────────────────────────────────────────
    div_section = _extract_section(text,
                                   start_markers=["DIVIDENDS & INTEREST ACTIVITY",
                                                  "DIVIDENDS&INTEREST"],
                                   end_markers=["TOTAL DIVIDENDS", "WITHDRAWALS",
                                                "OTHER ACTIVITY", "PAGE "])
    for m in _OLD_DIV_RE.finditer(div_section):
        d_str, desc, symbol, amount_str = m.groups()
        if symbol == "00099A109":   # sweep fund, skip
            continue
        try:
            d = _parse_old_date(d_str)
            amount = Decimal(amount_str.replace(",", ""))
        except (InvalidOperation, ValueError):
            continue
        raw_id = f"etrade_old_div_{d.isoformat()}_{symbol}_{amount_str}"
        txns.append(NormalizedTransaction(
            broker=BROKER_ID_OLD,
            raw_id=raw_id,
            trade_date=d,
            settle_date=None,
            txn_type=TransactionType.DIVIDEND,
            asset_class=AssetClass.STOCK,
            symbol=symbol,
            isin=NXPI_ISIN if symbol == NXPI_SYMBOL else None,
            description=desc.strip(),
            country_code=NXPI_COUNTRY if symbol == NXPI_SYMBOL else None,
            domicile=Domicile.FOREIGN,
            quantity=None, price=None, price_currency=None,
            orig_currency="USD",
            orig_amount=amount,
            source_file=source,
        ))

    return txns, account_id


# ══════════════════════════════════════════════════════════════════════════════
# NEW FORMAT (2024+, E*TRADE from Morgan Stanley, monthly)
# ══════════════════════════════════════════════════════════════════════════════

# Statement period header (appears on page 1 and again on data pages):
#   "For the Period February 1-29, 2024"
#   "For the Period August 1- September30, 2024"
#   "For the Period November 1-30, 2024"
_PERIOD_YEAR_RE = re.compile(
    r"For the Period .+?(\d{4})",
    re.IGNORECASE,
)

# CASH FLOW ACTIVITY BY DATE — Sold / Bought row:
#   "2/22 2/26 Sold NXP SEMICONDUCTORS NV ACTED AS AGENT 41.000 240.2325 9,849.45"
# Settlement date may be absent (just one date) for same-day transactions.
# The Credits/(Debits) amount is always positive for Sold (cash credit).
_NEW_TRADE_RE = re.compile(
    r"^(\d{1,2}/\d{1,2})"           # activity date (M/D)
    r"(?:\s+\d{1,2}/\d{1,2})?"      # optional settlement date
    r"\s+(Sold|Bought)"              # transaction type
    r"\s+(.+?)\s+"                   # description
    r"(?:ACTED AS AGENT\s+)?"        # optional agency marker
    r"([\d.]+)\s+"                   # quantity
    r"([\d.]+)\s+"                   # price
    r"([\d,]+\.\d+)$",               # amount
    re.MULTILINE,
)

# Qualified Dividend row:
#   "7/10 Qualified Dividend NXP SEMICONDUCTORS NV 75.85"
_NEW_QUAL_DIV_RE = re.compile(
    r"^(\d{1,2}/\d{1,2})\s+Qualified Dividend\s+(.+?)\s+([\d,]+\.\d+)$",
    re.MULTILINE,
)

# Dividend row with WHT info (two sub-lines):
#   "7/10 Dividend NXP SEMICONDUCTORS NV 0.00"
#   "ADJ GROSS DIV AMOUNT 13.38"
#   "FOREIGN TAX PAID IS 13.38"
_NEW_DIV_RE = re.compile(
    r"^(\d{1,2}/\d{1,2})\s+Dividend\s+(.+?)\s+0\.00\n"
    r"ADJ GROSS DIV AMOUNT\s+([\d.]+)\n"
    r"FOREIGN TAX PAID IS\s+([\d.]+)",
    re.MULTILINE,
)

# Security Transfers — Transfer into Account row (RSU vesting, net shares):
#   "11/1 Transfer into Account NXP SEMICONDUCTORS NV 28.000 $6,680.52"
#   "11/7 Transfer into Account NXP SEMICONDUCTORS NV 22.000 5,194.64"
_NEW_TRANSFER_RE = re.compile(
    r"^(\d{1,2}/\d{1,2})\s+Transfer into Account\s+(.+?)\s+([\d.]+)\s+\$?([\d,]+\.\d+)$",
    re.MULTILINE,
)


def _parse_new(pages_text: list[str], source: str,
               skip_transfer_dates: set = None) -> tuple[list[NormalizedTransaction], str]:
    txns: list[NormalizedTransaction] = []
    full_text = "\n".join(pages_text)

    # ── Statement year ─────────────────────────────────────────────────────
    ym = _PERIOD_YEAR_RE.search(full_text)
    stmt_year = int(ym.group(1)) if ym else date.today().year
    log.debug(f"[etrade-new] Statement year: {stmt_year} ({source})")

    account_id = _extract_account_id(full_text)

    def _new_date(md: str) -> date:
        """Convert 'M/D' to date using statement year; handle Dec→Jan year boundary."""
        parts = md.split("/")
        m, d = int(parts[0]), int(parts[1])
        # If December statement and we see Jan dates, use stmt_year+1
        if m == 1 and stmt_year and _stmt_month(full_text) == 12:
            return date(stmt_year + 1, m, d)
        return date(stmt_year, m, d)

    # ── Cash Flow Activity — Sold / Bought ─────────────────────────────────
    activity_text = _extract_section(full_text,
                                     start_markers=["CASH FLOW ACTIVITY BY DATE"],
                                     end_markers=["NET CREDITS/(DEBITS)",
                                                  "MONEY MARKET FUND"])
    for m in _NEW_TRADE_RE.finditer(activity_text):
        act_date_str, txn_type, desc, qty_str, price_str, amount_str = m.groups()
        try:
            act_date = _new_date(act_date_str)
            qty = Decimal(qty_str)
            price = Decimal(price_str)
            amount = Decimal(amount_str.replace(",", ""))
        except (InvalidOperation, ValueError) as e:
            log.warning(f"[etrade-new] Skipping unparseable trade: {m.group()!r} ({e})")
            continue

        t = TransactionType.SELL if txn_type == "Sold" else TransactionType.BUY
        raw_id = f"etrade_new_{act_date.isoformat()}_{txn_type}_{qty}_{price}"
        is_nxpi = "NXP" in desc.upper()
        txns.append(NormalizedTransaction(
            broker=BROKER_ID_NEW,
            raw_id=raw_id,
            trade_date=act_date,
            settle_date=None,
            txn_type=t,
            asset_class=AssetClass.STOCK,
            symbol=NXPI_SYMBOL if is_nxpi else desc.split()[0],
            isin=NXPI_ISIN if is_nxpi else None,
            description=desc.strip(),
            country_code=NXPI_COUNTRY if is_nxpi else None,
            domicile=Domicile.FOREIGN,
            quantity=qty,
            price=price,
            price_currency="USD",
            orig_currency="USD",
            orig_amount=amount if t == TransactionType.SELL else -amount,
            source_file=source,
        ))

    # ── Cash Flow Activity — Qualified Dividends + WHT ─────────────────────
    # Pair each Qualified Dividend with its corresponding Dividend (WHT) row.
    # Strategy: collect all WHT entries by date, then attach to matching div.
    wht_by_date: dict[str, Decimal] = {}
    for m in _NEW_DIV_RE.finditer(activity_text):
        d_str, _desc, _gross, wht_str = m.groups()
        wht_by_date[d_str] = Decimal(wht_str)

    for m in _NEW_QUAL_DIV_RE.finditer(activity_text):
        d_str, desc, amount_str = m.groups()
        if "TREASURY" in desc.upper():   # skip money-market sweep income
            continue
        try:
            d = _new_date(d_str)
            net_amount = Decimal(amount_str.replace(",", ""))
        except (InvalidOperation, ValueError):
            continue

        wht = wht_by_date.get(d_str, ZERO)
        gross = net_amount + wht
        is_nxpi = "NXP" in desc.upper()
        raw_id = f"etrade_new_div_{d.isoformat()}_{desc[:8]}_{amount_str}"
        txns.append(NormalizedTransaction(
            broker=BROKER_ID_NEW,
            raw_id=raw_id,
            trade_date=d,
            settle_date=None,
            txn_type=TransactionType.DIVIDEND,
            asset_class=AssetClass.STOCK,
            symbol=NXPI_SYMBOL if is_nxpi else desc.split()[0],
            isin=NXPI_ISIN if is_nxpi else None,
            description=desc.strip(),
            country_code=NXPI_COUNTRY if is_nxpi else None,
            domicile=Domicile.FOREIGN,
            quantity=None, price=None, price_currency=None,
            orig_currency="USD",
            orig_amount=gross,
            wht_amount_orig=wht,
            wht_rate_actual=NL_WHT_RATE if is_nxpi and wht > ZERO else None,
            source_file=source,
        ))

    # ── Security Transfers — RSU vestings (all pages) ──────────────────────
    # These appear on page 8 of monthly statements and page 11 of December recap.
    for page_text in pages_text:
        if "SECURITY TRANSFERS" not in page_text and "Transfer into Account" not in page_text:
            continue
        sec_transfer_text = _extract_section(
            page_text,
            start_markers=["SECURITY TRANSFERS"],
            end_markers=["TOTAL SECURITY TRANSFERS", "MESSAGES", "PAGE "],
        )
        for m in _NEW_TRANSFER_RE.finditer(sec_transfer_text):
            d_str, desc, qty_str, amount_str = m.groups()
            try:
                d = _new_date(d_str)
                qty = Decimal(qty_str)
                fmv_total = Decimal(amount_str.replace(",", ""))
                price = (fmv_total / qty).quantize(Decimal("0.0001"))
            except (InvalidOperation, ValueError, ZeroDivisionError) as e:
                log.warning(f"[etrade-new] Skipping RSU transfer: {m.group()!r} ({e})")
                continue

            if skip_transfer_dates and d in skip_transfer_dates:
                log.info(f"[etrade-new] Skipping account-migration transfer on {d} "
                         f"({qty} shares of {desc.strip()}) — cost basis carried from original lots")
                continue

            is_nxpi = "NXP" in desc.upper()
            raw_id = f"etrade_new_rsu_{d.isoformat()}_{qty}"
            txns.append(NormalizedTransaction(
                broker=BROKER_ID_NEW,
                raw_id=raw_id,
                trade_date=d,
                settle_date=None,
                txn_type=TransactionType.BUY,
                asset_class=AssetClass.STOCK,
                symbol=NXPI_SYMBOL if is_nxpi else desc.split()[0],
                isin=NXPI_ISIN if is_nxpi else None,
                description=desc.strip(),
                country_code=NXPI_COUNTRY if is_nxpi else None,
                domicile=Domicile.FOREIGN,
                quantity=qty,
                price=price,
                price_currency="USD",
                orig_currency="USD",
                orig_amount=-fmv_total,
                source_file=source,
                notes="RSU vest (net shares after sell-to-cover)",
            ))

    return txns, account_id


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _extract_account_id(text: str) -> str:
    """Extract the brokerage account number from statement text."""
    m = _ACCOUNT_RE.search(text)
    return m.group(1) if m else ""


def _extract_section(text: str, start_markers: list[str], end_markers: list[str]) -> str:
    """Return the text between the first matching start marker and the first end marker."""
    start = -1
    for marker in start_markers:
        idx = text.find(marker)
        if idx != -1:
            start = idx + len(marker)
            break
    if start == -1:
        return ""
    sub = text[start:]
    for marker in end_markers:
        idx = sub.find(marker)
        if idx != -1:
            sub = sub[:idx]
    return sub


def _stmt_month(text: str) -> int:
    """Extract the primary statement month (1-12) from the period header."""
    months = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12,
    }
    m = re.search(r"For the Period\s+(\w+)", text, re.IGNORECASE)
    if m:
        return months.get(m.group(1).lower(), 1)
    return 1


def _get_price_on_date(symbol: str, target: date) -> Optional[Decimal]:
    """
    Fetch the closing price of `symbol` on `target` date via yfinance.
    Falls back to the previous trading day if target is a weekend/holiday.
    Results are NOT cached (arbitrary dates; use sparingly).
    """
    try:
        import yfinance as yf
    except ImportError:
        log.error("yfinance not installed; cannot fetch RSU vesting price")
        return None

    from datetime import timedelta
    start = target - timedelta(days=5)
    end   = target + timedelta(days=2)
    try:
        hist = yf.Ticker(symbol).history(
            start=start.isoformat(), end=end.isoformat(), auto_adjust=True
        )
    except Exception as e:
        log.warning(f"[etrade] yfinance error for {symbol} on {target}: {e}")
        return None

    if hist is None or hist.empty:
        return None

    hist.index = hist.index.date
    candidates = hist[hist.index <= target]
    if candidates.empty:
        return None

    price = Decimal(str(round(float(candidates.iloc[-1]["Close"]), 4)))
    log.info(f"[etrade] RSU vest price {symbol} {candidates.index[-1]}: ${price}")
    return price
