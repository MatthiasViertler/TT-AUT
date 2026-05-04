# Kapitalertrag — Claude Context

## What / Repo
Austrian capital gains tax calculator (Python CLI).
Repo: https://github.com/MatthiasViertler/TT-AUT

## Stack
Python 3.11+, openpyxl, PyYAML, yfinance. Venv: `.venv/`. ECB FX cached in `data/fx_cache/`. Year-end prices in `data/price_cache/`.

## Structure
```
main.py               CLI (argparse) — --person optional, defaults to "auto"
core/config.py        loads config.yaml + deep-merge with config.local.yaml
core/models.py        NormalizedTransaction, TaxSummary, enums
core/fx.py            ECB FX fetcher + disk cache
core/tax_engine.py    KESt rules, FIFO matching, WHT crediting, correctness checks
core/nichtmeldefonds.py  § 186 InvFG pauschal AE calculation
core/price_fetcher.py   Yahoo Finance year-end price fetch + cache
core/pipeline.py      parse → FX → tax → output orchestration
brokers/ib_csv.py     IB Flex Query CSV parser (BOS/EOS + HEADER/DATA)
output/writer.py      write_all() — orchestrates all output files
output/freedom.py     Freedom dashboard HTML generator
output/wht_reclaim.py WHT reclaim report generator
config.yaml           account_map, freedom_dashboard defaults, output flags
config.local.yaml     NEVER committed — real account IDs, personal settings
```

## Key behaviours
- FIFO cost basis — NO state between runs, pass ALL years via `--input`
- `--person` auto-detected from account ID via `account_map` in config.yaml
- WHT warning only fires if excess > €0.05 (suppresses rounding noise)
- Domestic = ISIN starts AT or exchange WBAG/XWBO
- KZ 937 NOT auto-calculated (needs OeKB data)
- **OPT rows (AssetClass=OPT) — SKIPPED intentionally.** Derivatives KZ deferred.

## Security rule — NEVER violate
**Never write real account IDs, API keys, passwords, or any PII into committed files.**
Use placeholders (U11111111, U22222222) in CLAUDE.md/config.yaml.
Real values live ONLY in `config.local.yaml` (gitignored).

## Accounts
Account IDs are **placeholders only** — real IDs are in `config.local.yaml`.
- Jessie: placeholder U11111111 → tested 2024/2025/2026 ✓
- Matthias: placeholder U22222222 → end-to-end done ✓ (2026-05-04), exports 2021–2026
- Matthias Nichtmeldefonds: O, EPR, OHI, WPC, ARCC
- **Special cases**: P911 RoC skipped ✓, BAYN reversal netting ✓, ALVd→ALV DE normalization ✓,
  1COV/1CO Covestro tender (symbol_aliases) ✓, SOLV spin-off (manual_cost_basis, cost=0) ✓
- GAZ (Russian ADR) — held, likely worthless, no tax impact yet
- **New 2025**: HENSOLDT, RENK, RHEINMETALL, TKMS, 4SC, DRONESHIELD, BLACKSKY

## Run
```bash
# Jessie:
python main.py --input data/2024-AUT-TAX-Divi-Trades-Report.csv data/2025-AUT-TAX-Divi-Trades-Report.csv --year 2025
# Matthias:
python main.py --input data/matthias_2021.csv data/matthias_2022.csv data/matthias_2023.csv data/matthias_2024.csv data/matthias_2025.csv data/matthias_2026.csv --year 2025
```

## Output files (per run)
- `output/{person}_{year}_tax_summary.txt`   — E1kv Kennziffern for FinanzOnline
- `output/{person}_{year}_transactions.csv`  — full transaction log
- `output/{person}_{year}_dashboard.xlsx`    — E1kv Summary, Transactions, Dividends, Trades, Freedom, [Nichtmeldefonds]
- `output/{person}_{year}_freedom.html`      — interactive financial independence dashboard (sliders)
- `output/{person}_{year}_wht_reclaim.txt`   — WHT reclaim report (if at_residency_start_year set)

## Key config knobs (config.local.yaml)
- `at_residency_start_year: 2024` — enables WHT reclaim report
- `manual_cost_basis: [{symbol, isin, purchase_date, quantity, cost_eur}]` — seeds FIFO for spin-offs
- `symbol_aliases: {NEWTICKER: OLDTICKER}` — tender/merger FIFO matching
- `freedom_dashboard: {portfolio_eur, monthly_expenses_eur, monthly_contribution_eur, yield_pct, growth_pct}`
- `nichtmeldefonds: [{symbol, isin, name, type, currency}]`

## Correctness checks (warnings, never block output)
- **FIFO cross-check**: warns if our gain differs from IB's FifoPnlRealized by > €1.00 (HEADER/DATA only)
- **Negative position**: warns if total sells > total buys per symbol across all input years
- **FX sanity**: warns (log) if ECB rate deviates >20% from prior cached day

## Nichtmeldefonds (§ 186 InvFG)
AE = max(90% × annual gain, 10% × Dec31 price) per share × FX. KeSt = 27.5% × AE.
Prices auto-fetched via yfinance, cached. Add symbol under `nichtmeldefonds:` in config.yaml.

## Manual cost basis
`manual_cost_basis` in config.local.yaml seeds FIFO lots in date order alongside real buys.
Known limitation: not counted in negative-position check (FIFO match still works correctly).

## Testing
- `python -m pytest tests/` — 65 tests, all green
- **Rule**: every new feature ships with at least one test
- Ground truth: 2025 DE €3,808.73 gross / €1,003.18 WHT / €431.87 excess (IBKR report 126354004/20251231)

## Next up (priority order)
1. Usability: `--input-dir` folder scanning
2. Tax: Verlustausgleich tracker (year-by-year gain/loss table)
3. SAXO broker parser — needs sample export from Matthias
4. `--regelbesteuerung` flag

## WHT reclaim status (Matthias)
- Total reclaimable: **EUR 852.14** (DE: 775.00, DK: 37.91, FR: 39.24)
- ⚠️ **France 2024 deadline: 2026-12-31** — Cerfa n°12816, MC + SAF, €12.06 excess
- Ansässigkeitsbescheinigung (ZS-AD): filed at Finanzamt 2026-05-03
