"""
AT Tax Efficiency Report — per-position analysis for Austrian investors.

Outputs three sections:
1. Nichtmeldefonds positions: annual KeSt burden, cumulative AE step-up,
   embedded P&L estimate, KeSt credit if underwater and sold this year.
2. Dividend payment frequency: monthly / quarterly / semi-annual / annual
   breakdown per symbol, derived from transaction history.
3. Summary: total NMF burden, top action items.
"""

import logging
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from core.models import NichtmeldefondsResult, TransactionType
from core.nichtmeldefonds import _calc_position

log = logging.getLogger(__name__)
ZERO = Decimal("0")
KEST_RATE = Decimal("0.275")
LINE = "─" * 70
DLINE = "═" * 70


# ── Public entry point ────────────────────────────────────────────────────────

def write_tax_efficiency_report(
    config: dict,
    tax_year: int,
    all_transactions: list,
    nmf_results: list,          # list[NichtmeldefondsResult] — current year
    portfolio_positions: list,  # list[PortfolioPosition] — from pipeline (unused for now)
    fx,                         # FXRateProvider
    output_path: Path,
) -> None:
    """Write the AT tax efficiency report to output_path."""
    lines = _build_report(config, tax_year, all_transactions,
                          nmf_results, portfolio_positions, fx)
    output_path.write_text("\n".join(lines), encoding="utf-8")


# ── Report builder ────────────────────────────────────────────────────────────

def _build_report(config, tax_year, all_transactions,
                  nmf_results, portfolio_positions, fx):
    person = config.get("person_label", "")
    title_person = f"  {person} —" if person else ""
    lines = [
        DLINE,
        f"  AT TAX EFFICIENCY REPORT{title_person} {tax_year}",
        DLINE,
        "",
        "  This report identifies structural tax inefficiencies in your portfolio.",
        "  It complements the WHT Reclaim Report (excess withholding tax refunds).",
        "",
    ]
    lines += _section_nmf(config, tax_year, all_transactions, nmf_results, fx)
    lines += _section_dividend_frequency(all_transactions)
    lines += _section_summary(config, tax_year, all_transactions, nmf_results, fx)
    lines.append("")
    return lines


# ── Section 1: Nichtmeldefonds ────────────────────────────────────────────────

def _section_nmf(config, tax_year, all_transactions, nmf_results, fx):
    lines = [
        DLINE,
        "  SECTION 1: NICHTMELDEFONDS POSITIONS (§ 186 InvFG)",
        DLINE,
        "",
        "  Punitive pauschal AE applies on top of normal dividend tax.",
        "  AE = max(90% × annual price gain, 10% × Dec31 price) per share.",
        "",
    ]

    if not nmf_results:
        lines += ["  No Nichtmeldefonds positions configured.", ""]
        return lines

    price_cache_dir = config.get("price_cache_dir", "./cache/price_cache")

    for result in nmf_results:
        sym = result.symbol
        lines.append(f"  {sym:<6} {result.name:<32}  ({result.fund_type})  {result.shares_held:,.0f} sh")
        lines.append(f"  {LINE}")

        if result.price_dec31 and result.ae_per_share:
            rule_tag = "90%" if result.ae_per_share == result.ae_90pct_per_share else "10% min"
            lines.append(f"  Annual AE/share  ({tax_year}):   {result.currency} {result.ae_per_share:>9.4f}"
                         f"  [{rule_tag}]")
            lines.append(f"  Annual AE total  ({tax_year}):   {result.currency} {result.ae_total_native:>11.2f}"
                         f"  →  EUR {result.ae_total_eur:>9.2f}")
            lines.append(f"  Annual KeSt      ({tax_year}):   EUR {result.kest_due_eur:>9.2f}")
        elif result.warning:
            lines.append(f"  ⚠ {result.warning}")
            lines.append("")
            continue

        # Embedded P&L
        emb = _calc_embedded_pnl(sym, config, tax_year, all_transactions, fx,
                                  price_cache_dir, result)
        if emb:
            cost, cum_ae, adj_cost, curr_val, pnl, credit = emb
            lines.append("")
            lines.append(f"  Cumulative AE step-up (all years):  EUR {cum_ae:>9.2f}")
            lines.append(f"  Original cost basis:                EUR {cost:>9.2f}")
            lines.append(f"  Adjusted cost basis (cost + AE):    EUR {adj_cost:>9.2f}")
            lines.append(f"  Current market value (Dec 31 {tax_year}): EUR {curr_val:>9.2f}")
            sign = "−" if pnl < ZERO else "+"
            label = "← LOSS" if pnl < ZERO else "← GAIN"
            lines.append(f"  Embedded P&L:                       EUR {sign}{abs(pnl):>8.2f}  {label}")
            if credit > ZERO:
                lines.append(f"  KeSt credit if sold in {tax_year}:       EUR {credit:>9.2f}")
                lines.append("")
                lines.append(f"  ⚠  SELL CANDIDATE: ~EUR {credit:,.0f} KeSt credit available.")
                lines.append(f"     Sell in a year with >= EUR {abs(pnl):,.0f} other capital gains.")
                lines.append(f"     AT: same-year Verlustausgleich only — no carryforward.")
            else:
                lines.append("")
                lines.append(f"  ✓  Above water — no embedded tax loss credit available.")
        else:
            lines.append("  (Cost basis not found — add to manual_cost_basis config for P&L estimate.)")

        if result.warning:
            lines.append(f"  ⚠ {result.warning}")

        lines.append("")

    return lines


