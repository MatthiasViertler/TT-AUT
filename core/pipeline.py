"""
Pipeline orchestrator.
Wires together: broker parsing → FX enrichment → tax calculation → output.
"""

import logging
from datetime import date
from decimal import Decimal
from pathlib import Path

from brokers import load_transactions
from brokers.ib_csv import parse_ibkr_cash_report, parse_ibkr_interest, _iter_interest_rows
from brokers.ibkr_positions import parse_ibkr_positions
from core.config import load_config, scan_account_ids, _deep_merge
from core.fx import FXRateProvider
from core.models import NormalizedTransaction, PortfolioPosition, TransactionType
from core.meldefonds import calculate_meldefonds
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
    ibkr_positions_path: Path | None = None,
) -> None:

    print(f"\n{'='*60}")
    print(f"  Kapitalertrag  |  {person_label}  |  Tax year {tax_year}")
    print(f"{'='*60}")

    # ── 1. Parse all input files ──────────────────────────────────────────────
    all_transactions: list[NormalizedTransaction] = []
    account_ids: set[str] = set()

    skipped = 0
    for path in input_paths:
        txns, account_id = load_transactions(path, config, broker_hint)
        if txns is None:
            skipped += 1
            continue
        all_transactions.extend(txns)
        if account_id:
            account_ids.add(account_id)
        print(f"  [parse]  {path.name}  →  {len(txns)} transactions"
              + (f"  (account: {account_id})" if account_id else ""))
    if skipped:
        print(f"  [skip]   {skipped} file(s) not recognised as broker exports (see log for names)")

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

    _print_coverage(all_transactions, tax_year)

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

    # ── 3c. Meldefonds (OeKB-registered fund AE/WA) ──────────────────────────
    mf_results = calculate_meldefonds(config, tax_year, all_transactions, fx)
    if mf_results:
        summary.meldefonds              = mf_results
        summary.meldefonds_ae_eur       = sum(r.ae_total_eur   for r in mf_results)
        summary.meldefonds_kest_gross_eur = sum(r.kest_gross_eur for r in mf_results)
        summary.meldefonds_wa_eur       = sum(r.wa_total_eur   for r in mf_results)
        summary.meldefonds_kest_net_eur = sum(r.kest_net_eur   for r in mf_results)
        for r in mf_results:
            if r.kz == "936":
                summary.kz_936        += r.ae_total_eur
                summary.saldo_inland  += r.ae_total_eur
            else:
                summary.kz_937        += r.ae_total_eur
                summary.saldo_ausland += r.ae_total_eur
            summary.net_taxable_eur += r.ae_total_eur
            summary.kest_due_eur    += r.kest_gross_eur
        # WA is a fund-internal credit that reduces the KeSt remaining to pay
        summary.kest_remaining_eur = max(
            ZERO,
            (summary.kest_due_eur
             - summary.wht_creditable_eur
             - summary.meldefonds_wa_eur).quantize(Decimal("0.01"))
        )
        mf_warn = sum(1 for r in mf_results if r.warning)
        print(f"  [mf]     Meldefonds: {len(mf_results)} position(s), "
              f"AE = EUR {summary.meldefonds_ae_eur:,.2f}, "
              f"KeSt = EUR {summary.meldefonds_kest_net_eur:,.2f}"
              + (f"  ⚠ {mf_warn} with zero AE (verify on my.oekb.at)" if mf_warn else ""))

    # ── 3e. Dynamic portfolio value (Dec 31 market price × remaining lots) ───
    symbol_divs = _compute_symbol_dividends(all_transactions, tax_year)
    symbol_info = _build_symbol_info(config, mf_results, nmf_results)

    # Parse IBKR Open Positions data (more accurate than FIFO × yfinance).
    # Priority: explicit positions file → Open Positions section in any input file.
    ibkr_pos_data: dict = {}
    ibkr_pos_source: str = ""
    if ibkr_positions_path is not None and ibkr_positions_path.exists():
        ibkr_pos_data = parse_ibkr_positions(ibkr_positions_path)
        ibkr_pos_source = ibkr_positions_path.name
    if not ibkr_pos_data:
        # Option A: Open Positions section embedded in activity statement file
        for p in input_paths:
            candidate = parse_ibkr_positions(p)
            if candidate:
                ibkr_pos_data = candidate
                ibkr_pos_source = p.name
                break
    if ibkr_pos_data:
        print(f"  [ibkr-pos] {len(ibkr_pos_data)} positions from {ibkr_pos_source}")

    portfolio_eur, portfolio_positions = _compute_portfolio_value(
        engine.remaining_positions,
        engine.symbol_meta,
        fx,
        tax_year,
        config,
        symbol_divs=symbol_divs,
        symbol_info=symbol_info,
        ibkr_positions=ibkr_pos_data,
    )
    # ── 3e-ii. IBKR Cash Report ───────────────────────────────────────────────
    ibkr_cash_eur = ZERO
    for p in input_paths:
        cash = parse_ibkr_cash_report(p)
        if cash is not None and cash > ZERO:
            ibkr_cash_eur = cash
            summary.ibkr_cash_eur = cash
            print(f"  [cash]   IBKR cash: EUR {cash:,.2f} (from {p.name})")
            break

    if ibkr_cash_eur > ZERO:
        portfolio_eur += ibkr_cash_eur
        portfolio_positions.append(PortfolioPosition(
            symbol="CASH",
            name="IBKR Cash",
            fund_type="Cash",
            currency="EUR",
            qty=ibkr_cash_eur,
            is_synthetic=False,
            eur_value=ibkr_cash_eur,
            dividends_eur=ZERO,
            yield_pct=None,
            portfolio_pct=None,
        ))
        # Re-normalize portfolio_pct now that total includes cash
        for pos in portfolio_positions:
            if pos.eur_value > ZERO:
                pos.portfolio_pct = round(float(pos.eur_value / portfolio_eur * 100), 2)

    summary.portfolio_positions = portfolio_positions
    if portfolio_eur > ZERO:
        summary.portfolio_eur_computed = portfolio_eur
        n_valued = len([p for p in portfolio_positions
                        if not p.is_synthetic and p.eur_value > ZERO
                        and p.symbol != "CASH"])
        n_synthetic = len([p for p in portfolio_positions if p.is_synthetic])
        src_note = " (from IBKR positions file)" if ibkr_pos_data else ""
        cash_note = f" + EUR {ibkr_cash_eur:,.2f} cash" if ibkr_cash_eur > ZERO else ""
        print(f"  [port]   Portfolio value (computed): EUR {portfolio_eur:,.2f} "
              f"({n_valued} positions valued; "
              f"{n_synthetic} synthetic skipped{cash_note}){src_note}")
    else:
        print(f"  [port]   Portfolio value: could not compute (no prices available) "
              f"— using config value if set")

    # ── 3e-iii. IBKR Cash Interest ────────────────────────────────────────────
    # 'Broker Interest Received' rows from CTRN section.  Fully optional: absent
    # rows → ZERO, no change to tax output.  Present rows added to KZ 863 and kest_due.
    # Deduplicate by (currency, description): the same monthly payment appears in
    # both the auto-fetched flex CSV and the annual TT-AUT export — count it once.
    interest_eur = ZERO
    seen_interest: dict[tuple, Decimal] = {}
    for p in input_paths:
        for key, eur_amt in _iter_interest_rows(p, tax_year):
            if key not in seen_interest:
                seen_interest[key] = eur_amt
    if seen_interest:
        interest_eur = sum(seen_interest.values(), ZERO)
        print(f"  [interest] EUR {interest_eur:,.2f} cash interest for {tax_year} "
              f"({len(seen_interest)} unique payments across {len(input_paths)} files)")

    if interest_eur > ZERO:
        summary.interest_eur = interest_eur
        summary.kz_863          += interest_eur
        summary.saldo_ausland   += interest_eur
        summary.net_taxable_eur += interest_eur
        summary.kest_due_eur    += (interest_eur * Decimal("0.275")).quantize(Decimal("0.01"))
        summary.kest_remaining_eur = max(
            ZERO,
            (summary.kest_due_eur
             - summary.wht_creditable_eur
             - summary.meldefonds_wa_eur).quantize(Decimal("0.01"))
        )

    # ── 3f. Trailing dividend yield (actual dividends / Dec31 portfolio) ──────
    computed_yield = _compute_dividend_yield(summary)
    if computed_yield is not None:
        summary.dividend_yield_computed = computed_yield
        n_synthetic = sum(1 for p in engine.remaining_positions.values() if p["has_synthetic"])
        note = f"  ⚠ {n_synthetic} synthetic positions excluded — yield may be inflated" if n_synthetic else ""
        print(f"  [port]   Trailing dividend yield: {computed_yield:.2f}% "
              f"(EUR {float(summary.total_dividends_eur):,.2f} dividends "
              f"/ EUR {float(summary.portfolio_eur_computed):,.2f} portfolio){note}")

    # ── 4. Output ─────────────────────────────────────────────────────────────
    write_all(
        transactions=all_transactions,
        summary=summary,
        output_dir=output_dir,
        config=config,
    )

    # ── 5. Console summary ────────────────────────────────────────────────────
    _print_summary(summary)


