"""
Output module.
Generates four artefacts per run:

1.  {person}_{year}_transactions.csv   — full normalized transaction log
2.  {person}_{year}_tax_summary.txt    — E1kv Kennziffern, ready to copy into FinanzOnline
3.  {person}_{year}_dashboard.xlsx     — Excel workbook with dashboard + detail tabs
4.  {person}_{year}_freedom.html       — interactive financial independence dashboard

openpyxl is used for Excel (pure Python, no COM/xlwings dependency).
"""

import csv
import logging
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional

try:
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

from core.models import NormalizedTransaction, TaxSummary, TransactionType
from output.freedom import write_freedom_html

log = logging.getLogger(__name__)
ZERO = Decimal("0")


def write_all(
    transactions: list[NormalizedTransaction],
    summary: TaxSummary,
    output_dir: Path,
    config: dict,
) -> None:
    slug = f"{summary.person_label}_{summary.tax_year}"
    opts = config.get("output", {})

    if opts.get("csv", True):
        p = output_dir / f"{slug}_transactions.csv"
        _write_csv(transactions, p)
        print(f"  [out]    {p}")

    if opts.get("tax_summary", True):
        p = output_dir / f"{slug}_tax_summary.txt"
        _write_tax_summary(summary, p)
        print(f"  [out]    {p}")

    if opts.get("excel", True):
        if OPENPYXL_AVAILABLE:
            p = output_dir / f"{slug}_dashboard.xlsx"
            _write_excel(transactions, summary, p)
            print(f"  [out]    {p}")
        else:
            log.warning("openpyxl not installed — skipping Excel output. "
                        "Run: pip install openpyxl")

    if opts.get("html", True):
        p = output_dir / f"{slug}_freedom.html"
        write_freedom_html(transactions, summary, p, config)
        print(f"  [out]    {p}")


# ── CSV ───────────────────────────────────────────────────────────────────────

HEADERS = [
    "trade_date", "settle_date", "broker", "txn_type", "symbol", "isin",
    "description", "country_code", "domicile", "asset_class",
    "quantity", "price", "price_currency",
    "orig_currency", "orig_amount",
    "commission", "commission_currency",
    "wht_rate_actual", "wht_amount_orig",
    "fx_rate_to_eur", "eur_amount", "eur_commission", "eur_wht",
    "notes",
]


def _write_csv(txns: list[NormalizedTransaction], path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(HEADERS)
        for t in sorted(txns, key=lambda x: x.trade_date):
            w.writerow([
                t.trade_date, t.settle_date, t.broker, t.txn_type.value,
                t.symbol, t.isin or "", t.description,
                t.country_code or "", t.domicile.value, t.asset_class.value,
                _fmt(t.quantity), _fmt(t.price), t.price_currency or "",
                t.orig_currency, _fmt(t.orig_amount),
                _fmt(t.commission), t.commission_currency or "",
                _fmt(t.wht_rate_actual), _fmt(t.wht_amount_orig),
                _fmt(t.fx_rate_to_eur), _fmt(t.eur_amount),
                _fmt(t.eur_commission), _fmt(t.eur_wht),
                t.notes,
            ])


def _fmt(v: Optional[Decimal]) -> str:
    if v is None:
        return ""
    return str(v.normalize())


# ── Tax Summary TXT ───────────────────────────────────────────────────────────

def _write_tax_summary(s: TaxSummary, path: Path) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "=" * 62,
        f"  KAPITALERTRAG — E1kv KENNZIFFERN",
        f"  Person : {s.person_label}",
        f"  Year   : {s.tax_year}",
        f"  Created: {now}",
        "=" * 62,
        "",
        "  ENTER THESE VALUES INTO FINANZONLINE / E1kv FORM:",
        "",
        f"  KZ 862   Inländ. Dividendenerträge          EUR {s.kz_862:>12,.2f}",
        f"  KZ 863   Ausländ. Dividendenerträge          EUR {s.kz_863:>12,.2f}",
        f"  KZ 981   Inländ. Kursgewinne                 EUR {s.kz_981:>12,.2f}",
        f"  KZ 994   Ausländ. Kursgewinne                EUR {s.kz_994:>12,.2f}",
        f"  KZ 891   Inländ. Kursverluste                EUR {s.kz_891:>12,.2f}",
        f"  KZ 892   Ausländ. Kursverluste               EUR {s.kz_892:>12,.2f}",
        f"  KZ 898   Ausschüttungen (Ausland)            EUR {s.kz_898:>12,.2f}",
        f"  KZ 937   Ausschüttungsgleiche Ertr. (Ausl.)  EUR {s.kz_937:>12,.2f}",
        f"  KZ 899   KESt inländ. WP im Ausland          EUR {s.kz_899:>12,.2f}",
        f"  KZ 998   Quellensteuer ausländ. Div.         EUR {s.kz_998:>12,.2f}",
        "",
        "─" * 62,
        f"  Net taxable income                           EUR {s.net_taxable_eur:>12,.2f}",
        f"  KESt due @ 27.5%                             EUR {s.kest_due_eur:>12,.2f}",
        f"  WHT creditable (max 15%)                     EUR {s.wht_creditable_eur:>12,.2f}",
        f"  KESt remaining to pay                        EUR {s.kest_remaining_eur:>12,.2f}",
        "─" * 62,
        "",
        f"  Transactions processed : {s.transaction_count}",
        f"  Unmatched sells        : {s.unmatched_sells}",
        f"  Missing FX rates       : {s.missing_fx_count}",
        "",
    ]

    if s.warnings:
        lines.append(f"  WARNINGS ({len(s.warnings)}):")
        for w in s.warnings:
            lines.append(f"    • {w}")
        lines.append("")

    lines += [
        "  NOTE: KZ 937 (Ausschüttungsgleiche Erträge) requires OeKB",
        "  fund data and is NOT automatically calculated. Check your",
        "  broker's tax report or oekb.at for any ETF/fund holdings.",
        "",
        "  This output is informational. Verify with your tax consultant.",
        "=" * 62,
    ]

    path.write_text("\n".join(lines), encoding="utf-8")


