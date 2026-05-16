"""
Nichtmeldefonds (unregistered fund) tax calculation — § 186 InvFG.

Applies to funds NOT registered with OeKB: US REITs, BDCs, most foreign ETFs.

Tax base per position per year (pauschal ermittelte AE):
  AE/share = max(
      90% × (Dec31_price - Jan1_price),   # 90% of annual price gain
      10% × Dec31_price                   # minimum regardless of performance
  )
  Total AE (EUR) = AE/share × shares_held × FX_rate_Dec31
  KeSt = 27.5% × Total AE (EUR)

The AE also increases the steuerliche Anschaffungskosten (cost basis) by the same amount,
preventing double-taxation when the position is eventually sold.

Prices must be configured manually in config.yaml (nichtmeldefonds[].dec31_prices).
Shares held are inferred automatically from broker transaction history.

Limitation: mid-year purchases should technically use purchase price as the start
price for those lots, not Jan 1. V1 uses Dec 31 prior year for all lots (conservative,
consistent with most consultant practice). Can be refined in a future version.
"""

import logging
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from core.models import NichtmeldefondsResult, NormalizedTransaction, TransactionType
from core.price_fetcher import get_year_end_price

log = logging.getLogger(__name__)
ZERO      = Decimal("0")
TWO       = Decimal("0.01")
KEST_RATE = Decimal("0.275")
NINETY_PCT = Decimal("0.9")
TEN_PCT    = Decimal("0.1")


def calculate_nichtmeldefonds(
    config: dict,
    tax_year: int,
    all_transactions: list[NormalizedTransaction],
    fx,                             # FXRateProvider — avoid circular import
) -> list[NichtmeldefondsResult]:
    """
    Calculate pauschal AE for every configured Nichtmeldefonds position.
    Returns one NichtmeldefondsResult per position that had shares at year-end.
    """
    nmf_config = config.get("nichtmeldefonds", [])
    if not nmf_config:
        return []

    price_cache_dir = config.get("price_cache_dir", "./cache/price_cache")
    results = []
    for entry in nmf_config:
        result = _calc_position(entry, tax_year, all_transactions, fx, price_cache_dir)
        if result is not None:
            results.append(result)

    return results


def _calc_position(
    entry: dict,
    tax_year: int,
    all_transactions: list[NormalizedTransaction],
    fx,
    price_cache_dir: str = "./cache/price_cache",
) -> NichtmeldefondsResult | None:
    symbol    = entry.get("symbol", "")
    isin      = entry.get("isin", "")
    name      = entry.get("name", symbol)
    fund_type = entry.get("type", "FUND").upper()
    currency  = entry.get("currency", "USD").upper()
    cache_dir = price_cache_dir

    # Manual overrides in config take precedence; auto-fetch fills the rest
    manual_prices = {str(k): Decimal(str(v)) for k, v in entry.get("dec31_prices", {}).items()}

    override_map = {str(k): Decimal(str(v)) for k, v in entry.get("shares_held_override", {}).items()}
    if str(tax_year) in override_map:
        shares = override_map[str(tax_year)]
        log.debug(f"NMF {symbol}: using shares_held_override for {tax_year}: {shares}")
    else:
        shares = _net_shares_at_year_end(all_transactions, symbol, tax_year)
    if shares <= ZERO:
        log.debug(f"NMF {symbol}: no shares held at end of {tax_year}, skipping")
        return None

    price_dec31 = manual_prices.get(str(tax_year)) or get_year_end_price(symbol, currency, tax_year, cache_dir)
    price_jan1  = manual_prices.get(str(tax_year - 1)) or get_year_end_price(symbol, currency, tax_year - 1, cache_dir)

    # FX rate on Dec 31 (ECB may not publish on weekends — provider falls back to last available)
    dec31_date = date(tax_year, 12, 31)
    fx_dec31   = fx.get_rate(currency, dec31_date) or ZERO

    warning = ""
    if not price_dec31 or price_dec31 == ZERO:
        warning = (f"Could not determine Dec 31 {tax_year} price for {symbol} "
                   f"— yfinance fetch failed and no manual dec31_prices override set")
        log.warning(f"NMF {symbol}: {warning}")
        return NichtmeldefondsResult(
            symbol=symbol, isin=isin, name=name, fund_type=fund_type,
            currency=currency, shares_held=shares,
            price_jan1=price_jan1, price_dec31=None, fx_dec31=fx_dec31,
            warning=warning,
        )

    if not price_jan1 or price_jan1 == ZERO:
        warning = (f"No prior-year price for {symbol} {tax_year - 1} "
                   f"— using 10% minimum only (may understate if price rose significantly)")
        log.warning(f"NMF {symbol}: {warning}")
        price_jan1 = ZERO

    annual_gain   = max(ZERO, price_dec31 - price_jan1)
    ae_90         = (annual_gain * NINETY_PCT).quantize(TWO, ROUND_HALF_UP)
    ae_10         = (price_dec31 * TEN_PCT).quantize(TWO, ROUND_HALF_UP)
    ae_per_share  = max(ae_90, ae_10)

    ae_native = (ae_per_share * shares).quantize(TWO, ROUND_HALF_UP)
    ae_eur    = (ae_native * fx_dec31).quantize(TWO, ROUND_HALF_UP)
    kest_eur  = (ae_eur * KEST_RATE).quantize(TWO, ROUND_HALF_UP)

    return NichtmeldefondsResult(
        symbol=symbol,
        isin=isin,
        name=name,
        fund_type=fund_type,
        currency=currency,
        shares_held=shares,
        price_jan1=price_jan1 if price_jan1 > ZERO else None,
        price_dec31=price_dec31,
        fx_dec31=fx_dec31 if fx_dec31 > ZERO else None,
        annual_gain_per_share=annual_gain,
        ae_90pct_per_share=ae_90,
        ae_10pct_per_share=ae_10,
        ae_per_share=ae_per_share,
        ae_total_native=ae_native,
        ae_total_eur=ae_eur,
        kest_due_eur=kest_eur,
        cost_basis_adj_eur=ae_eur,
        warning=warning,
    )