def _compute_symbol_dividends(
    transactions: list,
    tax_year: int,
) -> "dict[str, Decimal]":
    """
    Sum gross EUR dividends (eur_amount) by symbol for DIVIDEND transactions
    in the given tax year.  Returns {symbol: total_eur}.
    """
    result: dict[str, Decimal] = {}
    for txn in transactions:
        if txn.txn_type != TransactionType.DIVIDEND:
            continue
        if txn.trade_date.year != tax_year:
            continue
        sym = txn.symbol
        amount = txn.eur_amount or ZERO
        result[sym] = result.get(sym, ZERO) + amount
    return result


def _build_symbol_info(config: dict, mf_results: list, nmf_results: list) -> "dict[str, dict]":
    """
    Build {symbol: {"name": str, "type": str, "currency": str}} from:
    - config["nichtmeldefonds"] entries (REITs, BDCs, unregistered funds)
    - mf_results (MeldefondsResult list) — OeKB-registered ETFs/funds

    ETF entries from mf_results get an "(acc)" or "(dist)" suffix on the name.
    """
    info: dict[str, dict] = {}

    # Nichtmeldefonds from config
    for entry in config.get("nichtmeldefonds", []):
        sym = entry.get("symbol", "")
        if not sym:
            continue
        info[sym] = {
            "name": entry.get("name", sym),
            "type": entry.get("type", "Fund"),
            "currency": entry.get("currency", "USD"),
        }

    # Meldefonds results
    for r in mf_results:
        name = r.name
        if r.fund_type == "ETF":
            suffix = " (acc)" if r.ertragsverwendung == "thesaurierend" else " (dist)"
            name = name + suffix
        info[r.symbol] = {
            "name": name,
            "type": r.fund_type,
            "currency": r.currency,
        }

    return info


