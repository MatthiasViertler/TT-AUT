# Kapitalertrag

Austrian capital gains tax calculator. Parses Interactive Brokers exports, applies KeSt rules (FIFO, WHT crediting, Nichtmeldefonds), and produces ready-to-file E1kv Kennziffern plus an Excel dashboard and a financial freedom projection.

> **Personal tool** — built for Austrian tax residents with Interactive Brokers accounts. Contributions welcome, but no guarantees. Always verify output against your broker statements and consult a tax advisor for edge cases.

---

## What it produces

For each run (`--person`, `--year`):

| File | Contents |
|------|----------|
| `output/{person}_{year}_tax_summary.txt` | E1kv Kennziffern ready to copy into FinanzOnline |
| `output/{person}_{year}_transactions.csv` | Full transaction log with FX rates, cost basis, gain/loss |
| `output/{person}_{year}_dashboard.xlsx` | Excel workbook — E1kv Summary, Overview (Verlustausgleich), Transactions, Dividends, Trades, Freedom, [Nichtmeldefonds] |
| `output/{person}_{year}_freedom.html` | Interactive financial independence dashboard (sliders) |
| `output/{person}_{year}_wht_reclaim.txt` | Per-country WHT reclaim report (if `at_residency_start_year` set) |
| `output/{person}_{year}_anv_checklist.txt` | L1 deduction checklist — Werbungskosten, Pendlerpauschale, Sonderausgaben, Familienbonus (if `anv:` set) |
| `output/{person}_{year}_summary.json` | Machine-readable year snapshot; populates the multi-year Overview tab |

FX rates are fetched from the ECB and cached locally — no API key needed.

---

## Supported brokers

| Broker | Format | Status |
|--------|--------|--------|
| Interactive Brokers — TT-AUT BOS/EOS | Matthias-style Flex Query CSV | ✓ supported |
| Interactive Brokers — HEADER/DATA | Jessie-style Flex Query CSV | ✓ supported |
| SAXO — ClosedPositions | Reports → ClosedPositions xlsx | ✓ supported (preferred for trades — real share quantities) |
| SAXO — AggregatedAmounts | Reports → AggregatedAmounts xlsx | ✓ supported (preferred for dividends; set `saxo_skip_agg_trades: true` when combined with ClosedPositions) |
| SAXO — ShareDividends | Reports → ShareDividends xlsx | ✓ supported (optional — better WHT detail) |
| E*Trade | — | planned |

---

## Setup

**Requirements:** Python 3.11+

```bash
git clone https://github.com/MatthiasViertler/TT-AUT.git
cd TT-AUT
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**Configure your account** — edit `config.yaml`:

```yaml
account_map:
  U11111111: Jessie      # find your account ID in the BOF row of any Flex Query export
  U22222222: Matthias
```

Real account IDs and personal settings go in `config.local.yaml` (gitignored, never committed):

```yaml
# config.local.yaml
account_map:
  U99999999: YourName

at_residency_start_year: 2024   # for WHT reclaim report

anv:                            # for L1 / Arbeitnehmerveranlagung checklist
  home_office_days: 80          # days worked from home (€3/day, max 100 → max €300)
  commute_km: 0                 # one-way km (>20 for Kleines PP; >2 for Großes PP)
  commute_type: public          # "public" or "car"
  kirchenbeitrag_eur: 0
  donations_eur: 0
  tax_advisor_eur: 0
  family_bonus_children: 0      # €2,000 direct tax credit per child under 18

freedom_dashboard:
  portfolio_eur: 50000
  monthly_expenses_eur: 2000
  monthly_contribution_eur: 500
  yield_pct: 3.5
  growth_pct: 7.0
