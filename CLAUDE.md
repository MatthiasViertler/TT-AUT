# Kapitalertrag — Claude Context

## What / Repo
Austrian capital gains tax calculator (Python CLI).
Repo: https://github.com/MatthiasViertler/TT-AUT

## Stack
Python 3.11+, openpyxl, PyYAML, yfinance. Venv: `.venv/`. ECB FX rates cached in `data/fx_cache/`. Year-end prices cached in `data/price_cache/`.

## Structure
```
main.py               CLI (argparse) — --person optional, defaults to "auto"
core/config.py        loads config.yaml + defaults (deep-merge with config.local.yaml)
core/models.py        NormalizedTransaction, TaxSummary, enums
core/fx.py            ECB FX fetcher + disk cache
core/tax_engine.py    KESt rules, FIFO matching, WHT crediting
core/nichtmeldefonds.py  § 186 InvFG pauschal AE calculation
core/price_fetcher.py   Yahoo Finance year-end price fetch + cache (data/price_cache/)
core/pipeline.py      parse → FX → tax → output orchestration
brokers/__init__.py   auto-detects broker format, returns (txns, account_id)
brokers/ib_csv.py     IB Flex Query CSV parser
output/writer.py      write_all() — orchestrates all output files
output/freedom.py     Freedom dashboard HTML generator
config.yaml           account_map, freedom_dashboard defaults, output flags
config.local.yaml     NEVER committed — real account IDs, per-person freedom defaults
docs/                 Word documentation
```

## Key behaviours
- FIFO cost basis — NO state between runs, pass ALL years via `--input`
- `--person` auto-detected from account ID via `account_map` in config.yaml
- WHT warning only fires if excess > €0.05 (suppresses rounding noise)
- Domestic = ISIN starts AT or exchange WBAG/XWBO
- KZ 937 NOT auto-calculated (needs OeKB data)
- `freedom_dashboard` config section controls slider defaults in HTML output;
  override portfolio_eur + per-person assumptions in config.local.yaml
- **OPT rows (AssetClass=OPT) — SKIPPED intentionally.** Filtered out during parsing.
  Derivatives KZ (982/993/893–896) deferred. OPT data present in Matthias's exports
  from 2023 onward (EUREX calls/puts on IFX, ALV, VNA, VER, BAYN).

## IB Flex Query format quirks

**TT-AUT export (BOS/EOS format)** — Matthias's exports (2021–2026):
- BOF col[1] = account ID; BOF col[5] = year-end date (fallback for CTRN rows with no DateTime)
- BOS/EOS markers wrap each section; row after BOS = plain header, rows after = plain data
- CTRN rows have NO Date/Time → grouped by (symbol, per_share_str, currency) and netted
- WHT amounts are negative in source; `wht_held = -sum(whts)` to get positive withheld amount
- Return of Capital detected via description substring "return of capital" → entire group skipped
- PER_SHARE_RE extracts grouping key: `r'([A-Z]{3}\s+\d+(?:\.\d+)?\s+PER\s+SHARE)'`
- BAYN 2021 reversal/re-booking: netting correctly resolves [70, −70, 70.01] → 70.01

**HEADER/DATA format** — Jessie's exports:
- BOF row col[1] = account ID
- Section codes: TRNT=Trades, CTRN=Cash Transactions
- Field names: CurrencyPrimary, DateTime, TradePrice, IBCommission, AssetClass
- Date format: `yyyy-MM-dd;HH:mm:ss`
- Type strings (CTRN): "Dividends", "Withholding Tax", "Broker Interest Received"
- Duplicate rows: same trade with CostBasis ±1.00 → deduped via raw_id

## Security rule — NEVER violate
**Never write real account IDs, API keys, passwords, ISINs tied to a person, or any other PII
into committed files.** Use placeholders (U11111111, U22222222) in CLAUDE.md/config.yaml.
Real values live ONLY in `config.local.yaml` (gitignored). This applies to CLAUDE.md, TASKS.md,
config.yaml, output files, and any other committed file. Treat account IDs like API keys.

## Accounts
Account IDs below are **placeholders only** — real IDs are in `config.local.yaml` (gitignored).
- Jessie's IBKR account → placeholder U11111111 → tested 2024/2025/2026 ✓
- Matthias's IBKR account → placeholder U22222222 → **end-to-end run done ✓ (2026-05-04)**
- Matthias's exports available: 2021, 2022, 2023, 2024, 2025, 2026 (partial) → in `data/matthias_*.csv`
- **2020 intentionally excluded** — IBKR UK/IE split year, nothing tax-relevant. FIFO starts 2021.
- Matthias has REITs/BDCs (Nichtmeldefonds): O, EPR, OHI, WPC, ARCC
- Matthias's symbols (STK): ALV, AIR, BAS, BAYN, BMW, FRE, GAZ, HEN3, HOT, IFX, KHC,
  LIN, LMT, IBKR, MC, MMM, MUV2, NOV, OMV, P911, RIO1, RDSB, SAF, SHL, SIE, UNVB,
  VER, VOW3, AVGO, ABEC, SOLV (Solventum — 3M spin-off, no buy record → cost basis 0)
- **New 2025 additions** (from IBKR German Tax Report): HENSOLDT (DE000HAG0005),
  RENK (DE000RENK730), RHEINMETALL (DE0007030009), TKMS (DE000TKMS001),
  4SC (DE000A3E5C40), DRONESHIELD (AU000000DRO2), BLACKSKY (US09263B2079)