# ── Excel Dashboard ───────────────────────────────────────────────────────────

def _write_excel(txns: list[NormalizedTransaction],
                 summary: TaxSummary, path: Path) -> None:
    from openpyxl import Workbook

    wb = Workbook()

    # ── Tab 1: E1kv Summary (for tax consultant) ──────────────────────────────
    ws = wb.active
    ws.title = "E1kv Summary"
    _fill_summary_sheet(ws, summary)

    # ── Tab 2: All Transactions ───────────────────────────────────────────────
    wt = wb.create_sheet("Transactions")
    _fill_transactions_sheet(wt, txns, summary.tax_year)

    # ── Tab 3: Dividends only ─────────────────────────────────────────────────
    wd = wb.create_sheet("Dividends")
    div_txns = [t for t in txns
                if t.txn_type == TransactionType.DIVIDEND
                and t.trade_date.year == summary.tax_year]
    _fill_transactions_sheet(wd, div_txns, summary.tax_year, title="Dividends")

    # ── Tab 4: Trades only ────────────────────────────────────────────────────
    wtr = wb.create_sheet("Trades")
    trade_txns = [t for t in txns
                  if t.txn_type in (TransactionType.BUY, TransactionType.SELL)
                  and t.trade_date.year == summary.tax_year]
    _fill_transactions_sheet(wtr, trade_txns, summary.tax_year, title="Trades")

    wb.save(path)


# ── Excel helpers ─────────────────────────────────────────────────────────────

HEADER_FILL  = "1F3864"   # dark navy
ACCENT_FILL  = "2E75B6"   # mid blue
LIGHT_FILL   = "DEEAF1"   # pale blue
WARN_FILL    = "FFF2CC"   # yellow
GREEN_FILL   = "E2EFDA"
RED_FILL     = "FCE4D6"
WHITE        = "FFFFFF"


def _hfill(color): return PatternFill("solid", fgColor=color)
def _font(bold=False, color="000000", size=11):
    return Font(bold=bold, color=color, size=size)
def _border():
    s = Side(style="thin", color="BBBBBB")
    return Border(left=s, right=s, top=s, bottom=s)
def _center(): return Alignment(horizontal="center", vertical="center")
def _right():  return Alignment(horizontal="right",  vertical="center")


