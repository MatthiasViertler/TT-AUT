"""
Arbeitnehmerveranlagung (ANV) Checklist — per-person deduction reminder.

The ANV is filed via the Austrian L1 form alongside E1kv.  This module
produces a plain-text checklist: auto-calculated deductions from config
plus a manual TODO list for items that need receipts or verification.

Config keys (all under `anv:` in config.local.yaml — set per person):
  home_office_days          — days worked from home (€3/day, max 100 → max €300)
  home_office_equipment_eur — home-office furniture/equipment (max €300)
  commute_km                — one-way commute distance in km (0 = no commute)
  commute_type              — "public" (Kleines Pendlerpauschale) or "car" (Großes)
  commute_days_per_year     — days actually commuting (default 220; PP requires >50% of workdays)
  kirchenbeitrag_eur        — church tax paid (deductible up to €400)
  donations_eur             — donations to BMF-approved Spendenempfänger
  tax_advisor_eur           — tax advisor / accountant fees (fully deductible)
  union_fees_eur            — Gewerkschaftsbeitrag
  training_eur              — Fortbildungskosten (professional training)
  professional_books_eur    — Fachliteratur (professional books / subscriptions)
  work_equipment_eur        — Arbeitsmittel (laptop, monitor, desk — home office)
  family_bonus_children     — number of children under 18 (Familienbonus Plus €2,000/child)
  prior_year_income_eur     — prior year gross income (donation limit = 10% of this)
"""

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

ZERO = Decimal("0")

# 2025 Pendlerpauschale rates (annual, EUR)
_PP_PUBLIC = [(20, 696), (40, 1356), (60, 2016)]   # Kleines — public transport available
_PP_CAR    = [(2, 372),  (20, 1476), (40, 2568), (60, 3672)]  # Großes — no public transport


def _pendlerpauschale(km: float, typ: str) -> float:
    """Return annual Pendlerpauschale for one-way commute of `km` km."""
    if km <= 0:
        return 0.0
    table = _PP_PUBLIC if typ == "public" else _PP_CAR
    result = 0.0
    for threshold, amount in table:
        if km > threshold:
            result = amount
    return result