```

---

## Getting an IB Flex Query export

In Client Portal / TWS:

1. **Reports → Flex Queries → Create**
2. Select **Activity Flex Query**
3. Include sections: **Trades**, **Cash Transactions**
4. Date range: full calendar year(s) you want to calculate
5. Format: **CSV**
6. Run query and save the file to `data/`

For multi-year FIFO accuracy, always pass **all years from your first trade** onward — cost basis is recalculated from scratch each run.

---

## Getting a SAXO export

In SAXO Client Portal → **Reports**:

**AggregatedAmounts** (mandatory for trades):
1. Reports → AggregatedAmounts → set date range to full calendar year
2. Export as xlsx → save to `data/`
3. This report contains both trades AND dividends — it is the primary input

**ShareDividends** (optional, better dividend data):
1. Reports → ShareDividends → set date range
2. Export as xlsx
3. **Do not pass ShareDividends alongside AggregatedAmounts for the same period** — dividends would be double-counted
4. Use ShareDividends only for periods where you have no AggregatedAmounts

**Corporate acquisitions** (e.g. SWAV acquired by J&J): these appear as "Corporate Actions - Cash Compensation" and are automatically treated as taxable SELL events.

**No per-share quantity**: SAXO exports carry no share quantity. Each trade is stored as one lot (quantity=1) at total trade price. For positions opened before your earliest AggregatedAmounts file, seed the FIFO queue with `manual_cost_basis` entries (see below).

### Recommended data folder structure

```
data/{person}/{broker}/{year}/
```

Example:
```
data/matthias/SAXO/2024/AggregatedAmounts_19999999_2024-01-01_2024-12-31.xlsx
data/matthias/SAXO/2025/AggregatedAmounts_19999999_2025-01-01_2025-12-31.xlsx
data/matthias/IB/2024/matthias_2024.csv
data/jessie/IB/2025/jessie_2025.csv
```

This prevents accidentally mixing files from different brokers or years. Pass files explicitly via `--input`.

---

## Usage

```bash
# Single year
python main.py --input data/2025.csv --year 2025

# Multi-year (required for correct FIFO if you bought before the tax year)
python main.py --input data/2023.csv data/2024.csv data/2025.csv --year 2025

# Explicit person label (overrides account_map lookup)
python main.py --input data/2025.csv --year 2025 --person matthias
```

All options:

```
--input FILE [FILE ...]   broker export file(s); multiple files are merged
--year INT                tax year to calculate
--person NAME             output label; default: auto-detected from account_map
--config FILE             config file path (default: config.yaml)
--output-dir DIR          output directory (default: ./output)
```

---

## Key tax rules implemented

- **FIFO** cost basis matching across all input files and years
- **KeSt rate:** 27.5% flat (§ 27a EStG)
- **WHT crediting:** up to treaty rate (default 15%) offset against Austrian KeSt
- **Domestic classification:** ISIN prefix `AT` or exchange `WBAG`/`XWBO`
- **WHT excess warning** when foreign withholding exceeds the creditable amount (> €0.05 threshold suppresses rounding noise)
- **Return of Capital** — groups detected by "return of capital" in description are skipped entirely
- **Corporate actions / mergers** — `symbol_aliases` in config maps sell-ticker → buy-ticker for FIFO matching
- **Nichtmeldefonds** (§ 186 InvFG) — pauschal AE = max(90% × annual gain, 10% × Dec31 price) per share; year-end prices auto-fetched from Yahoo Finance and cached
- **Manual cost basis override** — seed the FIFO queue for positions with no IB buy record (spin-offs, broker transfers)
- **KZ 937** (Ausschüttungsgleiche Erträge for accumulating funds) is **not** auto-calculated — requires OeKB data; flagged for manual entry

---

## Nichtmeldefonds (§ 186 InvFG)

For US REITs, BDCs, and other funds not registered with OeKB, add to `config.yaml`:

```yaml
nichtmeldefonds:
  - symbol: O              # Yahoo Finance ticker
    isin: US7561091049
    name: Realty Income Corp
    type: REIT
    currency: USD