- Special cases handled: P911 Return of Capital (2024: EUR 2.31/sh, 2025: EUR 1.49/sh — both skipped ✓),
  BAYN reversal/re-booking 2021 (netting resolves correctly ✓), VNA 'd' suffix normalization ✓,
  1COV/1CO Covestro tender offer (symbol_aliases) ✓
- **DE symbol normalization**: IB appends 'd' to German-exchange tickers (ALVd → ALV). Stripped by
  `_normalize_de_symbol()` when `isin.startswith("DE") and symbol.endswith("d")`.
- **symbol_aliases** (config.local.yaml): maps tender/merger sell-symbol → normalized buy-symbol.
  Currently: `1CO: 1COV` (Covestro tender 2025). Used by tax engine for FIFO matching.
- GAZ (Russian ADR) — held, likely worthless. No sale event; no tax impact yet.

## Data files (not committed — see .gitignore)
```
data/2024-AUT-TAX-Divi-Trades-Report.csv   — Jessie IBKR Flex Query
data/2025-AUT-TAX-Divi-Trades-Report.csv
data/2026-AUT-TAX-Divi-Trades-Report.csv
data/matthias_2021.csv                      — Matthias IBKR TT-AUT exports
data/matthias_2022.csv
data/matthias_2023.csv
data/matthias_2024.csv
data/matthias_2025.csv
data/matthias_2026.csv
```

## Run
```bash
source .venv/bin/activate  # VS Code terminal: auto-activated
# Jessie:
python main.py --input data/2024-AUT-TAX-Divi-Trades-Report.csv data/2025-AUT-TAX-Divi-Trades-Report.csv --year 2025
# Matthias:
python main.py --input data/matthias_2021.csv data/matthias_2022.csv data/matthias_2023.csv data/matthias_2024.csv data/matthias_2025.csv data/matthias_2026.csv --year 2025
```

## Output files (per run)
- `output/{person}_{year}_tax_summary.txt`   — E1kv Kennziffern for FinanzOnline
- `output/{person}_{year}_transactions.csv`  — full transaction log
- `output/{person}_{year}_dashboard.xlsx`    — Excel workbook (E1kv Summary, Transactions, Dividends, Trades, Freedom, [Nichtmeldefonds])
- `output/{person}_{year}_freedom.html`      — interactive financial independence dashboard
- `output/{person}_{year}_wht_reclaim.txt`   — WHT reclaim report (only if at_residency_start_year set)

## Freedom dashboard (HTML + Excel tab)
HTML: interactive, sliders for portfolio/expenses/contribution/yield/growth.
Excel "Freedom" tab: static snapshot — key metrics, per-symbol holdings breakdown, 10-year
projection table (portfolio × yield_pct, growth_pct, +monthly_contribution/mo).
Both populated from config freedom_dashboard section; override in config.local.yaml.

## Matthias's E1kv (from consultant's Excel — screenshot 2026-05-02)
Much more complex than Jessie's: REITs/BDCs (Nichtmeldefonds), capital losses offsetting gains.
Full E1kv structure needed: sections 1.3.1–1.7, Saldo 1.3, Nichtmeldefonds block.
KZ fields we currently don't output: 864/865 (25% gains), 897 (fund distributions domestic),
982/993/893–896 (derivatives), 171/173/175 (crypto), 942 (Lichtenstein), 984/900/901.

## Nichtmeldefonds (§ 186 InvFG) — fully implemented
- AE = max(90% × annual gain, 10% × Dec31 price) per share × FX Dec31
- KeSt = 27.5% × AE; AE added to cost basis (prevents double-tax on sale)
- Prices auto-fetched from Yahoo Finance via yfinance; cached in data/price_cache/
- Manual dec31_prices override still works if auto-fetch is wrong/unavailable
- Config: just add symbol + type + currency under nichtmeldefonds: in config.yaml

## Correctness checks (all emit warnings, never block output)
- **FIFO cross-check**: `broker_fifo_pnl_eur` captured from HEADER/DATA SELL rows; warns if
  our computed gain differs from IB's FifoPnlRealized by > €1.00 (rounding noise suppressed)
- **Negative position**: warns if total sells > total buys per symbol across all input years;
  respects `symbol_aliases`; known limitation: manual_cost_basis lots not counted
- **FX sanity**: warns (log) if ECB rate deviates >20% from nearest prior cached rate;
  no extra API calls — only compares against already-cached rates

## Testing
- `python -m pytest tests/` — 65 tests, all green
- `pytest>=9.0.0` in requirements.txt
- **Rule**: every new feature ships with at least one test (fixture CSV + assertion)
- Ground truth: 2025 DE €3,808.73 gross / €1,003.18 WHT / €431.87 excess — confirmed against
  IBKR German Tax Report (report ID 126354004/20251231, Line 7)

## Next up (priority order)
1. Usability: `--input-dir` folder scanning
2. Tax: Verlustausgleich tracker (year-by-year gain/loss table)
3. SAXO broker parser (brokers/saxo.py) — needs sample export from Matthias
4. --regelbesteuerung flag

## WHT reclaim status (Matthias, as of 2026-05-04)
- Implemented: `output/wht_reclaim.py` — generates per-country/year reclaim report
- 2024 residency start: only 2024+ dividends included (German resident 2020–2023)
- **Total reclaimable: EUR 852.14** (DE: 775.00, DK: 37.91, FR: 39.24)
- ⚠️  **France 2024 deadline: 2026-12-31** (241 days) — verify WHT rate before filing
- Ansässigkeitsbescheinigung (ZS-AD): filed at Finanzamt 2026-05-03 (confirm receipt)
- 2026 partial data included in report; file in Jan 2027 (deadline 2030, no urgency)
