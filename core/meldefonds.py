"""
Meldefonds (OeKB-registered fund) AE calculation.

Applies to funds registered with OeKB: most UCITS ETFs (IE/LU domicile),
Austrian funds, and any foreign fund that filed with OeKB's tax representative.

Tax base per position per year (from OeKB Steuerliche Mitteilung):
  KeSt = 27.5% × AE_per_share × shares_held × FX
  WA (Withhaltungsabzug) = fund-internal foreign tax credit, reduces KeSt due.
  Net KeSt = max(0, KeSt_gross - WA_EUR)

KZ routing:
  AT-prefix ISIN → KZ 936 (inländisch)
  All other ISIN  → KZ 937 (ausländisch)  — most UCITS ETFs (IE, LU)

Distributing vs. accumulating:
  Both use the same formula. For ausschüttend funds, distributions are separately
  taxed via the broker (KZ 898); AE here = additional undistributed income.
  For thesaurierend funds, AE = all fund income (no cash distribution).

AE/WA figures must be manually sourced from my.oekb.at and entered in
data/oekb_ae.yaml. The module warns if an entry is missing or zero.

The ak_korrektur_per_share (cost basis adjustment from OeKB) is reported in the
output tab. Applying it to the FIFO cost basis is a future enhancement.
"""

import logging
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import yaml

from core.models import MeldefondsResult, NormalizedTransaction, TransactionType

log = logging.getLogger(__name__)

ZERO      = Decimal("0")
TWO       = Decimal("0.01")
KEST_RATE = Decimal("0.275")

_dataset_cache: dict | None = None


def _load_dataset(path: str) -> dict:
    global _dataset_cache
    if _dataset_cache is not None:
        return _dataset_cache
    p = Path(path)
    if not p.exists():
        log.warning(f"Meldefonds dataset not found: {path}")
        _dataset_cache = {}
        return _dataset_cache
    with open(p) as f:
        raw = yaml.safe_load(f) or {}
    # Filter out non-dict top-level values (comments become None entries in some parsers)
    _dataset_cache = {k: v for k, v in raw.items() if isinstance(v, dict)}
    log.debug(f"Meldefonds dataset loaded: {len(_dataset_cache)} ISINs from {path}")
    return _dataset_cache


def _reset_cache() -> None:
    """Clear the module-level dataset cache (used in tests)."""
    global _dataset_cache
    _dataset_cache = None


def calculate_meldefonds(
    config: dict,
    tax_year: int,
    all_transactions: list[NormalizedTransaction],
    fx,
) -> list[MeldefondsResult]:
    """
    Calculate AE/WA for every configured Meldefonds position.
    Returns one MeldefondsResult per position that had shares at year-end
    AND had AE/WA data in the curated dataset.
    """
    mf_config = config.get("meldefonds", [])
    if not mf_config:
        return []

    dataset_path = config.get("meldefonds_data_file", "./data/oekb_ae.yaml")
    dataset = _load_dataset(dataset_path)

    results = []
    for entry in mf_config:
        result = _calc_position(entry, tax_year, all_transactions, fx, dataset)
        if result is not None:
            results.append(result)
    return results


