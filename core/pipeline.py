"""
Pipeline orchestrator.
Wires together: broker parsing → FX enrichment → tax calculation → output.
"""

import logging
from datetime import date
from decimal import Decimal
from pathlib import Path

from brokers import load_transactions
from core.config import load_config, scan_account_ids, _deep_merge
from core.fx import FXRateProvider
from core.models import NormalizedTransaction, TransactionType
from core.nichtmeldefonds import calculate_nichtmeldefonds
from core.price_fetcher import get_year_end_price
from core.tax_engine import TaxEngine
from generators.writer import write_all

log = logging.getLogger(__name__)
ZERO = Decimal("0")


def run_pipeline(
    input_paths: list[Path],
    tax_year: int,
    person_label: str,
    broker_hint: str,
    config: dict,
    output_dir: Path,
    fetch_fx: bool,
    users_dir: Path = Path("users"),
) -> None:

    print(f"\n{'='*60}")
    print(f"  Kapitalertrag  |  {person_label}  |  Tax year {tax_year}")
    print(f"{'='*60}")

    # ── 1. Parse all input files ──────────────────────────────────────────────
    all_transactions: list[NormalizedTransaction] = []
    account_ids: set[str] = set()

    for path in input_paths:
        txns, account_id = load_transactions(path, config, broker_hint)
        all_transactions.extend(txns)
        if account_id:
            account_ids.add(account_id)
        print(f"  [parse]  {path.name}  →  {len(txns)} transactions"
              + (f"  (account: {account_id})" if account_id else ""))

    if not all_transactions:
        print("  [warn]  No transactions loaded. Check your input files.")
        return

    # Auto-resolve person label by scanning users/*/config.local.yaml for account_id
    if person_label == "auto":
        account_map = scan_account_ids(users_dir)
        resolved = set()
        for aid in account_ids:
            name = account_map.get(str(aid))
            if name:
                resolved.add(name)
        if len(resolved) == 1:
            person_label = resolved.pop()
            print(f"  [person] Auto-detected: {person_label} (account: {', '.join(account_ids)})")
            # Load person-specific config overrides now that we know who this is
            import yaml as _yaml
            local_path = users_dir / person_label / "config.local.yaml"
            if local_path.exists():
                with open(local_path) as _f:
                    _deep_merge(config, _yaml.safe_load(_f) or {})
                print(f"  [config] Loaded person overrides: {local_path}")
        elif len(resolved) > 1:
            person_label = "_".join(sorted(resolved))
            print(f"  [person] Multiple accounts detected: {person_label}")
        else:
            # No mapping found — fall back to account ID itself
            person_label = "_".join(sorted(account_ids)) if account_ids else "unknown"
            print(f"  [person] No account_id mapping found — using: {person_label}")
            print(f"           Add account_id to users/{person_label}/config.local.yaml")

    # Deduplicate by raw_id
    seen = set()
    unique = []
    for t in all_transactions:
        if t.raw_id not in seen:
            seen.add(t.raw_id)
            unique.append(t)
    if len(unique) < len(all_transactions):
        print(f"  [dedup]  Removed {len(all_transactions) - len(unique)} duplicate rows")
    all_transactions = unique

    # ── 2. FX enrichment ─────────────────────────────────────────────────────
    fx = FXRateProvider(
        cache_dir=config.get("fx_cache_dir", "./cache/fx_cache"),
        fetch_live=fetch_fx,
    )
    missing_fx = 0
    for txn in all_transactions:
        rate = fx.get_rate(txn.orig_currency, txn.trade_date)
        if rate is None:
            missing_fx += 1
            txn.notes += f" [WARN: no FX rate for {txn.orig_currency} on {txn.trade_date}]"
            rate = ZERO
        txn.fx_rate_to_eur = rate
        txn.eur_amount = (txn.orig_amount * rate).quantize(Decimal("0.01"))
        txn.eur_commission = (txn.commission * rate).quantize(Decimal("0.01"))
        txn.eur_wht = (txn.wht_amount_orig * rate).quantize(Decimal("0.01"))

    if missing_fx:
        print(f"  [fx]     WARNING: {missing_fx} transactions missing FX rate (set to 0)")
    else:
        print(f"  [fx]     All FX rates resolved")

    # ── 3. Tax calculation ────────────────────────────────────────────────────
    engine = TaxEngine(config, tax_year, person_label)
    summary = engine.calculate(all_transactions)
    summary.missing_fx_count = missing_fx
    print(f"  [tax]    Calculated for {summary.transaction_count} transactions in {tax_year}")

    # ── 3b. Nichtmeldefonds (pauschal AE) ─────────────────────────────────────
    nmf_results = calculate_nichtmeldefonds(config, tax_year, all_transactions, fx)
    if nmf_results:
        summary.nichtmeldefonds = nmf_results
        summary.nichtmeldefonds_ae_eur   = sum(r.ae_total_eur  for r in nmf_results)
        summary.nichtmeldefonds_kest_eur = sum(r.kest_due_eur  for r in nmf_results)
        # AE flows into KZ 937 (ausschüttungsgleiche Erträge Ausland) and saldo
        summary.kz_937          += summary.nichtmeldefonds_ae_eur
        summary.saldo_ausland   += summary.nichtmeldefonds_ae_eur
        summary.net_taxable_eur += summary.nichtmeldefonds_ae_eur
        summary.kest_due_eur    += summary.nichtmeldefonds_kest_eur
        summary.kest_remaining_eur = max(
            ZERO,
            (summary.kest_due_eur - summary.wht_creditable_eur).quantize(Decimal("0.01"))
        )
        positions_ok    = sum(1 for r in nmf_results if not r.warning)
        positions_warn  = sum(1 for r in nmf_results if r.warning)
        print(f"  [nmf]    Nichtmeldefonds: {len(nmf_results)} position(s), "
              f"AE = EUR {summary.nichtmeldefonds_ae_eur:,.2f}, "
              f"KeSt = EUR {summary.nichtmeldefonds_kest_eur:,.2f}"
              + (f"  ⚠ {positions_warn} missing price(s)" if positions_warn else ""))

    # ── 3c. Dynamic portfolio value (Dec 31 market price × remaining lots) ───
    portfolio_eur = _compute_portfolio_value(
        engine.remaining_positions,
        engine.symbol_meta,
        fx,
        tax_year,
        config,
    )
    if portfolio_eur > ZERO:
        summary.portfolio_eur_computed = portfolio_eur
        print(f"  [port]   Portfolio value (computed): EUR {portfolio_eur:,.2f} "
              f"({len([p for p in engine.remaining_positions.values() if not p['has_synthetic']])} "
              f"positions valued; "
              f"{len([p for p in engine.remaining_positions.values() if p['has_synthetic']])} "
              f"synthetic skipped)")
    else:
        print(f"  [port]   Portfolio value: could not compute (no prices available) "
              f"— using config value if set")

    # ── 4. Output ─────────────────────────────────────────────────────────────
    write_all(
        transactions=all_transactions,
        summary=summary,
        output_dir=output_dir,
        config=config,
    )

    # ── 5. Console summary ────────────────────────────────────────────────────
    _print_summary(summary)


