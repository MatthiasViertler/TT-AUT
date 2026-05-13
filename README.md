# Kapitalertrag

Austrian capital gains tax calculator. Parses Interactive Brokers exports, applies KeSt rules (FIFO, WHT crediting, Nichtmeldefonds), and produces ready-to-file E1kv Kennziffern plus an Excel dashboard and a financial freedom projection.

> **Personal tool** — built for Austrian tax residents with Interactive Brokers accounts. Contributions welcome, but no guarantees. Always verify output against your broker statements and consult a tax advisor for edge cases.

---

## What it produces

For each run (`--person`, `--year`):

| File | Contents |
|------|----------|
| `users/{person}/output/{person}_{year}_tax_summary.txt` | E1kv Kennziffern ready to copy into FinanzOnline |
| `users/{person}/output/{person}_{year}_transactions.csv` | Full transaction log with FX rates, cost basis, gain/loss |
| `users/{person}/output/{person}_{year}_dashboard.xlsx` | Excel workbook — E1kv Summary, Overview (Verlustausgleich), Transactions, Dividends, Trades, Freedom, [Nichtmeldefonds], [Meldefonds] |
| `users/{person}/output/{person}_{year}_freedom.html` | Interactive financial independence dashboard (sliders) |
| `users/{person}/output/{person}_{year}_wht_reclaim.txt` | Per-country WHT reclaim report (if `at_residency_start_year` set) |
| `users/{person}/output/{person}_{year}_anv_checklist.txt` | L1 deduction checklist — Werbungskosten, Pendlerpauschale, Sonderausgaben, Familienbonus (if `anv:` set) |
| `users/{person}/output/{person}_{year}_summary.json` | Machine-readable year snapshot; populates the multi-year Overview tab |

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

### Security — install the pre-commit hook

A pre-commit hook prevents real broker account IDs from being accidentally committed. Install it once after cloning:

```bash
cp .hooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

The hook reads your real account IDs and IBKR Flex token from `users/*/config.local.yaml` at commit time and blocks any staged file that contains them. It covers every broker and credential automatically — no updates needed when you add a new one (E*Trade, etc.).

**Placeholder IDs to use in all committed files** (docs, tests, config examples):

| Broker | Placeholder |
|--------|-------------|
| Interactive Brokers | `U11111111` / `U22222222` |
| SAXO DK | `19999999` |
| SAXO SG | `8888888` |
| E*Trade and others | any obviously fake ID in the same format |

Real IDs belong only in `users/{yourname}/config.local.yaml`, which is gitignored.

---

**Create a folder for each person** — all personal data lives under `users/` (gitignored):

```
users/
  yourname/
    config.local.yaml    ← person-specific settings (never committed)
    data/
      IB/2025/activity.csv
      SAXO/2025/ClosedPositions_...xlsx
    output/              ← generated files land here
  spouse/
    config.local.yaml
    data/
      IB/2025/activity.csv
    output/
```

**`users/{yourname}/config.local.yaml`** — person-specific settings:

```yaml
# Your broker account ID(s) — used for auto-detection.
# Scalar for a single broker; list for multiple brokers or migrated accounts.
account_id:
  - U99999999        # IB account (find in BOF row of any Flex Query export)
  - "19999999"       # SAXO account (optional, if you use SAXO)

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

`config.yaml` contains only universal settings (KeSt rate, FX source, treaty rates). It is committed and has no personal data.

---

## Getting an IB Flex Query export

### Option A — auto-fetch (recommended)

Create `users/{yourname}/secrets.local.yaml` (edit rarely — only when credentials change):

```yaml
ibkr_flex:
  token: "your_flex_token"   # see below for where to find this
  query_id: 123456           # see below for where to find this
```

Then run:

```bash
python main.py --person matthias --year 2025 --fetch-ibkr
# Re-download even if a cached file already exists:
python main.py --person matthias --year 2025 --force-fetch-ibkr
```

The report is saved automatically to `users/{yourname}/data/IB/{yourname}_ibkr_flex.csv` and picked up in the same run. On future runs without `--fetch-ibkr`, the cached file is still used — re-fetch only when you want updated data.

**Where to find your token and query ID:**

1. **Token** — IB Client Portal → Settings → Flex Web Service → Manage Service Tokens → Create Token. Keep it secret: treat it like a password (the pre-commit hook blocks it from being committed to git).
2. **Query ID** — Reports → Flex Queries → open (or create) your Activity Flex Query → the numeric ID appears in the page URL (e.g. `queryId=123456`).

**Flex Query settings** (when creating or editing your query):
- Type: **Activity Flex Query**
- Format: **CSV**
- Date range: **from your first trade ever** (all years needed for FIFO)
- Sections to include:

| Section | Purpose | Required fields |
|---------|---------|-----------------|
| **Trades** | Capital gains (buys/sells) | all defaults |
| **Cash Transactions** | Dividends + WHT | all defaults |
| **Open Positions** | Portfolio value (Dec 31 snapshot) | Symbol, ISIN, Position, Mark Price, Currency, Asset Class, Level of Detail |

Adding **Open Positions** to your existing query is a one-time edit — no new config key needed. After the next `--fetch-ibkr` run, portfolio value is computed from IBKR's own mark prices instead of Yahoo Finance, which resolves ticker-matching issues for European stocks (RENK, RHM, etc.).

**How to add Open Positions to an existing query:**
1. IB Client Portal → Reports → Flex Queries → click your existing Activity Flex Query
2. Scroll to **Open Positions** → tick the checkbox to enable it
3. In the field selector, ensure these are checked: **Symbol**, **ISIN**, **Position**, **Mark Price**, **Currency** (= CurrencyPrimary), **Asset Class**, **Level of Detail**
4. Save the query — the query ID stays the same, no config change needed
5. Run `--force-fetch-ibkr` once to re-download with the new section included

### Option B — manual export

1. **Reports → Flex Queries → Create**
2. Select **Activity Flex Query**
3. Include sections: **Trades**, **Cash Transactions**, **Open Positions** (same fields as above)
4. Date range: full calendar year(s) you want to calculate
5. Format: **CSV**
6. Run query and save the file to `users/{yourname}/data/IB/{year}/`

For multi-year FIFO accuracy, place **all years** in the data folder — cost basis is recalculated from scratch each run and all files are picked up automatically.

---

## Getting a SAXO export

In SAXO Client Portal → **Reports**:

**ClosedPositions** (preferred for trades — real share quantities):
1. Reports → ClosedPositions → set date range to full calendar year
2. Export as xlsx → save to `users/{yourname}/data/SAXO/{year}/`

**AggregatedAmounts** (for dividends when using ClosedPositions for trades):
1. Reports → AggregatedAmounts → set date range to full calendar year
2. Export as xlsx → save to `users/{yourname}/data/SAXO/{year}/`
3. Set `saxo_skip_agg_trades: true` in your `config.local.yaml` to suppress duplicate trades

**ShareDividends** (richer WHT detail — can combine with AggregatedAmounts):
1. Reports → ShareDividends → set date range
2. Export as xlsx → save to `users/{yourname}/data/SAXO/{year}/`
3. Set `saxo_skip_agg_dividends: true` in your `config.local.yaml` — suppresses duplicate dividend rows from AggregatedAmounts so only ShareDividends provides them

> If you load AggregatedAmounts **without** `saxo_skip_agg_dividends: true`, and also load ShareDividends for the same period, dividends will be double-counted. Use the flag whenever both files cover the same date range.

**Corporate acquisitions** (e.g. SWAV acquired by J&J): appear as "Corporate Actions - Cash Compensation" and are automatically treated as taxable SELL events.

**No per-share quantity in AggregatedAmounts**: each trade is stored as one lot (quantity=1). For positions opened before your earliest ClosedPositions/AggregatedAmounts file, seed the FIFO queue with `manual_cost_basis` entries (see below).

### Data folder structure

```
users/{person}/data/{broker}/{year}/
```

Example:
```
users/matthias/data/SAXO/2024/AggregatedAmounts_19999999_2024-01-01_2024-12-31.xlsx
users/matthias/data/SAXO/2025/ClosedPositions_19999999_2025-01-01_2025-12-31.xlsx
users/matthias/data/SAXO/2025/AggregatedAmounts_19999999_2025-01-01_2025-12-31.xlsx
users/matthias/data/IB/2024/matthias_2024.csv
users/jessie/data/IB/2025/jessie_2025.csv
```

All files under `users/{person}/data/` are picked up automatically when you run with `--person {person}` — no need to list files explicitly.

---

## Usage

```bash
# Recommended — auto-discovers all files in users/{person}/data/
python main.py --person matthias --year 2025
python main.py --person jessie   --year 2025

# Auto-fetch from IBKR (requires ibkr_flex: token + query_id in config.local.yaml)
python main.py --person matthias --year 2025 --fetch-ibkr
python main.py --person matthias --year 2025 --force-fetch-ibkr          # re-download
python main.py --person matthias --year 2025 --fetch-ibkr-positions       # positions only
python main.py --person matthias --year 2025 --force-fetch-ibkr-positions # force re-download

# Explicit input files (non-standard layout or mixing sources)
python main.py --person matthias --input users/matthias/data/IB/2025/file.csv --year 2025

# Auto-detect person from account_id (when input paths are under users/)
python main.py --input users/matthias/data/IB/2025/file.csv --year 2025
```

All options:

```
--person NAME             person label; auto-detected from account_id in users/*/config.local.yaml
--year INT                tax year to calculate
--input FILE [FILE ...]   broker export file(s) or folder(s); optional when --person is given
--users-dir DIR           root for per-user data (default: ./users)
--config FILE             universal config file (default: config.yaml)
--output-dir DIR          output directory override (default: users/{person}/output/)
--fetch-ibkr              download activity statement from IBKR Flex Web Service before processing
--force-fetch-ibkr        re-download even if a cached file already exists (implies --fetch-ibkr)
--fetch-ibkr-positions    download Open Positions report separately (if using a dedicated query)
--force-fetch-ibkr-positions  re-download positions even if cached (implies --fetch-ibkr-positions)
--no-fx-fetch             skip fetching live FX rates (use cached only)
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
- **ISIN rename hint** — if a sell finds no lots but the same ISIN exists under a different buy symbol, the warning suggests the exact `symbol_aliases` entry to add (catches broker mid-year ticker renames)
- **Same-day round-trip detection** — if a sell + same-day repurchase of the same symbol produces a gain/loss < 1% of proceeds (> €500), a warning flags possible FIFO mismatch against the new buy instead of older lots
- **Nichtmeldefonds** (§ 186 InvFG) — pauschal AE = max(90% × annual gain, 10% × Dec31 price) per share; year-end prices auto-fetched from Yahoo Finance and cached
- **Manual cost basis override** — seed the FIFO queue for positions with no IB buy record (spin-offs, broker transfers)
- **Meldefonds (OeKB-registered funds, KZ 936/937)** — AE/WA per share from curated `data/oekb_ae.yaml`; KeSt = 27.5% × AE × shares × FX; WA (Withhaltungsabzug) reduces KeSt due; AT-domiciled ISINs → KZ 936, foreign (IE/LU) → KZ 937. Configured via `meldefonds:` in config.local.yaml.

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