def compute_nmf_cumulative_ae(
    config: dict,
    tax_year: int,
    all_transactions: list,
    fx,
    price_cache_dir: str = "./cache/price_cache",
) -> "dict[str, Decimal]":
    """
    Returns {symbol: cumulative_ae_eur} for each configured NMF symbol.

    Sums ae_total_eur from the symbol's first purchase year through tax_year-1
    (prior years only — AE is assessed only on Dec-31 holdings; a mid-year sale
    means no AE charge for that year).

    Used by TaxEngine to adjust FIFO lot cost basis before sell matching.
    """
    nmf_config = config.get("nichtmeldefonds", [])
    result: dict[str, Decimal] = {}
    for entry in nmf_config:
        symbol = entry.get("symbol", "")
        purchase_year = _get_nmf_purchase_year(symbol, config, all_transactions, tax_year)
        cum_ae = ZERO
        for year in range(purchase_year, tax_year):
            yr = _calc_position(entry, year, all_transactions, fx, price_cache_dir)
            if yr and yr.ae_total_eur:
                cum_ae += yr.ae_total_eur
        if cum_ae > ZERO:
            result[symbol] = cum_ae.quantize(TWO, ROUND_HALF_UP)
    return result


def _get_nmf_purchase_year(
    symbol: str,
    config: dict,
    all_transactions: list,
    fallback: int,
) -> int:
    """Earliest purchase year for an NMF symbol."""
    from core.models import TransactionType as _TT
    earliest = None
    for lot in config.get("manual_cost_basis", []):
        if lot.get("symbol") != symbol:
            continue
        pd_str = str(lot.get("purchase_date", ""))
        if pd_str and len(pd_str) >= 4:
            yr = int(pd_str[:4])
            if earliest is None or yr < earliest:
                earliest = yr
    if earliest is not None:
        return earliest
    years = [t.trade_date.year for t in all_transactions
             if t.symbol == symbol and t.txn_type == _TT.BUY]
    return min(years) if years else fallback


def _net_shares_at_year_end(
    transactions: list[NormalizedTransaction],
    symbol: str,
    tax_year: int,
) -> Decimal:
    """Net shares held at Dec 31 of tax_year, accumulated over all available history."""
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