def _compute_portfolio_value(
    remaining_positions: dict,
    symbol_meta: dict,
    fx: FXRateProvider,
    tax_year: int,
    config: dict,
) -> Decimal:
    """
    Compute EUR portfolio value from remaining FIFO lots at Dec 31.

    Skips synthetic positions (SAXO AggregatedAmounts qty=1 convention and
    manual_cost_basis entries) where the recorded quantity is not a real share count.

    Returns 0 if no prices could be fetched.
    """
    price_cache_dir = config.get("price_cache_dir", "./cache/price_cache")
    dec31 = date(tax_year, 12, 31)
    total = ZERO

    for symbol, pos in remaining_positions.items():
        if pos["has_synthetic"]:
            continue
        qty = pos["qty"]
        if qty <= ZERO:
            continue

        meta = symbol_meta.get(symbol, {})
        currency = meta.get("currency", "USD")

        price = get_year_end_price(symbol, currency, tax_year, price_cache_dir)
        if price is None or price == ZERO:
            log.debug(f"Portfolio: no Dec31 {tax_year} price for {symbol} — skipping")
            continue

        fx_rate = fx.get_rate(currency, dec31)
        if fx_rate is None or fx_rate == ZERO:
            log.debug(f"Portfolio: no Dec31 FX rate for {currency} — skipping {symbol}")
            continue

        eur_value = (qty * price * fx_rate).quantize(Decimal("0.01"))
        log.debug(f"Portfolio: {symbol} {qty} × {price} {currency} × {fx_rate} = EUR {eur_value}")
        total += eur_value

    return total


def _print_summary(s) -> None:
    W = 60
    def row(label, value, indent=2):
        pad = W - indent - len(label) - len(value)
        print(f"  {'':>{indent-2}}{label}{'.'*max(1,pad)}{value}")

    print(f"\n{'─'*W}")
    print(f"  TAX SUMMARY  {s.person_label}  –  {s.tax_year}")
    print(f"{'─'*W}")
    print(f"  DIVIDENDS")
    row("KZ 862  Inländ. Dividenden",    f"EUR {s.kz_862:>12,.2f}")
    row("KZ 863  Ausländ. Dividenden",   f"EUR {s.kz_863:>12,.2f}")
    print(f"  CAPITAL GAINS")
    row("KZ 981  Inländ. Kursgewinne",   f"EUR {s.kz_981:>12,.2f}")
    row("KZ 994  Ausländ. Kursgewinne",  f"EUR {s.kz_994:>12,.2f}")
    row("KZ 891  Inländ. Kursverluste",  f"EUR {s.kz_891:>12,.2f}")
    row("KZ 892  Ausländ. Kursverluste", f"EUR {s.kz_892:>12,.2f}")
    print(f"  WITHHOLDING TAX")
    row("KZ 899  KESt inländ. WP",       f"EUR {s.kz_899:>12,.2f}")
    row("KZ 998  Quellensteuer ausländ.",f"EUR {s.kz_998:>12,.2f}")
    print(f"{'─'*W}")
    row("Net taxable income",            f"EUR {s.net_taxable_eur:>12,.2f}")
    row("KESt due  (27.5%)",             f"EUR {s.kest_due_eur:>12,.2f}")
    row("WHT creditable",                f"EUR {s.wht_creditable_eur:>12,.2f}")
    row("KESt remaining to pay",         f"EUR {s.kest_remaining_eur:>12,.2f}", indent=4)
    print(f"{'─'*W}")

    if s.warnings:
        print(f"\n  ⚠  {len(s.warnings)} WARNING(S):")
        for w in s.warnings[:10]:
            print(f"     • {w}")
        if len(s.warnings) > 10:
            print(f"     … and {len(s.warnings)-10} more (see output files)")
    if s.unmatched_sells:
        print(f"\n  ⚠  {s.unmatched_sells} sell(s) with no matching purchase record — cost basis assumed 0")

    print()