def _calc_embedded_pnl(
    symbol: str,
    config: dict,
    tax_year: int,
    all_transactions: list,
    fx,
    price_cache_dir: str,
    nmf_result: NichtmeldefondsResult,
) -> "tuple | None":
    """
    Returns (cost_eur, cum_ae_eur, adj_cost_eur, current_val_eur, pnl_eur, credit_eur)
    or None when cost basis or price data is unavailable.
    """
    shares = nmf_result.shares_held
    if not shares or shares <= ZERO:
        return None
    if not nmf_result.price_dec31 or not nmf_result.fx_dec31:
        return None

    current_val = (shares * nmf_result.price_dec31 * nmf_result.fx_dec31).quantize(Decimal("0.01"))

    cost_eur = _get_cost_eur(symbol, config, all_transactions)
    if cost_eur <= ZERO:
        return None

    # Cumulative AE: run NMF calc for every year from purchase to now
    purchase_year = _get_purchase_year(symbol, config, all_transactions, tax_year)
    nmf_entries = config.get("nichtmeldefonds", [])
    entry = next((e for e in nmf_entries if e.get("symbol") == symbol), {})

    cum_ae = ZERO
    for year in range(purchase_year, tax_year + 1):
        yr = _calc_position(entry, year, all_transactions, fx, price_cache_dir)
        if yr and yr.ae_total_eur:
            cum_ae += yr.ae_total_eur
    cum_ae = cum_ae.quantize(Decimal("0.01"))

    adj_cost = (cost_eur + cum_ae).quantize(Decimal("0.01"))
    pnl = (current_val - adj_cost).quantize(Decimal("0.01"))
    credit = ((-pnl * KEST_RATE).quantize(Decimal("0.01")) if pnl < ZERO else ZERO)

    return cost_eur, cum_ae, adj_cost, current_val, pnl, credit


def _get_cost_eur(symbol: str, config: dict, all_transactions: list) -> Decimal:
    """
    Sum manual_cost_basis cost_eur for symbol (SAXO qty=1 lots; each cost_eur
    = total EUR cost for that tranche's real shares). Falls back to BUY txns.
    """
    total = ZERO
    for lot in config.get("manual_cost_basis", []):
        if lot.get("symbol") != symbol:
            continue
        total += Decimal(str(lot.get("cost_eur", 0)))
    if total > ZERO:
        return total.quantize(Decimal("0.01"))
    # Fallback: IB BUY transactions
    for txn in all_transactions:
        if txn.symbol == symbol and txn.txn_type == TransactionType.BUY:
            total += abs(txn.eur_amount or ZERO)
    return total.quantize(Decimal("0.01"))


def _get_purchase_year(symbol: str, config: dict, all_transactions: list,
                       fallback: int) -> int:
    """Return the earliest purchase year for a NMF symbol."""
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
             if t.symbol == symbol and t.txn_type == TransactionType.BUY]
    return min(years) if years else fallback


# ── Section 2: Dividend payment frequency ─────────────────────────────────────

def _section_dividend_frequency(all_transactions: list):
    lines = [
        DLINE,
        "  SECTION 2: DIVIDEND PAYMENT FREQUENCY",
        DLINE,
        "",
        "  Averaged across all available years in the transaction history.",
        "  Monthly payers improve cash flow for FIRE strategies.",
        "",
    ]

    freq = compute_dividend_frequency(all_transactions)
    if not freq:
        lines += ["  No dividend transactions found.", ""]
        return lines

    groups: dict[str, list] = {"monthly": [], "quarterly": [],
                                "semi-annual": [], "annual": []}
    for sym, info in sorted(freq.items()):
        cat = info["category"]
        if cat in groups:
            groups[cat].append((sym, info))

    labels = {
        "monthly":     "Monthly payers     (≥10×/yr)",
        "quarterly":   "Quarterly payers   (3–9×/yr)",
        "semi-annual": "Semi-annual payers (2×/yr)",
        "annual":      "Annual payers      (1×/yr)",
    }

    for cat in ("monthly", "quarterly", "semi-annual", "annual"):
        members = groups[cat]
        if not members:
            continue
        lines.append(f"  {labels[cat]}")
        lines.append(f"  {'─'*50}")
        lines.append(f"  {'Symbol':<8}  {'Avg pmts/yr':>12}  Note")
        for sym, info in members:
            avg = info["avg_payments_per_year"]
            yrs = info["years_observed"]
            note = f"({yrs} yr{'s' if yrs != 1 else ''} of data)"
            lines.append(f"  {sym:<8}  {avg:>12.1f}  {note}")
        lines.append("")

    annual_n = len(groups["annual"])
    frequent_n = sum(len(groups[k]) for k in ("monthly", "quarterly", "semi-annual"))
    if annual_n > frequent_n and annual_n > 2:
        lines += [
            f"  ⚠  {annual_n} annual payers vs {frequent_n} more-frequent payers.",
            "     Consider shifting some allocation to monthly/quarterly payers",
            "     to smooth out cash flow without reducing total dividend income.",
            "",
        ]

    return lines


