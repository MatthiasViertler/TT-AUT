"""
WHT Reclaim Assistant — generates per-country excess withholding tax report.

Austrian tax residents can reclaim WHT withheld above the DBA treaty rate (15% for
most countries) from the source country's tax authority. This module identifies
excess WHT from all dividend transactions since the start of Austrian residency
and formats it for BZSt (Germany), SKAT (Denmark), and other countries.

Key constraints:
- Only valid for years the taxpayer was an Austrian resident.
- Reclaim windows: Germany 4 years, Denmark 3 years, France 2 years.
- Exact dividend payment dates (required on official forms) must be taken from
  the IB Annual Tax Report — TT-AUT exports only carry a year-end fallback date.
"""

from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Optional

from core.models import NormalizedTransaction, TransactionType

ZERO = Decimal("0")

# Per-country reclaim metadata
COUNTRY_RECLAIM_INFO = {
    "DE": {
        "name": "Germany",
        "authority": "BZSt — Bundeszentralamt für Steuern",
        "form": "Antrag auf Erstattung der deutschen Kapitalertragsteuer (§ 50d EStG)",
        "url": "https://www.bzst.de/",
        "window": 4,
        "notes": [
            "File the Ansässigkeitsbescheinigung (ZS-AD) from the Austrian Finanzamt with the application.",
            "BZSt accepts applications by post. Include broker tax certificate (IBKR Jahressteuerbescheinigung).",
        ],
    },
    "DK": {
        "name": "Denmark",
        "authority": "SKAT",
        "form": "Form 06.003 — Claim for Refund of Danish Dividend Tax",
        "url": "https://www.skat.dk/",
        "window": 3,
        "notes": [
            "DK domestic WHT = 27%; AT-DK DBA caps creditable at 15%; excess 12% reclaimable.",
            "Novo Nordisk (NOV): confirm payment date from IBKR Annual Tax Report.",
        ],
    },
    "FR": {
        "name": "France",
        "authority": "French Tax Authority (DGFiP)",
        "form": "Cerfa n°12816 — Formulaire 5000 + 5001 (EU residents)",
        "url": "https://www.impots.gouv.fr/",
        "window": 2,
        "notes": [
            "FR domestic WHT for non-residents: 25% (2023+). AT-FR DBA caps at 15%; 10% excess reclaimable.",
            "Note: Some sources cite 12.8% PFU for EU residents — verify the applicable rate for each dividend.",
        ],
    },
    "NL": {
        "name": "Netherlands",
        "authority": "Belastingdienst",
        "form": "IB 92 Form — Verzoek om teruggaaf dividendbelasting",
        "url": "https://www.belastingdienst.nl/",
        "window": 3,
        "notes": [
            "NL domestic WHT = 15%. AT-NL DBA also 15% — no excess WHT normally reclaimable.",
        ],
    },
}