## Meldefonds — OeKB-registered funds (KZ 936/937)

For UCITS ETFs and other funds registered with OeKB (most IE/LU-domiciled ETFs), add to `config.local.yaml`:

```yaml
meldefonds:
  - isin: IE00B3RBWM25   # VWRL — Vanguard FTSE All-World (Distributing)
    symbol: VWRL          # ticker as it appears in your broker export
  - isin: IE00BK5BQT80   # VWCE — Vanguard FTSE All-World (Accumulating)
    symbol: VWCE
```

AE (Ausschüttungsgleiche Erträge) and WA (Withhaltungsabzug) values are read from `data/oekb_ae.yaml` — a curated dataset keyed by ISIN. Share counts are inferred automatically from your transaction history.

**KZ routing:** ISINs with `AT` prefix → KZ 936 (inländisch); all others (IE, LU, …) → KZ 937 (ausländisch).

**Distributing vs. accumulating:** tax treatment is identical — both declare AE annually. For distributing funds, distributions are separately taxed by the broker (KZ 898); AE here = additional undistributed income (may be zero or negative). For accumulating funds, all fund income is AE.

**⚠ Verify AE/WA values** on [my.oekb.at](https://my.oekb.at) before filing. PLACEHOLDER entries in `data/oekb_ae.yaml` produce zero — fill in the actual figures from the fund's "Steuerliche Mitteilung" PDF for each year.

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

**Portfolio value is computed automatically** from the remaining FIFO lots at Dec 31 (quantity × yfinance price × ECB FX). This replaces the static `portfolio_eur` config value as the slider default. Positions from SAXO AggregatedAmounts (qty=1 convention) and `manual_cost_basis` entries are excluded from valuation since their recorded quantities are not real share counts. The slider shows a green **auto** badge when computed, grey **config** when falling back to the config value. The slider max scales dynamically (no 500 k cap).

**Dividend yield is also computed automatically** as trailing yield = actual annual dividends ÷ Dec 31 portfolio value.

**Portfolio Holdings table** — both the HTML and Excel Freedom tab include a per-symbol breakdown: symbol, type (Stock / REIT / BDC / ETF), quantity, Dec 31 EUR value, % of portfolio, annual dividends, and yield. Synthetic positions (SAXO AggregatedAmounts qty=1 lots) are shown with `~qty` and no EUR value. Configurable via `freedom_dashboard.holdings_sort` (`value` | `yield` | `alpha`) and `holdings_group_by_type` (`true` / `false`). The yield slider defaults to this figure (green **auto** badge) when both values are available, otherwise falls back to the static `yield_pct` config value (grey **config** badge). A warning is printed if synthetic positions are excluded from the portfolio, which can inflate the computed yield.

The Excel **Freedom** tab uses the same computed values and labels the source ("computed" vs "config") in the projection subtitle.

Configure fallback defaults in `config.local.yaml` under `freedom_dashboard` (see Setup above).

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

282 tests covering: both IB parser formats, SAXO xlsx parser (AggregatedAmounts + ShareDividends + ClosedPositions), IBKR Flex Web Service auto-fetch (retry logic, error handling, file management), WHT reclaim calculations (ground truth validated against IBKR German Tax Report), ANV checklist (Pendlerpauschale rates, deduction calculations), plausibility sanity checks, manual cost basis FIFO logic, FIFO cross-check, FX sanity, negative-position detection, Verlustausgleich year-over-year tracking, ISIN rename hint, same-day round-trip detection, Meldefonds AE/WA calculation (KZ 936/937, WA credit, share inference), portfolio holdings table (sort, grouping, synthetic positions, sold positions).

---

## Disclaimer

This tool is provided as-is for personal use. Output should be verified against your broker statements. Tax law changes frequently — KeSt rules, treaty rates, and OeKB reporting requirements may differ from what is implemented here. The authors are not liable for errors in tax filings made using this tool.