def compute_dividend_frequency(transactions: list) -> dict:
    """
    Public helper used by tests.
    Returns {symbol: {"avg_payments_per_year": float, "category": str, "years_observed": int}}

    Counts distinct months with a dividend per (symbol, year), then averages over years.
    Using distinct months avoids double-counting same-month WHT correction rows.
    """
    # symbol → year → set of distinct months
    payments: dict = defaultdict(lambda: defaultdict(set))

    for txn in transactions:
        if txn.txn_type != TransactionType.DIVIDEND:
            continue
        payments[txn.symbol][txn.trade_date.year].add(txn.trade_date.month)

    result = {}
    for sym, year_months in payments.items():
        counts = [len(m) for m in year_months.values()]
        avg = sum(counts) / len(counts)
        if avg >= 10:
            cat = "monthly"
        elif avg >= 3:
            cat = "quarterly"
        elif avg >= 2:
            cat = "semi-annual"
        else:
            cat = "annual"
        result[sym] = {
            "avg_payments_per_year": round(avg, 1),
            "category": cat,
            "years_observed": len(counts),
        }

    return result


# ── Section 3: Summary ────────────────────────────────────────────────────────

def _section_summary(config, tax_year, all_transactions, nmf_results, fx):
    lines = [
        DLINE,
        "  SECTION 3: SUMMARY & ACTION ITEMS",
        DLINE,
        "",
    ]

    if not nmf_results:
        lines += ["  No Nichtmeldefonds positions.", ""]
        return lines

    price_cache_dir = config.get("price_cache_dir", "./cache/price_cache")
    total_kest = sum(r.kest_due_eur for r in nmf_results)
    lines.append(f"  NMF KeSt burden ({tax_year}):    EUR {total_kest:>10,.2f}")

    credits = []
    for result in nmf_results:
        emb = _calc_embedded_pnl(result.symbol, config, tax_year, all_transactions,
                                  fx, price_cache_dir, result)
        if emb and emb[5] > ZERO:
            credits.append((result.symbol, emb[5]))

    if credits:
        total_credit = sum(c for _, c in credits)
        lines.append(f"  NMF credits if sold in {tax_year}:  EUR {total_credit:>10,.2f}")
        lines.append("")
        lines.append(f"  Positions generating KeSt credits if sold in {tax_year}:")
        for sym, credit in sorted(credits, key=lambda x: -x[1]):
            lines.append(f"    {sym:<6}  EUR {credit:>8,.2f}")
        lines.append("")
        min_gains_needed = sum(c / KEST_RATE for _, c in credits)
        lines.append(f"  ⚠  KEY: Sell underwater positions in a year with >= EUR {min_gains_needed:,.0f}")
        lines.append(f"     other capital gains to fully absorb the credit.")
        lines.append(f"     AT KeSt: same-year Verlustausgleich only — no loss carryforward.")
    else:
        lines.append("  NMF positions: all above water (no embedded loss credit).")

    lines.append("")
    lines.append("  For WHT excess reclaim amounts, see the _wht_reclaim.txt report.")
    lines.append("")
    return lines


# ── Public helpers for pipeline / tests ──────────────────────────────────────

def compute_nmf_embedded_pnl(
    config: dict,
    tax_year: int,
    all_transactions: list,
    nmf_results: list,
    fx,
) -> list[dict]:
    """
    Returns a list of embedded P&L dicts per NMF symbol.
    Each dict: {symbol, name, cost_eur, cum_ae_eur, adj_cost_eur,
                current_val_eur, pnl_eur, credit_eur}
    """
    price_cache_dir = config.get("price_cache_dir", "./cache/price_cache")
    output = []
    for result in nmf_results:
        emb = _calc_embedded_pnl(result.symbol, config, tax_year,
                                  all_transactions, fx, price_cache_dir, result)
        if emb:
            cost, cum_ae, adj_cost, curr_val, pnl, credit = emb
            output.append({
                "symbol": result.symbol,
                "name": result.name,
                "cost_eur": cost,
                "cum_ae_eur": cum_ae,
                "adj_cost_eur": adj_cost,
                "current_val_eur": curr_val,
                "pnl_eur": pnl,
                "credit_eur": credit,
            })
    return output