def write_wht_reclaim_report(
    transactions: list[NormalizedTransaction],
    config: dict,
    tax_year: int,
    person_label: str,
    output_path: Path,
) -> None:
    """Generate WHT reclaim text report covering all claimable years."""
    max_creditable = Decimal(str(config.get("max_creditable_wht", "0.15")))
    wht_treaty = {k: Decimal(str(v)) for k, v in config.get("wht_treaty_rates", {}).items()}
    at_residency_start = config.get("at_residency_start_year", tax_year)

    # Collect per-country per-year data for all dividends since Austrian residency
    # Structure: country → year → [RecordEntry]
    data: dict[str, dict[int, list[dict]]] = defaultdict(lambda: defaultdict(list))

    for txn in transactions:
        if txn.txn_type != TransactionType.DIVIDEND:
            continue
        yr = txn.trade_date.year
        if yr < at_residency_start:
            continue

        country = txn.country_code or ""
        if not country or country == "AT":
            continue  # skip domestic — no foreign reclaim

        gross_eur = txn.eur_amount or ZERO
        wht_eur   = txn.eur_wht or ZERO
        if wht_eur <= ZERO:
            continue  # no WHT paid

        treaty_rate = wht_treaty.get(country, max_creditable)
        creditable  = min(wht_eur, gross_eur * treaty_rate)
        excess      = wht_eur - creditable

        if excess <= Decimal("0.05"):
            continue  # below rounding threshold

        data[country][yr].append({
            "symbol":      txn.symbol,
            "isin":        txn.isin or "",
            "description": txn.description,
            "trade_date":  txn.trade_date,
            "gross_orig":  txn.orig_amount,
            "currency":    txn.orig_currency,
            "gross_eur":   gross_eur,
            "wht_eur":     wht_eur,
            "creditable":  creditable,
            "excess":      excess,
            "treaty_rate": treaty_rate,
        })

    if not data:
        return  # nothing to reclaim

    today = date.today()
    max_year = max((yr for yrs in data.values() for yr in yrs), default=tax_year)
    lines: list[str] = []

    def h1(text: str) -> None:
        lines.append("=" * 70)
        lines.append(f"  {text}")
        lines.append("=" * 70)

    def h2(text: str) -> None:
        lines.append("")
        lines.append(f"  ── {text} " + "─" * max(0, 63 - len(text)))

    def row(label: str, value: str, indent: int = 2) -> None:
        pad = "  " * indent
        lines.append(f"{pad}{label:<28}{value}")

    h1(f"WHT RECLAIM ASSISTANT — {person_label}")
    lines.append(f"  Generated: {today.isoformat()}  |  Austrian resident from: {at_residency_start}")
    if max_year > tax_year:
        lines.append(f"  Covering tax years: {at_residency_start} – {max_year}  (incl. partial {max_year} data)")
    else:
        lines.append(f"  Covering tax years: {at_residency_start} – {tax_year}")
    lines.append("")
    lines.append("  IMPORTANT: Exact dividend payment dates required on official forms.")
    lines.append("  Use this report to identify reclaimable amounts. Obtain exact dates")
    lines.append("  from your IBKR Jahressteuerbescheinigung / Annual Tax Report.")
    lines.append("")

    # Country order: DE first, then DK, then others alphabetically
    priority = ["DE", "DK", "FR", "NL"]
    sorted_countries = sorted(data.keys(), key=lambda c: (priority.index(c) if c in priority else 99, c))

    grand_total_excess = ZERO

    for country in sorted_countries:
        country_info = COUNTRY_RECLAIM_INFO.get(country, {
            "name": country,
            "authority": f"Tax authority of {country}",
            "form": "Country-specific refund form",
            "url": "",
            "window": 4,
            "notes": [],
        })

        years_data = data[country]
        country_excess_total = sum(
            entry["excess"] for yr_data in years_data.values() for entry in yr_data
        )
        grand_total_excess += country_excess_total

        h2(f"{country_info['name']} ({country})  —  Total excess: EUR {country_excess_total:,.2f}")
        lines.append("")
        row("Authority:", country_info["authority"])
        row("Form:", country_info["form"])
        if country_info.get("url"):
            row("URL:", country_info["url"])
        deadline_base = min(years_data.keys())
        deadline_yr   = deadline_base + country_info["window"]
        row("Deadline (earliest year):", f"{deadline_yr}-12-31  (for {deadline_base} dividends)")
        lines.append("")

        for note in country_info.get("notes", []):
            lines.append(f"    ℹ  {note}")
        if country_info.get("notes"):
            lines.append("")

        # Per-year breakdown
        for yr in sorted(years_data.keys()):
            entries = years_data[yr]
            yr_gross  = sum(e["gross_eur"] for e in entries)
            yr_wht    = sum(e["wht_eur"]   for e in entries)
            yr_credit = sum(e["creditable"] for e in entries)
            yr_excess = sum(e["excess"]     for e in entries)

            claim_deadline = yr + country_info["window"]
            days_left      = (date(claim_deadline, 12, 31) - today).days

            lines.append(f"  ┌─ {yr}  (deadline: {claim_deadline}-12-31, {days_left} days left)")
            lines.append(f"  │  Gross dividends from {country}:   EUR {yr_gross:>10,.2f}")
            lines.append(f"  │  WHT paid:                        EUR {yr_wht:>10,.2f}")
            lines.append(f"  │  Creditable @ {float(entries[0]['treaty_rate']):.0%}:              EUR {yr_credit:>10,.2f}")
            lines.append(f"  │  Excess → RECLAIM:                EUR {yr_excess:>10,.2f}")
            lines.append(f"  │")
            lines.append(f"  │  Per-stock breakdown:")

            # Group entries by symbol for cleaner display
            sym_totals: dict[str, dict] = {}
            for e in entries:
                sym = e["symbol"]
                if sym not in sym_totals:
                    sym_totals[sym] = {
                        "isin": e["isin"],
                        "gross_eur": ZERO, "wht_eur": ZERO, "excess": ZERO,
                        "currency": e["currency"],
                    }
                sym_totals[sym]["gross_eur"] += e["gross_eur"]
                sym_totals[sym]["wht_eur"]   += e["wht_eur"]
                sym_totals[sym]["excess"]    += e["excess"]

            # Header
            lines.append(f"  │  {'Symbol':<10} {'ISIN':<14} {'Gross EUR':>12}  {'WHT EUR':>10}  {'Excess EUR':>10}")
            lines.append(f"  │  {'─'*10} {'─'*14} {'─'*12}  {'─'*10}  {'─'*10}")
            for sym, st in sorted(sym_totals.items(), key=lambda x: -x[1]["excess"]):
                lines.append(
                    f"  │  {sym:<10} {st['isin']:<14} {float(st['gross_eur']):>12,.2f}  "
                    f"{float(st['wht_eur']):>10,.2f}  {float(st['excess']):>10,.2f}"
                )
            lines.append(f"  └─ Subtotal {yr}:  Reclaim EUR {yr_excess:,.2f}")
            lines.append("")

    # Grand total
    lines.append("─" * 70)
    lines.append(f"  TOTAL RECLAIMABLE (all countries, {at_residency_start}–{tax_year}):   EUR {grand_total_excess:,.2f}")
    lines.append("─" * 70)
    lines.append("")
    lines.append("  NEXT STEPS:")
    lines.append("  1. Obtain Ansässigkeitsbescheinigung (ZS-AD) from Austrian Finanzamt")
    lines.append("     → Filed 2026-05-03 (confirm receipt and valid date range)")
    lines.append("  2. Obtain IBKR Annual Tax Report (Jahressteuerbescheinigung)")
    lines.append("     → Contains exact payment dates needed on BZSt and SKAT forms")
    lines.append("  3. Germany (BZSt): submit for 2024 + 2025 (deadline 2028/2029)")
    lines.append("     → bzst.de → 'Erstattung Kapitalertragsteuer Ausländer'")
    lines.append("  4. Denmark (SKAT): submit Form 06.003 for 2024 + 2025 (deadline 2027/2028)")
    lines.append("     → skat.dk → 'Refund of Danish dividend tax' → Form 06.003")
    lines.append("  5. France: verify applicable rate, then decide whether to file")
    lines.append("     → 2-year window: 2025 deadline = 2027")
    lines.append("")
    lines.append("  This report is informational. Verify with your tax consultant.")
    lines.append("=" * 70)

    output_path.write_text("\n".join(lines), encoding="utf-8")