def _compute_portfolio_value(
    remaining_positions: dict,
    symbol_meta: dict,
    fx: FXRateProvider,
    tax_year: int,
    config: dict,
    symbol_divs: "dict[str, Decimal] | None" = None,
    symbol_info: "dict[str, dict] | None" = None,
    ibkr_positions: "dict | None" = None,
) -> "tuple[Decimal, list]":
    """
    Compute EUR portfolio value from remaining FIFO lots at Dec 31.

    When ibkr_positions is provided (from an IBKR Open Positions Flex report),
    uses IBKR's actual Dec-31 quantity and mark price instead of FIFO × yfinance.
    This is more accurate for European stocks and any ticker yfinance can't resolve.

    Builds a list of PortfolioPosition objects with market value, dividends,
    yield%, and portfolio% filled in.  Sold positions (dividend but no
    remaining lot) are appended at the end.

    Returns (total_eur, list[PortfolioPosition]).
    Synthetic positions are included in the list but excluded from value totals.
    """
    if symbol_divs is None:
        symbol_divs = {}
    if symbol_info is None:
        symbol_info = {}
    if ibkr_positions is None:
        ibkr_positions = {}

    price_cache_dir = config.get("price_cache_dir", "./cache/price_cache")
    dec31 = date(tax_year, 12, 31)
    positions: list[PortfolioPosition] = []
    total = ZERO

    for symbol, pos in remaining_positions.items():
        is_synthetic = pos["has_synthetic"]
        qty = pos["qty"]

        meta = symbol_meta.get(symbol, {})
        currency = meta.get("currency", "USD")
        info = symbol_info.get(symbol, {})
        name = info.get("name", symbol)
        fund_type = info.get("type", "Stock")
        info_currency = info.get("currency", currency)

        eur_value = ZERO
        if not is_synthetic and qty > ZERO:
            ibkr_pos = ibkr_positions.get(symbol)
            if ibkr_pos:
                # Use IBKR's actual Dec-31 quantity and mark price (no yfinance needed)
                ibkr_qty   = ibkr_pos["qty"]
                ibkr_price = ibkr_pos["price"]
                ibkr_ccy   = ibkr_pos.get("currency") or info_currency or currency
                fx_rate = fx.get_rate(ibkr_ccy, dec31)
                if fx_rate is not None and fx_rate > ZERO:
                    eur_value = (ibkr_qty * ibkr_price * fx_rate).quantize(Decimal("0.01"))
                    qty = ibkr_qty  # use IBKR's actual quantity
                    log.debug(
                        "Portfolio (IBKR): %s %s × %s %s × %s = EUR %s",
                        symbol, ibkr_qty, ibkr_price, ibkr_ccy, fx_rate, eur_value,
                    )
                else:
                    log.debug("Portfolio (IBKR): no Dec31 FX rate for %s — skipping %s", ibkr_ccy, symbol)
            else:
                price = get_year_end_price(symbol, info_currency or currency, tax_year, price_cache_dir)
                if price is not None and price > ZERO:
                    fx_rate = fx.get_rate(info_currency or currency, dec31)
                    if fx_rate is not None and fx_rate > ZERO:
                        eur_value = (qty * price * fx_rate).quantize(Decimal("0.01"))
                        log.debug(
                            "Portfolio: %s %s × %s %s × %s = EUR %s",
                            symbol, qty, price, info_currency or currency, fx_rate, eur_value,
                        )
                    else:
                        log.debug("Portfolio: no Dec31 FX rate for %s — skipping %s", info_currency or currency, symbol)
                else:
                    log.debug("Portfolio: no Dec31 %s price for %s — skipping", tax_year, symbol)

        total += eur_value
        divs_eur = symbol_divs.get(symbol, ZERO)

        positions.append(PortfolioPosition(
            symbol=symbol,
            name=name,
            fund_type=fund_type,
            currency=info_currency or currency,
            qty=qty,
            is_synthetic=is_synthetic,
            eur_value=eur_value,
            dividends_eur=divs_eur,
            yield_pct=None,
            portfolio_pct=None,
        ))

    # Add sold positions (dividends received but no remaining lots)
    remaining_syms = set(remaining_positions.keys())
    for sym, div_eur in symbol_divs.items():
        if sym not in remaining_syms and div_eur > ZERO:
            info = symbol_info.get(sym, {})
            positions.append(PortfolioPosition(
                symbol=sym,
                name=info.get("name", sym),
                fund_type="Sold",
                currency=info.get("currency", ""),
                qty=ZERO,
                is_synthetic=False,
                eur_value=ZERO,
                dividends_eur=div_eur,
                yield_pct=None,
                portfolio_pct=None,
            ))

    # Fill portfolio_pct and yield_pct now that total is known
    for p in positions:
        if p.eur_value > ZERO and total > ZERO:
            p.portfolio_pct = round(float(p.eur_value / total * 100), 2)
        if p.eur_value > ZERO and p.dividends_eur > ZERO:
            p.yield_pct = round(float(p.dividends_eur / p.eur_value * 100), 2)

    # Sort positions per holdings_sort config
    fd = config.get("freedom_dashboard", {})
    sort_key = fd.get("holdings_sort", "value")

    def _sort_key(p: PortfolioPosition):
        # Category: 0 = normal, 1 = synthetic, 2 = sold
        if p.fund_type == "Sold":
            cat = 2
        elif p.is_synthetic:
            cat = 1
        else:
            cat = 0

        if sort_key == "yield":
            primary = -(p.yield_pct if p.yield_pct is not None else -1)
        elif sort_key == "alpha":
            primary = p.symbol
        else:  # "value" (default)
            primary = -float(p.eur_value)

        return (cat, primary)

    positions.sort(key=_sort_key)

    return total, positions