def _fill_summary_sheet(ws, s: TaxSummary) -> None:
    ws.column_dimensions["A"].width = 8
    ws.column_dimensions["B"].width = 46
    ws.column_dimensions["C"].width = 18

    def hdr(row, text, color=HEADER_FILL):
        ws.merge_cells(f"A{row}:C{row}")
        c = ws[f"A{row}"]
        c.value = text
        c.font = _font(bold=True, color=WHITE, size=12)
        c.fill = _hfill(color)
        c.alignment = _center()
        ws.row_dimensions[row].height = 22

    def kz(row, kennziffer, label, value, fill=None):
        ws[f"A{row}"] = kennziffer
        ws[f"A{row}"].font = _font(bold=True)
        ws[f"A{row}"].alignment = _center()
        ws[f"B{row}"] = label
        ws[f"B{row}"].font = _font()
        ws[f"C{row}"] = float(value)
        ws[f"C{row}"].number_format = '#,##0.00 "EUR"'
        ws[f"C{row}"].alignment = _right()
        if fill:
            for col in "ABC":
                ws[f"{col}{row}"].fill = _hfill(fill)

    def blank(row):
        ws.row_dimensions[row].height = 6

    hdr(1, f"E1kv — Kapitalvermögen  |  {s.person_label}  |  {s.tax_year}")
    blank(2)
    hdr(3, "DIVIDENDEN", ACCENT_FILL)
    kz(4, "862", "Inländische Dividendenerträge",        s.kz_862, LIGHT_FILL)
    kz(5, "863", "Ausländische Dividendenerträge",       s.kz_863)
    blank(6)
    hdr(7, "KURSGEWINNE / KURSVERLUSTE", ACCENT_FILL)
    kz(8, "981", "Inländische Kursgewinne",              s.kz_981, LIGHT_FILL)
    kz(9, "994", "Ausländische Kursgewinne",             s.kz_994)
    kz(10,"891", "Inländische Kursverluste",             s.kz_891, RED_FILL)
    kz(11,"892", "Ausländische Kursverluste",            s.kz_892, RED_FILL)
    blank(12)
    hdr(13,"AUSSCHÜTTUNGEN", ACCENT_FILL)
    kz(14,"898", "Ausschüttungen (Ausland)",             s.kz_898, LIGHT_FILL)
    kz(15,"937", "Ausschüttungsgleiche Erträge (Ausl.)", s.kz_937, WARN_FILL)
    blank(16)
    hdr(17,"BEREITS BEZAHLTE STEUER", ACCENT_FILL)
    kz(18,"899", "KESt für inländ. WP im Ausland",      s.kz_899, LIGHT_FILL)
    kz(19,"998", "Quellensteuer ausländ. Dividenden",   s.kz_998, GREEN_FILL)
    blank(20)
    hdr(21,"BERECHNUNG", ACCENT_FILL)
    kz(22,"",    "Steuerpflichtiger Gesamtbetrag",       s.net_taxable_eur, LIGHT_FILL)
    kz(23,"",    "KESt (27,5%)",                         s.kest_due_eur)
    kz(24,"",    "Anrechenbare Quellensteuer",           s.wht_creditable_eur, GREEN_FILL)
    kz(25,"",    "Verbleibende KESt",                    s.kest_remaining_eur, WARN_FILL)

    # Borders
    for row in range(3, 26):
        for col in "ABC":
            ws[f"{col}{row}"].border = _border()

    # Warning about KZ 937
    ws["A27"] = "⚠  KZ 937 nicht automatisch berechnet — OeKB-Daten erforderlich"
    ws["A27"].font = Font(color="C00000", italic=True, size=10)
    ws.merge_cells("A27:C27")


def _fill_transactions_sheet(ws, txns: list[NormalizedTransaction],
                               year: int, title: str = "Transactions") -> None:
    headers = [
        "Date", "Type", "Symbol", "ISIN", "Description",
        "Country", "Domicile", "Qty", "Currency",
        "Orig Amount", "Commission", "WHT (orig)",
        "FX Rate", "EUR Amount", "EUR Commission", "EUR WHT",
        "Notes",
    ]

    # Header row
    ws.append(headers)
    for col_idx, _ in enumerate(headers, 1):
        cell = ws.cell(1, col_idx)
        cell.font = _font(bold=True, color=WHITE)
        cell.fill = _hfill(HEADER_FILL)
        cell.alignment = _center()
        cell.border = _border()

    txns_sorted = sorted(txns, key=lambda t: t.trade_date)
    for t in txns_sorted:
        row = [
            t.trade_date.isoformat(),
            t.txn_type.value,
            t.symbol,
            t.isin or "",
            t.description[:60],
            t.country_code or "",
            t.domicile.value,
            float(t.quantity) if t.quantity else "",
            t.orig_currency,
            float(t.orig_amount),
            float(t.commission) if t.commission else "",
            float(t.wht_amount_orig) if t.wht_amount_orig else "",
            float(t.fx_rate_to_eur) if t.fx_rate_to_eur else "",
            float(t.eur_amount) if t.eur_amount else "",
            float(t.eur_commission) if t.eur_commission else "",
            float(t.eur_wht) if t.eur_wht else "",
            t.notes,
        ]
        ws.append(row)

    # Auto-width columns
    for col_idx in range(1, len(headers) + 1):
        col_letter = get_column_letter(col_idx)
        max_len = max(
            (len(str(ws.cell(row_idx, col_idx).value or ""))
             for row_idx in range(1, ws.max_row + 1)),
            default=8,
        )
        ws.column_dimensions[col_letter].width = min(max_len + 2, 40)

    # Freeze header row
    ws.freeze_panes = "A2"

    # Number format for EUR columns
    eur_cols = [10, 11, 12, 14, 15, 16]
    for row_idx in range(2, ws.max_row + 1):
        for col_idx in eur_cols:
            ws.cell(row_idx, col_idx).number_format = '#,##0.00'