def _calc_position(
    entry: dict,
    tax_year: int,
    all_transactions: list[NormalizedTransaction],
    fx,
    dataset: dict,
) -> MeldefondsResult | None:
    isin   = entry.get("isin", "").strip()
    symbol = entry.get("symbol", "").strip()

    if not isin:
        log.warning("Meldefonds entry missing 'isin' — skipping")
        return None

    fund_data = dataset.get(isin)
    if fund_data is None:
        log.warning(f"Meldefonds ISIN {isin} not in dataset ({entry.get('symbol', '?')}) "
                    f"— add it to data/oekb_ae.yaml")
        return None

    # Metadata from dataset; config can override symbol
    ds_symbol = fund_data.get("symbol", isin)
    effective_symbol = symbol or ds_symbol
    name     = fund_data.get("name", isin)
    currency = fund_data.get("currency", "USD").upper()
    domicile = fund_data.get("domicile", "").upper()
    ertragsverwendung = fund_data.get("ertragsverwendung", "")
    kz = "936" if domicile.startswith("AT") else "937"

    year_data = (fund_data.get("data") or {}).get(tax_year)
    if year_data is None:
        log.warning(f"Meldefonds {isin} ({effective_symbol}): no data for {tax_year} "
                    f"in dataset — add entry to data/oekb_ae.yaml")
        return None

    ae_per_share  = Decimal(str(year_data.get("ae_per_share", 0)))
    wa_per_share  = Decimal(str(year_data.get("wa_per_share", 0)))
    ak_korrektur  = Decimal(str(year_data.get("ak_korrektur_per_share", 0)))
    meldedatum    = str(year_data.get("meldedatum", ""))

    # Shares held: infer from transaction history
    shares = _net_shares_at_year_end(all_transactions, effective_symbol, tax_year)
    if shares <= ZERO:
        # Try ISIN-based matching as fallback
        shares = _net_shares_by_isin(all_transactions, isin, tax_year)
    if shares <= ZERO:
        log.debug(f"Meldefonds {isin} ({effective_symbol}): no shares held at end of "
                  f"{tax_year} — skipping")
        return None

    # FX rate: use meldedatum if available, else Dec 31
    fx_date = _parse_date(meldedatum) or date(tax_year, 12, 31)
    fx_rate = fx.get_rate(currency, fx_date) or ZERO
    if fx_rate == ZERO:
        log.warning(f"Meldefonds {isin}: no FX rate for {currency} on {fx_date}")

    warning = ""
    if ae_per_share == ZERO:
        warning = (f"AE per share is zero for {isin} {tax_year} — "
                   f"verify on my.oekb.at (may be correct for ausschüttend funds)")
        log.info(f"Meldefonds {isin}: {warning}")

    ae_native = (ae_per_share * shares).quantize(TWO, ROUND_HALF_UP)
    wa_native = (wa_per_share * shares).quantize(TWO, ROUND_HALF_UP)

    ae_eur       = (ae_native * fx_rate).quantize(TWO, ROUND_HALF_UP)
    wa_eur       = (wa_native * fx_rate).quantize(TWO, ROUND_HALF_UP)
    kest_gross   = (ae_eur * KEST_RATE).quantize(TWO, ROUND_HALF_UP)
    kest_net     = max(ZERO, (kest_gross - wa_eur).quantize(TWO, ROUND_HALF_UP))

    return MeldefondsResult(
        isin=isin,
        symbol=effective_symbol,
        name=name,
        fund_type=fund_data.get("type", "ETF"),
        currency=currency,
        ertragsverwendung=ertragsverwendung,
        kz=kz,
        shares_held=shares,
        ae_per_share=ae_per_share,
        wa_per_share=wa_per_share,
        fx_rate=fx_rate if fx_rate > ZERO else None,
        ae_total_native=ae_native,
        wa_total_native=wa_native,
        ae_total_eur=ae_eur,
        wa_total_eur=wa_eur,
        kest_gross_eur=kest_gross,
        kest_net_eur=kest_net,
        ak_korrektur_eur=(ak_korrektur * shares).quantize(TWO, ROUND_HALF_UP),
        meldedatum=meldedatum,
        warning=warning,
    )


def _net_shares_at_year_end(
    transactions: list[NormalizedTransaction],
    symbol: str,
    tax_year: int,
) -> Decimal:
    """Net shares held at Dec 31 of tax_year, accumulated from all available history."""
    shares = ZERO
    for t in transactions:
        if t.symbol != symbol:
            continue
        if t.trade_date.year > tax_year:
            continue
        qty = (t.quantity or ZERO).copy_abs()
        if t.txn_type == TransactionType.BUY:
            shares += qty
        elif t.txn_type == TransactionType.SELL:
            shares -= qty
    return max(ZERO, shares)


def _net_shares_by_isin(
    transactions: list[NormalizedTransaction],
    isin: str,
    tax_year: int,
) -> Decimal:
    """Fallback: match by ISIN when the ticker in broker export differs from config."""
    shares = ZERO
    for t in transactions:
        if (t.isin or "").strip().upper() != isin.upper():
            continue
        if t.trade_date.year > tax_year:
            continue
        qty = (t.quantity or ZERO).copy_abs()
        if t.txn_type == TransactionType.BUY:
            shares += qty
        elif t.txn_type == TransactionType.SELL:
            shares -= qty
    return max(ZERO, shares)


def _parse_date(s: str) -> date | None:
    try:
        return date.fromisoformat(s)
    except (ValueError, TypeError):
        return None