def write_anv_checklist(
    config: dict,
    tax_year: int,
    person_label: str,
    path: Path,
) -> None:
    """Generate the ANV checklist text file."""
    anv = config.get("anv", {})
    if not anv:
        return  # no ANV config → skip silently

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # ── Read config ───────────────────────────────────────────────────────────
    ho_days       = int(anv.get("home_office_days", 0))
    ho_equip      = float(anv.get("home_office_equipment_eur", 0))
    commute_km    = float(anv.get("commute_km", 0))
    commute_type  = str(anv.get("commute_type", "public")).lower()
    commute_days  = int(anv.get("commute_days_per_year", 220))
    kirche        = float(anv.get("kirchenbeitrag_eur", 0))
    donations     = float(anv.get("donations_eur", 0))
    tax_adv       = float(anv.get("tax_advisor_eur", 0))
    union         = float(anv.get("union_fees_eur", 0))
    training      = float(anv.get("training_eur", 0))
    books         = float(anv.get("professional_books_eur", 0))
    equipment     = float(anv.get("work_equipment_eur", 0))
    fb_children   = int(anv.get("family_bonus_children", 0))
    prior_income  = float(anv.get("prior_year_income_eur", 0))

    # ── Calculations ──────────────────────────────────────────────────────────
    ho_capped     = min(ho_days, 100)
    ho_pauschale  = ho_capped * 3.0
    ho_equip_ded  = min(ho_equip, 300.0)

    pp_amount     = _pendlerpauschale(commute_km, commute_type)
    pendler_euro  = commute_km * 2.0  # direct tax credit, not income deduction

    kirche_ded    = min(kirche, 400.0)
    donation_max  = prior_income * 0.10 if prior_income > 0 else donations
    donation_ded  = min(donations, donation_max) if prior_income > 0 else donations

    wk_itemized = sum([
        ho_pauschale, ho_equip_ded,
        tax_adv, union, training, books, equipment,
    ])
    wk_net = max(wk_itemized, 132.0)  # employer Pauschale is €132 baseline

    lines: list[str] = []

    def sep(char="=", width=64): lines.append(char * width)
    def blank(): lines.append("")
    def hdr(text): lines.extend(["", "  " + text, "  " + "-" * (len(text) + 2)])
    def row(label, amount, note=""):
        amt_str = f"EUR {amount:>10,.2f}" if amount else "            —"
        suffix  = f"  ({note})" if note else ""
        lines.append(f"  {label:<42}{amt_str}{suffix}")
    def todo(text): lines.append(f"  [ ] {text}")
    def info(text): lines.append(f"      {text}")
    def note(text): lines.append(f"  ⚠  {text}")

    # ── Header ────────────────────────────────────────────────────────────────
    sep()
    lines.append(f"  ARBEITNEHMERVERANLAGUNG — DEDUCTION CHECKLIST")
    lines.append(f"  Person : {person_label}")
    lines.append(f"  Year   : {tax_year}")
    lines.append(f"  Created: {now}")
    sep()
    blank()
    lines.append("  File via FinanzOnline: Erklärungen → Arbeitnehmerveranlagung (L1)")
    lines.append(f"  Deadline: {tax_year + 5}-12-31  (5-year window for voluntary refund)")
    lines.append("  Urgent deadline if income tax withheld: no urgency, but refund only")
    lines.append("  after filing. Typical refund paid within 4–8 weeks.")
    blank()

    # ── 1. Werbungskosten ────────────────────────────────────────────────────
    hdr("1. WERBUNGSKOSTEN  (work-related expenses)")
    blank()
    lines.append("  AUTO-CALCULATED from config:")
    blank()

    if ho_days > 0:
        row(f"Homeoffice-Pauschale ({ho_capped} days × €3)",
            ho_pauschale,
            f"capped at 100 days" if ho_days > 100 else "")
        if ho_days > 100:
            note(f"You entered {ho_days} days — only 100 days (€300) are deductible.")
    else:
        lines.append("  Homeoffice-Pauschale:  not configured (home_office_days = 0)")

    if ho_equip > 0:
        row(f"Home-office Ausstattung (equipment)",
            ho_equip_ded,
            f"capped at €300" if ho_equip > 300 else "")
    if union > 0:
        row("Gewerkschaftsbeitrag (union fees)", union)
    if training > 0:
        row("Fortbildungskosten (training)", training, "keep invoices + program description")
    if books > 0:
        row("Fachliteratur (professional books/subscriptions)", books, "keep receipts")
    if equipment > 0:
        row("Arbeitsmittel (work equipment)", equipment, "keep receipts")
    if tax_adv > 0:
        row("Steuerberatungskosten (tax advisor)", tax_adv, "fully deductible")

    blank()
    lines.append("  MANUAL — items to collect receipts for:")
    blank()
    todo("Professional training not yet in config (Fortbildungskosten)")
    info("→ Course fee invoices, program / certificate of attendance")
    todo("Professional books / subscriptions (Fachliteratur)")
    info("→ Receipts; only journals / books directly related to your job")
    todo("Work equipment purchased for home office (Arbeitsmittel)")
    info("→ Receipts; items > €1,000 net must be depreciated over useful life")
    todo("Uniform / protective clothing (Berufskleidung) — if applicable")
    todo("Double household (doppelte Haushaltsführung) — if you maintain two residences for work")

    blank()
    sep("-")
    if wk_itemized > 132:
        lines.append(f"  Itemized Werbungskosten total:  EUR {wk_itemized:>10,.2f}")
        lines.append(f"  Auto Pauschale (min.):          EUR {132.00:>10,.2f}")
        lines.append(f"  ✓ Itemizing saves EUR {wk_itemized - 132.0:,.2f} vs. Pauschale — WORTH FILING")
    elif wk_itemized > 0:
        lines.append(f"  Itemized Werbungskosten total:  EUR {wk_itemized:>10,.2f}")
        lines.append(f"  Auto Pauschale (min.):          EUR {132.00:>10,.2f}")
        lines.append(f"  Pauschale is higher — but manual items may close the gap.")
    else:
        lines.append(f"  No Werbungskosten configured — employer Pauschale of €132 applies automatically.")
    sep("-")
    blank()

    # ── 2. Pendlerpauschale ──────────────────────────────────────────────────
    hdr("2. PENDLERPAUSCHALE + PENDLEREURO")
    blank()
    if commute_km > 0:
        pp_label = "Kleines (public transport)" if commute_type == "public" else "Großes (no public transport)"
        lines.append(f"  Commute:  {commute_km:.0f} km one-way  |  type: {pp_label}")
        lines.append(f"  Working days configured: {commute_days}")
        blank()
        if pp_amount > 0:
            row("Pendlerpauschale (annual)", pp_amount)
            row("Pendlereuro (direct tax credit, not deduction)", pendler_euro,
                f"{commute_km:.0f} km × €2")
            blank()
            note(f"Pendlerpauschale only applies if you commute on >50% of working days.")
            note(f"Use BMF Pendlerrechner to confirm: https://pendlerrechner.bmf.gv.at/")
            blank()
            todo("Confirm commute days via employment record or calendar")
            todo("Run BMF Pendlerrechner — screenshot/printout for documentation")
            if commute_type == "public":
                todo("Confirm public transport is available (Klimaticket or monthly pass receipt)")
        else:
            lines.append(f"  Commute of {commute_km:.0f} km is below the Pendlerpauschale threshold")
            lines.append(f"  (Kleines: >20 km; Großes: >2 km) — Verkehrsabsetzbetrag (€421) applies automatically.")
    else:
        lines.append("  No commute configured (commute_km = 0).")
        lines.append("  Verkehrsabsetzbetrag of €421 is applied automatically by the employer (L16).")
        todo("Confirm: do you commute regularly? If so, set commute_km in config.local.yaml")
    blank()

    # ── 3. Sonderausgaben ────────────────────────────────────────────────────
    hdr("3. SONDERAUSGABEN  (special expenses)")
    blank()
    lines.append("  AUTO-CALCULATED from config:")
    blank()
    if kirche > 0:
        row(f"Kirchenbeitrag", kirche_ded,
            f"capped at €400" if kirche > 400 else "")
    if donations > 0:
        if prior_income > 0:
            row(f"Spenden (donations)", donation_ded,
                f"max 10% of prior income €{prior_income:,.0f}")
        else:
            row(f"Spenden (donations)", donation_ded,
                "set prior_year_income_eur in config for limit check")
    if tax_adv == 0:
        lines.append("  Steuerberatungskosten: not configured — set tax_advisor_eur if applicable")
    blank()
    lines.append("  MANUAL — items to check:")
    blank()
    todo("Kirchenbeitrag — annual invoice from your church (if applicable)")
    todo("Donations — official receipts from BMF-listed Spendenempfänger")
    info("→ Check list at: https://service.bmf.gv.at/Service/Anw/Behoerden/SpendenBeg.aspx")
    todo("Steuerberatungskosten — invoice from tax advisor (fully deductible)")
    todo("Private Versicherungen Altverträge — only pre-2016 life/health insurance contracts")
    info("→ New contracts since 2016 are NOT deductible")
    todo("Wohnraumschaffung Altverträge — only pre-2016 building-society (Bausparer) contracts")
    blank()

    # ── 4. Außergewöhnliche Belastungen ──────────────────────────────────────
    hdr("4. AUßERGEWÖHNLICHE BELASTUNGEN  (extraordinary burdens)")
    blank()
    lines.append("  These require a Selbstbehalt (co-payment) based on income — typically")
    lines.append("  6–12% of income. Only the excess above the Selbstbehalt is deductible.")
    blank()
    todo("Medical expenses not covered by insurance (doctor, hospital, medication)")
    info("→ Collect all invoices; subtract any health insurance reimbursements")
    todo("Dental / vision costs above standard coverage")
    todo("Disability (Behinderung) — claim Freibetrag for permanent disability")
    info("→ Requires medical certificate (Bescheid des Sozialministeriumservice)")
    todo("Care costs (Pflege) for dependent relatives — if applicable")
    todo("Funeral costs (Begräbniskosten) — limited deduction for death of close relative")
    blank()

    # ── 5. Absetzbeträge / Credits ───────────────────────────────────────────
    hdr("5. ABSETZBETRÄGE  (direct tax credits — high impact)")
    blank()
    if fb_children > 0:
        fb_total = fb_children * 2000.0
        lines.append(f"  Familienbonus Plus: {fb_children} child(ren) × €2,000 = EUR {fb_total:,.2f}/year")
        lines.append(f"  Can be split: each parent claims €1,000 per child.")
        lines.append(f"  Requires: birth certificate + proof of Familienbeihilfe entitlement.")
        blank()
        todo(f"Claim Familienbonus Plus for {fb_children} child(ren) on L1 form, section 'Absetzbeträge'")
        todo("If splitting with partner: both file L1 claiming €1,000 each per child")
        todo("Child attending university (18–24): reduced rate €700/child — verify eligibility")
    else:
        todo("Familienbonus Plus — do you have children under 18? €2,000/child direct tax credit")
        info("→ Set family_bonus_children in config.local.yaml if applicable")
    blank()
    todo("Alleinverdienerabsetzbetrag (€494+) — if partner earns < €6,000/year")
    todo("Alleinerzieherabsetzbetrag (€494+) — if single parent")
    todo("Unterhaltsabsetzbetrag — if paying child support for children not in your household")
    blank()

    # ── 6. Documents checklist ───────────────────────────────────────────────
    hdr("6. DOCUMENTS TO GATHER BEFORE FILING")
    blank()
    lines.append("  From your employer:")
    todo("Lohnzettel (L16) — auto-transmitted to Finanzamt; verify via FinanzOnline")
    todo("Any Lohnsteuerausgleich from prior years if not yet filed")
    blank()
    lines.append("  From your broker (already generated by this tool):")
    todo(f"E1kv Kennziffern — users/{person_label}/output/{person_label}_{tax_year}_tax_summary.txt")
    todo(f"Supporting detail — users/{person_label}/output/{person_label}_{tax_year}_dashboard.xlsx")
    blank()
    lines.append("  General:")
    todo("IBAN for refund — verify bank details in FinanzOnline profile")
    todo("Austrian tax ID (Steuernummer) — check your last Bescheid or FinanzOnline profile")
    blank()

    # ── 7. Filing steps ──────────────────────────────────────────────────────
    hdr("7. FILING STEPS")
    blank()
    lines.append("  1. Log in to FinanzOnline: https://finanzonline.bmf.gv.at/")
    lines.append("  2. Erklärungen → Arbeitnehmerveranlagung (L1)")
    lines.append(f"     Select year: {tax_year}")
    lines.append("  3. Fill in Werbungskosten (section 4 of the L1 form)")
    lines.append("  4. Fill in Sonderausgaben (section 5)")
    lines.append("  5. Fill in Außergewöhnliche Belastungen (section 6) if applicable")
    lines.append("  6. Add E1kv — in the same FinanzOnline session:")
    lines.append("     Erklärungen → Beilage E1kv → enter the Kennziffern from tax_summary.txt")
    lines.append("  7. Submit → you will receive a Bescheid within a few weeks")
    blank()

    # ── Footer ───────────────────────────────────────────────────────────────
    sep()
    lines.append("  This checklist is informational. Verify amounts with a Steuerberater.")
    lines.append(f"  Generated: {now}")
    sep()

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
