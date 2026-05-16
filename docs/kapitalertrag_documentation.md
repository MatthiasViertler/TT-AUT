# Kapitalertrag — Complete Setup & Usage Guide

**Austrian Capital Gains Tax Calculator**
Version: current (see git log for last update)
Tax jurisdiction: Austria (E1kv / FinanzOnline)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Prerequisites & Installation](#2-prerequisites--installation)
3. [Directory Structure](#3-directory-structure)
4. [Per-Person Configuration](#4-per-person-configuration)
5. [Interactive Brokers — Flex Query Setup](#5-interactive-brokers--flex-query-setup)
6. [Interactive Brokers — Auto-Fetch Setup](#6-interactive-brokers--auto-fetch-setup)
7. [SAXO Bank Setup](#7-saxo-bank-setup)
8. [E*Trade Setup](#8-etrade-setup)
9. [Running the Tool](#9-running-the-tool)
10. [Output Files](#10-output-files)
11. [Nichtmeldefonds (§ 186 InvFG)](#11-nichtmeldefonds--186-invfg)
12. [Meldefonds (OeKB-registered funds)](#12-meldefonds-oekb-registered-funds)
13. [WHT Reclaim Report](#13-wht-reclaim-report)
14. [ANV Deduction Checklist](#14-anv-deduction-checklist)
15. [Household Combined View](#15-household-combined-view)
16. [Multi-Year FIFO — The Correct Approach](#16-multi-year-fifo--the-correct-approach)
17. [How the Tax Engine Works](#17-how-the-tax-engine-works)
18. [Troubleshooting](#18-troubleshooting)

---

## 1. Overview

Kapitalertrag converts broker export files into Austrian tax-ready outputs. It handles FX
conversion (ECB rates), FIFO cost basis matching, withholding tax crediting, Nichtmeldefonds
pauschal-AE calculation, Meldefonds OeKB data, and produces pre-filled E1kv Kennziffern ready
for entry into FinanzOnline.

### Supported brokers

| Broker | Format | Status |
|--------|--------|--------|
| Interactive Brokers (IBKR) | Flex Query CSV | ✅ Full support + auto-fetch |
| SAXO Bank | AggregatedAmounts xlsx + ShareDividends xlsx + ClosedPositions xlsx | ✅ Full support |
| E*Trade / Morgan Stanley | PDF statements (old + new format) | ✅ Full support |

### Output Kennziffern (E1kv)

| KZ | Description |
|----|-------------|
| 862 | Inländische Dividendenerträge (AT-domiciled dividends + interest) |
| 863 | Ausländische Dividendenerträge (foreign dividends + interest) |
| 981 | Inländische Kursgewinne (AT securities, 27.5%) |
| 994 | Ausländische Kursgewinne (foreign securities, 27.5%) |
| 891 | Inländische Kursverluste |
| 892 | Ausländische Kursverluste |
| 897/898 | Ausschüttungen aus Investmentfonds (domestic/foreign) |
| 937 | Ausschüttungsgleiche Erträge (auto-calculated for configured Meldefonds + Nichtmeldefonds) |
| 899 | KESt für inländ. WP im Ausland |
| 998 | Anrechenbare ausländische Quellensteuer (creditable WHT, max 15% by treaty) |

---

## 2. Prerequisites & Installation

### Python 3.11+

```bash
python3 --version
```

### One-time setup

```bash
cd kapitalertrag
python3 -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\Scripts\activate         # Windows

pip install -r requirements.txt
```

Dependencies: `openpyxl`, `PyYAML`, `yfinance`, `pdfplumber`

### Pre-commit hook (security — do once per clone)

Prevents real account IDs from being committed:

```bash
cp .hooks/pre-commit .git/hooks/ && chmod +x .git/hooks/pre-commit
```

---

## 3. Directory Structure

```
kapitalertrag/
├── main.py                          CLI entry point
├── config.yaml                      Universal settings (committed; no personal data)
├── core/                            Core logic
│   ├── config.py                    Config loader + account ID scanner
│   ├── models.py                    NormalizedTransaction, TaxSummary, enums
│   ├── fx.py                        ECB FX fetcher + disk cache
│   ├── tax_engine.py                KESt rules, FIFO matching, WHT crediting
│   ├── nichtmeldefonds.py           § 186 InvFG pauschal AE
│   ├── price_fetcher.py             Yahoo Finance year-end prices + cache
│   └── pipeline.py                  Orchestration: parse → FX → tax → output
├── brokers/                         Broker parsers
│   ├── ib_csv.py                    IBKR Flex Query CSV
│   ├── ibkr_flex_fetch.py           IBKR auto-fetch via Flex Web Service
│   ├── ibkr_positions.py            IBKR Open Positions section
│   ├── saxo_xlsx.py                 SAXO AggregatedAmounts + ShareDividends
│   ├── saxo_closedpos_xlsx.py       SAXO ClosedPositions (real quantities)
│   └── etrade_pdf.py                E*Trade PDF (old + Morgan Stanley formats)
├── generators/                      Output generators
│   ├── writer.py                    Excel dashboard + summary.json + CSV + TXT
│   ├── freedom.py                   Interactive FIRE dashboard HTML
│   ├── wht_reclaim.py               WHT reclaim report
│   ├── anv_checklist.py             L1 deduction checklist
│   ├── tax_efficiency.py            NMF embedded P&L analysis
│   └── household.py                 Combined household Excel
├── data/
│   └── oekb_ae.yaml                 OeKB AE/WA data for Meldefonds
├── cache/
│   ├── fx_cache/                    ECB FX rates (gitignored; auto-populated)
│   └── price_cache/                 Dec 31 prices from yfinance (gitignored)
└── users/                           All personal data (gitignored entirely)
    ├── {person}/
    │   ├── config.local.yaml        Person-specific config + account IDs
    │   ├── secrets.local.yaml       IBKR Flex token (edit rarely; never commit)
    │   └── data/
    │       ├── IB/{year}/           IBKR Flex CSV exports
    │       ├── SAXO/{year}/         SAXO xlsx exports
    │       └── ETRADE/{year}/       E*Trade PDF statements
    └── household/
        └── output/{year}/           Household combined Excel output
```

### User output layout

After each run, outputs land in `users/{person}/output/{year}/`:

```
users/matthias/output/2025/
├── matthias_2025_tax_summary.txt     E1kv Kennziffern → copy into FinanzOnline
├── matthias_2025_transactions.csv    Full transaction log
├── matthias_2025_dashboard.xlsx      Multi-tab Excel workbook
├── matthias_2025_freedom.html        Interactive FIRE dashboard
├── matthias_2025_wht_reclaim.txt     WHT reclaim report (if at_residency_start_year set)
├── matthias_2025_anv_checklist.txt   L1 deduction checklist (if anv: set)
├── matthias_2025_tax_efficiency.txt  NMF P&L + KeSt analysis (if NMF positions)
└── matthias_2025_summary.json        Machine-readable snapshot (drives multi-year Overview)
```

---

## 4. Per-Person Configuration

Each person has their own `users/{person}/config.local.yaml`. This file is gitignored — it is
the only place real account IDs and personal details should appear.

### Minimal config

```yaml
account_id:
  - U99999999        # IBKR account (replace with real ID)
  - "19999999"       # SAXO DK account (replace with real ID)
```

### Full config reference

```yaml
# ── Identity ──────────────────────────────────────────────────────────────────
account_id:
  - U99999999        # scalar or list; drives --person auto-detection

# ── WHT reclaim ───────────────────────────────────────────────────────────────
at_residency_start_year: 2024   # enables WHT reclaim report

# ── ANV deduction checklist ───────────────────────────────────────────────────
anv:
  home_office_days: 45
  commute_km: 10
  commute_type: public          # public | car
  kirchenbeitrag_eur: 0
  steuerberatung_eur: 350
  income_eur: 30000             # gross employment income

# ── Freedom / FIRE dashboard ──────────────────────────────────────────────────
freedom_dashboard:
  portfolio_eur: 400000         # fallback if IBKR Open Positions not available
  monthly_expenses_eur: 3500
  monthly_contribution_eur: 1000
  yield_pct: 3.5
  growth_pct: 7.0
  holdings_group_by_type: false

# ── Portfolio supplement (SAXO manual estimate) ───────────────────────────────
portfolio_eur_supplement: 50000

# ── Meldefonds (OeKB-registered accumulating ETFs) ───────────────────────────
meldefonds:
  - isin: IE00B3RBWM25
    symbol: VWRL
  - isin: IE00B4L5Y983
    symbol: IWDA

# ── Nichtmeldefonds (US REITs, BDCs — § 186 InvFG pauschal AE) ───────────────
nichtmeldefonds:
  - symbol: O
    isin: US7561091049
    name: Realty Income Corp
    type: REIT
    currency: USD
    # shares_held_override required for SAXO positions (qty=1 convention):
    shares_held_override:
      2024: 150
      2025: 150

# ── FIFO seeds for spin-offs, migrations, and pre-history positions ───────────
manual_cost_basis:
  - symbol: SOLV
    isin: US83444N1037
    purchase_date: "2023-10-23"
    quantity: 1          # qty=1 for SAXO (see SAXO notes)
    cost_eur: 0          # spin-off: zero cost basis

# ── Corporate action aliases (only needed when ISIN changes) ─────────────────
# Plain broker ticker renames with the same ISIN are auto-resolved; no entry needed.
symbol_aliases:
  1COV: 1CO              # Covestro tender (different ISIN)

# ── SAXO-specific ─────────────────────────────────────────────────────────────
saxo_skip_agg_trades: true          # use ClosedPositions for trades, AA for divs only
saxo_skip_agg_dividends: false      # set true when ShareDividends also loaded for same period
saxo_closedpos_skip_buy_open_dates:
  - "2024-03-07"        # SG → DK transfer date (manual_cost_basis covers these lots)
  - "2024-06-10"        # NVDA 10:1 split lot

# ── E*Trade-specific ──────────────────────────────────────────────────────────
etrade_skip_transfers:
  - "2023-09-01"        # account migration date (old → Morgan Stanley)
```

---

## 5. Interactive Brokers — Flex Query Setup

The Flex Query tells IBKR what data to export. This setup must be done once in the IBKR
Client Portal.

### 5.1 Create the query

1. Log in to [clientportal.ibkr.com](https://clientportal.ibkr.com)
2. Navigate to: **Reports & Tools → Flex Queries → Activity Flex Query**
3. Click **Create New Activity Flex Query**
4. Name it, e.g. `Kapitalertrag-2025`

### 5.2 General settings

| Setting | Value |
|---------|-------|
| Date Period | Custom Date Range — Jan 1 to Dec 31 of the tax year |
| Date Format | `yyyy-MM-dd` |
| Time Format | `HH:mm:ss` |
| Date/Time Separator | Semicolon `;` |
| Include Canceled Trades | NO |
| Include Currency Rates | NO |
| Include Audit Trail | NO |

### 5.3 Format settings — critical

| Setting | Value |
|---------|-------|
| Format | CSV |
| Delimiter | Comma |
| Include Header and Trailer Records | **YES** — required for BOF/EOF detection |
| Include Column Headers | **YES** — field names from these rows |
| Include Section Code | **YES** — TRNT/CTRN prefix routes rows to correct parser |

### 5.4 Trades section — select these fields

In the left panel, check **Trades**, then select exactly:

`Symbol`, `ISIN`, `Description`, `Asset Class`, `Buy/Sell`, `DateTime`, `Quantity`,
`TradePrice`, `Proceeds`, `IBCommission`, `IBCommissionCurrency`, `CurrencyPrimary`,
`Exchange`, `Conid`, `CostBasis`, `FifoPnlRealized`

### 5.5 Cash Transactions section — select these fields

In the left panel, check **Cash Transactions**, then select:

`Symbol`, `ISIN`, `Description`, `AssetClass`, `Date/Time`, `Amount`,
`CurrencyPrimary`, `Type`, `Conid`, `TransactionID`

### 5.6 Open Positions section (portfolio value — recommended)

Enables accurate portfolio valuation using IBKR's own mark prices, instead of fetching from
Yahoo Finance (which fails for European tickers like RENK, RHM, TKMS).

In the left panel, check **Open Positions**, then select:

`Symbol`, `ISIN`, `Position`, `Mark Price`, `Currency`, `Asset Class`, `Level of Detail`

Set **Level of Detail** to `Summary`.

After adding this section, run `--force-fetch-ibkr` once to re-download the updated query.
The pipeline auto-detects and uses the Open Positions data thereafter.

### 5.7 Cash Report section (cash balance — optional)

Adds your total cash balance to the portfolio value in the Freedom dashboard. Optional.

In the left panel, check **Cash Report** (trade date basis), then select at minimum:

`Currency`, `Ending Cash`

Set **Level of Detail** to `Summary`.

After adding, run `--force-fetch-ibkr` once. Auto-detected thereafter from the `CRTT` section.
The `BASE_SUMMARY` row provides IB's own EUR-equivalent cash total — no FX lookup needed.

Privacy note: if you prefer not to expose full cash balances, simply omit this section.

### 5.8 All other sections

Leave unchecked unless you have a specific need. Particularly: do **not** enable Corporate
Actions, Transfers, or Interest Accruals — these can create duplicate entries.

### 5.9 Download and verify

1. Click **Save**, then **Run**
2. Download the CSV and save to `users/{person}/data/IB/{year}/`
3. Open in a text editor and verify it starts with:

```
"BOF","U1234567","Kapitalertrag-2025","2","2025-01-01","2025-12-31",...
"BOA","U1234567"
"BOS","TRNT","Trades; trade date basis"
"HEADER","TRNT","ClientAccountID","CurrencyPrimary",...
"DATA","TRNT","U1234567","EUR",...
"EOS","TRNT","..."
"BOS","CTRN","Cash Transactions"
"HEADER","CTRN","ClientAccountID","CurrencyPrimary","AssetClass","Symbol",...
```

---

## 6. Interactive Brokers — Auto-Fetch Setup

Instead of manually downloading the CSV each time, the tool can fetch it automatically.

### 6.1 Generate a Flex Web Service token

1. Log in to Client Portal
2. Navigate to: **Settings → Flex Web Service → Manage Tokens**
3. Click **Create Token** → copy the token string (show it once only)

### 6.2 Find your query ID

1. Navigate to: **Reports → Flex Queries**
2. Click the query name to open it
3. Look at the URL — the numeric ID at the end is your `query_id`

### 6.3 Write credentials to secrets.local.yaml

```yaml
# users/{person}/secrets.local.yaml
ibkr_flex:
  token: "your_token_here"
  query_id: 123456
  # positions_query_id: 234567   # optional: separate Open Positions query
```

⚠ This file is gitignored. Never copy its contents into any committed file.

### 6.4 Usage

```bash
# Fetch + run in one step (skips download if file already exists)
python main.py --person matthias --year 2025 --fetch-ibkr

# Force re-download even if a file already exists
python main.py --person matthias --year 2025 --force-fetch-ibkr
```

The downloaded file is saved to `users/{person}/data/IB/{person}_ibkr_flex.csv` and picked up
automatically on subsequent runs (via rglob).

### 6.5 --fetch-ibkr vs --force-fetch-ibkr

| Flag | Behaviour |
|------|-----------|
| `--fetch-ibkr` | Download from IBKR **only if no file exists** at the save path. If a previously downloaded file is present, it is reused silently. Safe to include in any run without risking rate-limit hits. |
| `--force-fetch-ibkr` | **Always re-download**, overwriting any existing file. Use this when you need fresh data (e.g. you ran the tool earlier today and new transactions have since settled), or after changing the Flex Query layout in IBKR. Implies `--fetch-ibkr`. |

The same logic applies to the Open Positions variants:

| Flag | Behaviour |
|------|-----------|
| `--fetch-ibkr-positions` | Download Open Positions only if no cached file exists. |
| `--force-fetch-ibkr-positions` | Always re-download Open Positions. Use after editing the Flex Query or when portfolio values look stale. |

**Error 1001**: IBKR enforces a ~10-minute cooldown between consecutive fetches. If you hit it,
wait 10 minutes and re-run with `--force-fetch-ibkr`. Using plain `--fetch-ibkr` will not
trigger a new fetch (the existing file is reused), so it is safe to run immediately.

---

## 7. SAXO Bank Setup

### 7.1 Which reports to export

| Need | Export type | Notes |
|------|------------|-------|
| Capital gains (buys/sells) | **ClosedPositions** xlsx | Real quantities per lot — preferred for DK account 2024+ |
| Dividends | **AggregatedAmounts** xlsx | Richer WHT/currency data available in ShareDividends |
| Dividends (with WHT detail) | **ShareDividends** xlsx | Better than AA for individual dividend breakdown |

**Recommended workflow (DK account, 2024+):**
1. Export **ClosedPositions** for capital gains
2. Export **AggregatedAmounts** with `saxo_skip_agg_trades: true` for dividends only  
   — OR — export **ShareDividends** and set `saxo_skip_agg_dividends: true` in AggregatedAmounts

### 7.2 Where to export in the SAXO interface

Log in → **Account → Reports → Account Statement**

- **ClosedPositions**: Account Statement → Format: Excel → Report type: Closed Positions
- **AggregatedAmounts**: Account Statement → Format: Excel → Report type: Aggregated Amounts
- **ShareDividends**: Account Statement → Format: Excel → Report type: Share Dividends

Save files to `users/{person}/data/SAXO/{year}/`.

### 7.3 Quantity convention (AggregatedAmounts)

SAXO's AggregatedAmounts report carries no per-share quantity. Each row is one trade with a
total EUR amount. The parser stores `quantity=1` for each trade, making `cost_per_unit = total`.
FIFO consumes exactly one lot per sell — correct given the available data.

**Consequence**: `manual_cost_basis` entries must also use `quantity: 1`, not the real share count.

### 7.4 SG → DK account migration (2024)

Lots opened in the Singapore account (pre-2024) were transferred to the DK account with a
transfer date as the `Trade Date Open`. To avoid using the wrong FX date for these lots:

1. Seed them via `manual_cost_basis` with the correct original cost
2. Add the transfer date to `saxo_closedpos_skip_buy_open_dates`:

```yaml
saxo_closedpos_skip_buy_open_dates:
  - "2024-03-07"   # SG → DK transfer date
```

---

## 8. E*Trade Setup

### 8.1 Two format generations

| Period | Format | Account label |
|--------|--------|--------------|
| 2020–2021 | Old E*TRADE Securities (quarterly PDFs) | XXXX0725 |
| 2022–Aug 2023 | Old E*TRADE Securities (monthly PDFs) | XXXX0725 |
| Sep 2023+ | E*Trade from Morgan Stanley (monthly PDFs) | XXXX201 |

### 8.2 Which files to download

Log in → **Documents → Account Statements**

Download **monthly** statements (not annual recaps). Annual recaps reprint prior-year transfers
with the same IDs — the pipeline's deduplication handles this, but the files are otherwise
informational only.

The September 2023 Morgan Stanley migration creates a "Transfer into Account" entry for all
positions. Suppress this with:

```yaml
etrade_skip_transfers:
  - "2023-09-01"   # migration date
```

Save PDFs to `users/{person}/data/ETRADE/{year}/`.

### 8.3 RSU treatment

Only net-issued shares appear in the export ("Transfer into Account" / "Receive"). The shares
withheld for tax are off-statement. Cost basis = Fair Market Value at vesting date (from statement
or yfinance). KeSt = 27.5% × (sale price − FMV).

---

## 9. Running the Tool

### 9.1 Recommended (auto-discover all files)

```bash
source .venv/bin/activate

# Run for a single person + year — scans users/{person}/data/ automatically
python main.py --person matthias --year 2025
python main.py --person jessie   --year 2025

# With IBKR auto-fetch (requires secrets.local.yaml)
python main.py --person matthias --year 2025 --fetch-ibkr

# Force re-download of IBKR data
python main.py --person matthias --year 2025 --force-fetch-ibkr
```

### 9.2 Explicit input files (advanced)

```bash
python main.py --person matthias \
  --input users/matthias/data/IB/2025/export.csv \
           users/matthias/data/SAXO/2025/ClosedPositions.xlsx \
  --year 2025
```

### 9.3 All CLI arguments

| Argument | Description |
|----------|-------------|
| `--person LABEL` | Person label. Auto-detected from `account_id` in `config.local.yaml` if omitted. |
| `--year YYYY` | Tax year to calculate. Required. |
| `--input FILE [...]` | Explicit broker export files. Optional: if omitted, scans `users/{person}/data/` recursively. |
| `--fetch-ibkr` | Download IBKR Flex report if no cached file exists. Requires `secrets.local.yaml`. |
| `--force-fetch-ibkr` | Always re-download IBKR Flex report, overwriting any cached file. Implies `--fetch-ibkr`. |
| `--fetch-ibkr-positions` | Download Open Positions report if no cached file exists. |
| `--force-fetch-ibkr-positions` | Always re-download Open Positions report. Implies `--fetch-ibkr-positions`. |
| `--no-fx-fetch` | Skip live ECB FX fetch. Use only cached rates. |

### 9.4 Multi-year FIFO

The tool has no state between runs. For accurate cost basis when sells span multiple years,
the auto-scan mode handles this automatically by picking up all years' files from
`users/{person}/data/`. If using explicit `--input`, pass all years' files:

```bash
python main.py --person matthias \
  --input users/matthias/data/IB/2023/export.csv \
           users/matthias/data/IB/2024/export.csv \
           users/matthias/data/IB/2025/export.csv \
  --year 2025
```

The `--year` flag controls which year is taxed. All files are parsed for FIFO continuity.
Duplicate transactions across overlapping files are automatically deduplicated.

---

## 10. Output Files

All output files land in `users/{person}/output/{year}/`.

| File | Description |
|------|-------------|
| `{person}_{year}_tax_summary.txt` | E1kv Kennziffern — copy values into FinanzOnline |
| `{person}_{year}_transactions.csv` | Full normalized transaction log with all fields |
| `{person}_{year}_dashboard.xlsx` | Multi-tab Excel workbook (see below) |
| `{person}_{year}_freedom.html` | Interactive FIRE dashboard with sliders |
| `{person}_{year}_wht_reclaim.txt` | WHT reclaim report per country (if `at_residency_start_year` set) |
| `{person}_{year}_anv_checklist.txt` | L1 deduction checklist (if `anv:` section configured) |
| `{person}_{year}_tax_efficiency.txt` | NMF embedded P&L + KeSt credit analysis (if NMF positions) |
| `{person}_{year}_summary.json` | Machine-readable snapshot; drives multi-year Overview tab |

### Excel dashboard tabs

| Tab | Contents |
|-----|----------|
| E1kv Summary | All Kennziffern with colour coding; cross-sheet formulas to Dividends/Trades |
| Overview | Multi-year table + charts: dividends/year, KeSt remaining, income sources, transactions, FIRE %, monthly breakdowns |
| Transactions | All transactions for the year |
| Dividends | Dividend transactions only, with domestic/foreign subtotals |
| Trades | Buy/sell transactions with gain/loss per trade |
| Freedom | Portfolio holdings table + 10-year FIRE projection |
| Nichtmeldefonds | Per-symbol NMF breakdown (if NMF positions configured) |
| Meldefonds | Per-fund AE/WA/KeSt breakdown (if Meldefonds configured) |

---

## 11. Nichtmeldefonds (§ 186 InvFG)

US REITs (O, EPR, OHI, WPC, VNQ, ...) and BDCs (ARCC, MAIN, ...) are classified as investment
funds under Austrian law but are not registered with OeKB. Austrian residents must apply the
pauschal AE calculation **in addition to** normal dividend taxation.

**AE formula**: `AE = max(90% × annual gain/share, 10% × Dec 31 price/share) × shares × FX`
**KeSt**: `27.5% × AE`

### Setup

Add symbols to `nichtmeldefonds:` in your `config.local.yaml`:

```yaml
nichtmeldefonds:
  - symbol: O
    isin: US7561091049
    name: Realty Income Corp
    type: REIT
    currency: USD
    shares_held_override:   # required for SAXO positions (qty=1 convention)
      2024: 150
      2025: 150
```

Dec 31 prices are fetched automatically from Yahoo Finance and cached in `cache/price_cache/`.

### AE cost basis step-up

Each prior year's AE is added to the steuerliche Anschaffungskosten (FIFO lot cost_per_unit)
before sell matching. This prevents double-taxation: if you paid KeSt on AE for 3 years, those
amounts are deducted from your taxable gain when you finally sell.

---

## 12. Meldefonds (OeKB-registered funds)

OeKB-registered accumulating ETFs (VWRL, VWCE, IWDA, ...) report AE/WA data annually. This
data is available at [my.oekb.at](https://my.oekb.at) and must be entered manually into
`data/oekb_ae.yaml`.

### Setup

1. Add ISINs to `meldefonds:` in your `config.local.yaml`:

```yaml
meldefonds:
  - isin: IE00B3RBWM25
    symbol: VWRL
```

2. Look up the AE/WA values on my.oekb.at for each fund and year
3. Enter them in `data/oekb_ae.yaml`:

```yaml
IE00B3RBWM25:  # VWRL
  "2024":
    ae_per_share: 0.8234
    wa_per_share: 0.0000
    meldedatum: "2025-02-14"
    ertragsverwendung: "A"  # A=ausschüttend, T=thesaurierend
    kz: "937"
```

PLACEHOLDER entries in `oekb_ae.yaml` produce KeSt = 0. Always verify and fill real values
before filing.

---

## 13. WHT Reclaim Report

When a foreign country withholds more tax than the Austria DBA treaty allows, the excess can be
reclaimed directly from that country's tax authority.

**Enable by setting** `at_residency_start_year` in your `config.local.yaml`:

```yaml
at_residency_start_year: 2024
```

The report (`*_wht_reclaim.txt`) lists each country with excess WHT, the total reclaimable amount,
the relevant filing authority, and the deadline.

### Country-specific filing

| Country | Authority | Form | Deadline |
|---------|-----------|------|----------|
| Germany | Bundeszentralamt für Steuern (BZSt) | BZSt portal online | 31 Dec + 4 years |
| France | Direction Générale des Finances Publiques | Cerfa n°12816 (Formulaire 5000+5001) | 31 Dec + 2 years |
| Denmark | SKAT | SKAT online portal | 31 Dec + 3 years |
| Netherlands | Belastingdienst | IB 96 NL | 31 Dec + 3 years |

An **Ansässigkeitsbescheinigung** (ZS-AD, confirming AT tax residency) from your Austrian
Finanzamt is required for most reclaim filings. Request it from your local Finanzamt.

---

## 14. ANV Deduction Checklist

The ANV checklist (`*_anv_checklist.txt`) lists claimable L1 deductions for the
Arbeitnehmerveranlagung based on your config.

**Enable by adding** `anv:` to your `config.local.yaml`:

```yaml
anv:
  home_office_days: 45
  commute_km: 10
  commute_type: public          # public | car
  kirchenbeitrag_eur: 0
  steuerberatung_eur: 350
  income_eur: 30000
```

---

## 15. Household Combined View

Generates a side-by-side comparison Excel for two people in the same household.

```bash
python main.py --household matthias,jessie --year 2025
```

**Prerequisites**: Each person's `summary.json` for the target year must exist (run the
individual pipelines first). The tool warns if any person's summary is >7 days old.

**Output**: `users/household/output/{year}/household_{year}_{persons}.xlsx`

The workbook shows side-by-side columns (person A | person B | Combined) for:
KZ 863, interest, gains/losses, net taxable, KeSt, WHT, KeSt Remaining, portfolio, yield.

---

## 16. Multi-Year FIFO — The Correct Approach

The tool has **no state between runs**. The FIFO queue is built fresh each run from all input
files. If you sell securities purchased in a prior year, that year's data must be included.

**With auto-scan (recommended)**: the tool picks up all years' files from `users/{person}/data/`
recursively. As long as all broker exports are stored there, multi-year FIFO works automatically.

**With explicit `--input`**: pass all years' files. The `--year` flag controls which year's gains
are taxed; all other years provide cost basis only.

Files can overlap in date range — duplicate transactions are automatically deduplicated by
`raw_id` (a deterministic hash of the transaction content).

---

## 17. How the Tax Engine Works

### FX conversion

All amounts are converted to EUR using the ECB reference rate on the trade date. Rates are
downloaded once per currency per year (full-year block) and cached in `cache/fx_cache/`. The
current year's cache is refreshed if >1 day old (ECB publishes daily). If no rate exists for a
specific date (weekend/holiday), the tool looks back up to 5 calendar days.

### FIFO cost basis (§ 27 EStG)

Sells are matched against the oldest open buy lots first. Cost basis = purchase price +
commission, both at the purchase-date FX rate. Gain = EUR proceeds − EUR cost basis − EUR sell
commission.

**Cross-check**: if a FIFO-sourced gross gain/loss deviates from IBKR's own `FifoPnlRealized`
field by >€1.00, a warning is printed.

**ISIN auto-alias**: if a sell has no matching lots under its symbol but another symbol shares
the same ISIN with sufficient quantity, the engine silently aliases them. Handles plain ticker
renames (VER→OEWA, NOV→NOVd, etc.). For corporate actions where ISIN changes (mergers, tenders),
use `symbol_aliases:` in config.

### WHT crediting (§ 27a EStG)

```
creditable_WHT = min(actual_WHT_paid, treaty_rate × gross_dividend)
KeSt_remaining = KeSt_due (27.5%) − creditable_WHT
```

Excess WHT (actual > treaty rate) is not creditable in Austria; it must be reclaimed from the
source country (see Section 13).

### What is NOT automatically calculated

- **Manual KZ 937 entries**: Meldefonds not in `data/oekb_ae.yaml` produce zero. Verify each
  AE/WA figure on my.oekb.at before filing.
- **Corporate actions**: splits, mergers, spin-offs affecting cost basis require manual config
  entries (`manual_cost_basis`, `symbol_aliases`).
- **Prior-year loss carryforward**: the tool calculates current-year net only.

---

## 18. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| No transactions loaded | Flex Query missing Trades/CashTransactions sections | Re-export with both sections; verify CSV starts with BOF + HEADER/DATA rows |
| `FX: No rate found for X around YYYY-MM-DD` (>5 days) | Stale current-year FX cache | Delete `cache/fx_cache/{CCY}_{YEAR}.json`; tool re-fetches automatically on next run |
| 28 transactions FX=0 | Current-year FX cache created before those dates | Same as above — delete the stale file |
| Overview tab shows only current year | Prior years' `summary.json` missing | Run the tool for each prior year; `summary.json` is created automatically |
| IBKR Error 1001 (`--fetch-ibkr`) | IBKR cooldown between consecutive fetches (~10 min) | Wait 10 minutes and retry |
| IBKR Error 1019 | IBKR still generating the report | Already retried automatically; try again in a few minutes |
| `Unmatched sell` warning | Purchase year not in input data | Run with all years' files, or place them all in `users/{person}/data/` |
| `Negative position` warning | More sells than buys for a symbol | Usually a missing prior-year file; can also indicate a split not in data |
| OPT rows skipped warning | Options/derivatives rows in IBKR data | Expected: KZ 982/993 not yet implemented; printed as `[warn]` |
| `openpyxl not installed` | Dependency missing | `pip install -r requirements.txt` |
| NameError / ImportError | Virtual environment not activated | `source .venv/bin/activate` |
| SAXO ClosedPositions qty=1 | Using AggregatedAmounts instead | Preferred: use ClosedPositions for 2024+ DK account capital gains |
| E*Trade recap PDF not parsed | Standalone annual recap has no year context | Expected: only monthly/quarterly statements are parsed; recaps are skipped |

---

*This file supersedes `docs/kapitalertrag_documentation.docx` (archived, last updated 2026-05-01 at v1.0).*
*For investment strategy and WHT reclaim research, see `docs/investment-strategy-matthias-2026.md`.*
