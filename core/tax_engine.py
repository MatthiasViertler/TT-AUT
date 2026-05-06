"""
Austrian capital gains tax engine (§ 27 EStG 1988).

Rules implemented:
- KESt rate: 27.5% on dividends, capital gains, interest
- FIFO cost basis matching for buy/sell pairs
- Domestic (AT) vs. foreign asset classification
- WHT crediting: min(actual_wht, treaty_rate × gross_dividend)
- Loss offsetting: gains and losses within same category may offset
- Kennziffern assignment for E1kv form

NOT yet implemented (mark as TODO in output):
- Meldefonds / Ausschüttungsgleiche Erträge (KZ 937) — requires OeKB data
- Verlustausgleich across categories (requires prior-year carryforward data)
"""

import logging
from collections import defaultdict, deque
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from core.models import (
    NormalizedTransaction, TransactionType, Domicile,
    MatchedTrade, TaxSummary
)

log = logging.getLogger(__name__)
ZERO = Decimal("0")
TWO = Decimal("0.01")


class TaxEngine:
    def __init__(self, config: dict, tax_year: int, person_label: str):
        self.config = config
        self.tax_year = tax_year
        self.person_label = person_label
        self.kest_rate = Decimal(str(config["kest_rate"]))
        self.max_creditable_wht = Decimal(str(config["max_creditable_wht"]))
        self.wht_treaty = {k: Decimal(str(v))
                           for k, v in config.get("wht_treaty_rates", {}).items()}
        # Maps sell symbol → buy symbol for corporate actions that change ticker/ISIN
        # e.g. tender offers where IB assigns a new temporary symbol
        self.symbol_aliases: dict[str, str] = config.get("symbol_aliases", {})

    # ── Entry Point ───────────────────────────────────────────────────────────

    def calculate(self, transactions: list[NormalizedTransaction]) -> TaxSummary:
        """Run the full tax calculation pipeline."""
        year_txns = [t for t in transactions if t.trade_date.year == self.tax_year]
        if not year_txns:
            log.warning(f"No transactions found for tax year {self.tax_year}")

        summary = TaxSummary(tax_year=self.tax_year, person_label=self.person_label)
        summary.transaction_count = len(year_txns)

        dividends = [t for t in year_txns if t.txn_type == TransactionType.DIVIDEND]
        year_sells = [t for t in year_txns if t.txn_type == TransactionType.SELL]
        all_sells  = [t for t in transactions if t.txn_type == TransactionType.SELL]  # all years
        buys = [t for t in transactions if t.txn_type == TransactionType.BUY]  # all years for basis
        interests = [t for t in year_txns if t.txn_type == TransactionType.INTEREST]

        self._check_negative_positions(transactions, summary)
        self._process_dividends(dividends, summary)
        self._process_capital_gains(buys, year_sells, all_sells, summary)
        self._process_interest(interests, summary)
        self._finalize(summary)

        return summary

    # ── Dividends ─────────────────────────────────────────────────────────────

    def _process_dividends(self, dividends: list[NormalizedTransaction],
                            summary: TaxSummary) -> None:
        for txn in dividends:
            gross = txn.eur_amount or ZERO
            wht   = txn.eur_wht or ZERO       # positive value

            if txn.domicile == Domicile.DOMESTIC:
                summary.kz_862 += gross
                # KESt already deducted at source by Austrian broker → KZ 899
                # (If broker deducted KESt, it's already net; gross reconstruction needed)
                # Simplified: add WHT to 899 as proxy
                summary.kz_899 += wht
            else:
                summary.kz_863 += gross
                # Calculate creditable WHT
                country = txn.country_code or ""
                treaty_rate = self.wht_treaty.get(country, self.max_creditable_wht)
                creditable = min(wht, gross * treaty_rate)
                summary.kz_998 += creditable
                if wht - creditable > Decimal("0.05"):
                    summary.warnings.append(
                        f"WHT on {txn.symbol} ({txn.trade_date}): "
                        f"€{wht:.2f} paid, only €{creditable:.2f} creditable "
                        f"(treaty rate {treaty_rate:.0%} for {country or 'unknown country'})"
                        f" — excess €{(wht - creditable):.2f} not creditable, reclaim from source country"
                    )

            summary.total_dividends_eur += gross
            summary.total_wht_paid_eur += wht

    # ── Negative position check ───────────────────────────────────────────────

    def _check_negative_positions(self, transactions: list[NormalizedTransaction],
                                   summary: TaxSummary) -> None:
        """Warn if any symbol's net holding goes negative across all input years."""
        net: dict[str, Decimal] = defaultdict(lambda: ZERO)
        for t in transactions:
            if t.txn_type == TransactionType.BUY:
                net[t.symbol] += (t.quantity or ZERO).copy_abs()
            elif t.txn_type == TransactionType.SELL:
                effective = self.symbol_aliases.get(t.symbol, t.symbol)
                net[effective] -= (t.quantity or ZERO).copy_abs()
        for entry in self.config.get("manual_cost_basis", []):
            net[entry["symbol"]] += Decimal(str(entry["quantity"]))
        for sym, qty in net.items():
            if qty < ZERO:
                summary.warnings.append(
                    f"Negative position: {sym} net holding = {qty:.4f} units "
                    f"(sold more than bought — missing buy records or add to symbol_aliases)"
                )

    # ── Capital Gains (FIFO) ──────────────────────────────────────────────────

    def _process_capital_gains(self,
                                all_buys: list[NormalizedTransaction],
                                year_sells: list[NormalizedTransaction],
                                all_sells: list[NormalizedTransaction],
                                summary: TaxSummary) -> None:
        # Collect all lots: real buys + manual cost basis overrides
        # Each entry: (date, symbol, qty, cost_per_unit)
        lots: list[tuple] = []
        for buy in all_buys:
            qty = buy.quantity or ZERO
            if not qty:
                continue
            cpu = (
                ((buy.eur_amount or ZERO).copy_abs() + (buy.eur_commission or ZERO)) / qty
            )
            lots.append((buy.trade_date, buy.symbol, qty, cpu))

        from datetime import date as date_t
        for entry in self.config.get("manual_cost_basis", []):
            qty = Decimal(str(entry["quantity"]))
            cost = Decimal(str(entry["cost_eur"]))
            d = entry["purchase_date"]
            if not isinstance(d, date_t):
                d = date_t.fromisoformat(str(d))
            cpu = cost / qty if qty else ZERO
            lots.append((d, entry["symbol"], qty, cpu))

        # Build FIFO queues in chronological order
        fifo: dict[str, deque] = defaultdict(deque)
        for d, sym, qty, cpu in sorted(lots, key=lambda x: x[0]):
            fifo[sym].append({"date": d, "qty_remaining": qty, "cost_per_unit": cpu})

        # Process ALL years' sells chronologically so prior-year sells drain their lots.
        # Only accumulate gains/losses into summary for current tax-year sells.
        year_sell_ids = {id(s) for s in year_sells}

        for sell in sorted(all_sells, key=lambda t: t.trade_date):
            qty_to_match = (sell.quantity or ZERO).copy_abs()
            proceeds = (sell.eur_amount or ZERO).copy_abs()
            commission = sell.eur_commission or ZERO

            cost_matched = ZERO
            effective_symbol = self.symbol_aliases.get(sell.symbol, sell.symbol)
            queue = fifo.get(effective_symbol, deque())

            while qty_to_match > ZERO and queue:
                lot = queue[0]
                use_qty = min(lot["qty_remaining"], qty_to_match)
                cost_matched += use_qty * lot["cost_per_unit"]
                lot["qty_remaining"] -= use_qty
                qty_to_match -= use_qty
                if lot["qty_remaining"] == ZERO:
                    queue.popleft()

            is_year_sell = id(sell) in year_sell_ids

            if qty_to_match > ZERO and is_year_sell:
                summary.unmatched_sells += 1
                summary.warnings.append(
                    f"FIFO: Unmatched sell {sell.symbol} on {sell.trade_date} "
                    f"— {qty_to_match} units have no purchase record. "
                    f"Cost basis set to 0 (may overstate gain)."
                )

            if not is_year_sell:
                continue  # lot consumed; nothing to report for prior years

            net_gain = proceeds - cost_matched - commission

            # Store on transaction for Excel audit trail
            sell.eur_gain_loss = net_gain
            sell.eur_cost_basis = cost_matched

            # Cross-check against broker-reported FIFO PnL (available from HEADER/DATA format)
            if sell.broker_fifo_pnl_eur is not None:
                diff = (net_gain - sell.broker_fifo_pnl_eur).copy_abs()
                if diff > Decimal("1.00"):
                    summary.warnings.append(
                        f"FIFO mismatch {sell.symbol} ({sell.trade_date}): "
                        f"our gain={net_gain:.2f} EUR, IB reports {sell.broker_fifo_pnl_eur:.2f} EUR "
                        f"(diff={diff:.2f} EUR) — verify cost basis"
                    )

            if sell.domicile == Domicile.DOMESTIC:
                if net_gain >= ZERO:
                    summary.kz_981 += net_gain
                    summary.total_gains_eur += net_gain
                else:
                    summary.kz_891 += net_gain.copy_abs()
                    summary.total_losses_eur += net_gain.copy_abs()
            else:
                if net_gain >= ZERO:
                    summary.kz_994 += net_gain
                    summary.total_gains_eur += net_gain
                else:
                    summary.kz_892 += net_gain.copy_abs()
                    summary.total_losses_eur += net_gain.copy_abs()

    # ── Interest ──────────────────────────────────────────────────────────────

    def _process_interest(self, interests: list[NormalizedTransaction],
                           summary: TaxSummary) -> None:
        for txn in interests:
            amt = txn.eur_amount or ZERO
            if txn.domicile == Domicile.DOMESTIC:
                summary.kz_862 += amt      # Treat as domestic capital income
            else:
                summary.kz_863 += amt
            summary.total_dividends_eur += amt

    # ── Final KESt Calculation ────────────────────────────────────────────────

    def _finalize(self, summary: TaxSummary) -> None:
        # Net taxable = dividends + gains - losses (intra-category offset allowed)
        domestic_net = (summary.kz_862 + summary.kz_981) - summary.kz_891
        foreign_net  = (summary.kz_863 + summary.kz_994) - summary.kz_892

        summary.net_taxable_eur = domestic_net + foreign_net

        # KESt on gross (losses reduce the base, WHT is a credit, not a deduction)
        summary.kest_due_eur = (summary.net_taxable_eur * self.kest_rate).quantize(TWO, ROUND_HALF_UP)

        # WHT credit: min(paid, 15% of foreign dividends)
        foreign_div_gross = summary.kz_863
        max_credit = (foreign_div_gross * self.max_creditable_wht).quantize(TWO, ROUND_HALF_UP)
        summary.wht_creditable_eur = min(summary.kz_998, max_credit)

        # Remaining KESt to pay
        summary.kest_remaining_eur = max(
            ZERO,
            (summary.kest_due_eur - summary.wht_creditable_eur).quantize(TWO, ROUND_HALF_UP)
        )

        summary.total_wht_paid_eur = summary.kz_998 + summary.kz_899

        # Saldo aus Punkt 1.3 — net capital income per domicile
        summary.saldo_inland = (
            summary.kz_862 + summary.kz_897 + summary.kz_936
            + summary.kz_981 + summary.kz_864
            + summary.kz_982 + summary.kz_893
            + summary.kz_171 + summary.kz_173
            - summary.kz_891 - summary.kz_895 - summary.kz_175
        )
        summary.saldo_ausland = (
            summary.kz_863 + summary.kz_898 + summary.kz_937
            + summary.kz_994 + summary.kz_865
            + summary.kz_993 + summary.kz_894
            - summary.kz_892 - summary.kz_896
        )