def _compute_dividend_yield(summary) -> "float | None":
    """Return trailing yield % (dividends / portfolio × 100), or None if not computable."""
    port = summary.portfolio_eur_computed
    divs = summary.total_dividends_eur
    if port is None or port <= ZERO or divs <= ZERO:
        return None
    return round(float(divs / port * 100), 2)


def _print_coverage(transactions: list, tax_year: int) -> None:
    """Print a data-coverage table grouped by broker so missing months are visible."""
    from collections import defaultdict

    _BROKER_LABELS = {
        "ib": "IBKR", "ibkr": "IBKR",
        "saxo": "SAXO", "etrade": "E*Trade",
    }

    # date range per broker: overall, and restricted to tax_year
    overall:  dict[str, list] = defaultdict(lambda: [None, None, 0])
    in_year:  dict[str, list] = defaultdict(lambda: [None, None, 0])

    for t in transactions:
        d      = t.trade_date
        broker = t.broker or "unknown"
        lo, hi, n = overall[broker]
        overall[broker] = [min(lo, d) if lo else d, max(hi, d) if hi else d, n + 1]
        if d.year == tax_year:
            lo, hi, n = in_year[broker]
            in_year[broker] = [min(lo, d) if lo else d, max(hi, d) if hi else d, n + 1]

    print("  [cover]  Data coverage by broker (by transaction date, not statement date):")
    for broker in sorted(overall):
        label       = _BROKER_LABELS.get(broker, broker)
        lo, hi, _   = overall[broker]
        if broker in in_year:
            ylo, yhi, yn = in_year[broker]
            year_part = f"{tax_year}: {ylo.strftime('%b %d')} → {yhi.strftime('%b %d')} ({yn} txns)"
        else:
            year_part = f"⚠ no {tax_year} transactions — check for missing files"
        print(f"           {label:<10}  {lo} → {hi}   |  {year_part}")


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