```

Year-end prices are fetched automatically via yfinance and cached in `data/price_cache/`.

---

## Arbeitnehmerveranlagung checklist (L1 form)

Add an `anv:` section to `config.local.yaml` to generate a plain-text deduction checklist alongside the E1kv output:

```yaml
# config.local.yaml
anv:
  home_office_days: 80            # €3/day Homeoffice-Pauschale (max 100 days = €300)
  home_office_equipment_eur: 200  # home-office furniture/equipment (max €300)
  commute_km: 0                   # one-way commute km (0 = no commute)
  commute_type: public            # "public" (Kleines PP) or "car" (Großes PP)
  kirchenbeitrag_eur: 0
  donations_eur: 0
  tax_advisor_eur: 0
  union_fees_eur: 0
  training_eur: 0
  professional_books_eur: 0
  work_equipment_eur: 0
  family_bonus_children: 0        # €2,000 direct tax credit per child under 18
  prior_year_income_eur: 0        # for donation deduction limit (10% of income)
```

The checklist auto-calculates:
- **Homeoffice-Pauschale** — days × €3, capped at €300 (100 days)
- **Pendlerpauschale** — annual amount based on distance and public transport availability
- **Pendlereuro** — direct tax credit (km × €2)
- **Kirchenbeitrag** — capped at €400
- **Werbungskosten comparison** — tells you if itemizing beats the automatic €132 Pauschale

It also generates a TODO list for items that need receipts (training, books, medical, Familienbonus Plus, etc.) and step-by-step FinanzOnline filing instructions.

---

## WHT reclaim

Set `at_residency_start_year` in `config.local.yaml` to generate a per-country excess WHT report:

```yaml
at_residency_start_year: 2024
```

The report covers dividends from that year onward and shows the reclaimable excess above the treaty rate per country (e.g. DE: 26.375% withheld − 15% treaty = 11.375% excess). Filing deadlines and authority contacts are included.

---

## Freedom dashboard

The HTML dashboard (`_freedom.html`) is interactive — sliders for portfolio value, monthly expenses, contribution, yield, and growth rate. Pre-populated with actual dividend data from the run.

The Excel **Freedom** tab is a static snapshot: key metrics, per-symbol holdings breakdown, and a 10-year projection table.

Configure defaults in `config.local.yaml` under `freedom_dashboard` (see Setup above).

---

## Verlustausgleich — year-over-year overview

Each run saves a small `{person}_{year}_summary.json` snapshot. The Excel **Overview** tab automatically loads all available snapshots for the same person and displays a year-by-year table:

| Year | Dividends | Cap Gains | Cap Losses | Net Taxable | KeSt 27.5% | WHT Credited | KeSt Remaining |

Run for multiple years and the table grows automatically — no manual aggregation needed.

---

## Manual cost basis override

For positions with no IB buy record (spin-offs, shares transferred from another broker):

```yaml
# config.local.yaml
manual_cost_basis:
  - symbol: SOLV
    isin: US83444M1018
    purchase_date: 2024-04-01
    quantity: 10
    cost_eur: 0.00          # total basis in EUR (not per share)
```

Lots are injected into the FIFO queue in date order alongside real buy records.

---

## Running tests

```bash
python -m pytest tests/ -v
```

152 tests covering: both IB parser formats, SAXO xlsx parser (AggregatedAmounts + ShareDividends + ClosedPositions), WHT reclaim calculations (ground truth validated against IBKR German Tax Report), ANV checklist (Pendlerpauschale rates, deduction calculations), plausibility sanity checks, manual cost basis FIFO logic, FIFO cross-check, FX sanity, negative-position detection, and Verlustausgleich year-over-year tracking.

---

## Disclaimer

This tool is provided as-is for personal use. Output should be verified against your broker statements. Tax law changes frequently — KeSt rules, treaty rates, and OeKB reporting requirements may differ from what is implemented here. The authors are not liable for errors in tax filings made using this tool.
