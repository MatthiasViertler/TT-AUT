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

## IB Flex Query format quirks
- BOF row col[1] = account ID
- Section codes: TRNT=Trades, CTRN=Cash Transactions
- Field names: CurrencyPrimary, DateTime, TradePrice, IBCommission, AssetClass
- Date format: `yyyy-MM-dd;HH:mm:ss`
- Type strings (CTRN): "Dividends", "Withholding Tax", "Broker Interest Received"
- Duplicate rows: same trade with CostBasis ±1.00 → deduped via raw_id

## Accounts
- Jessie's IBKR account → tested 2024/2025/2026 ✓
- Matthias's IBKR account ID → in config.local.yaml (U7251654), not yet tested end-to-end
- Matthias also has REITs/BDCs (Nichtmeldefonds): O, EPR, OHI, WPC, ARCC

## Data files (not committed — see .gitignore)
```
data/2024-AUT-TAX-Divi-Trades-Report.csv   — Jessie IBKR Flex Query
data/2025-AUT-TAX-Divi-Trades-Report.csv
data/2026-AUT-TAX-Divi-Trades-Report.csv
```

## Run
```bash
source .venv/bin/activate  # VS Code terminal: auto-activated
python main.py --input data/2024-AUT-TAX-Divi-Trades-Report.csv data/2025-AUT-TAX-Divi-Trades-Report.csv --year 2025
```

## Output files (per run)
- `output/{person}_{year}_tax_summary.txt`   — E1kv Kennziffern for FinanzOnline
- `output/{person}_{year}_transactions.csv`  — full transaction log
- `output/{person}_{year}_dashboard.xlsx`    — 4-tab Excel workbook
- `output/{person}_{year}_freedom.html`      — interactive financial independence dashboard

## Freedom dashboard (HTML)
Wired into pipeline. Pre-populated with real dividend data from the run.
Sliders: current portfolio value, monthly expenses, contribution, yield, growth rate.
Defaults from config.local.yaml freedom_dashboard section (Jessie: €40k portfolio, €1.2k/mo).
Shows: freedom %, FIRE timeline card, milestones, 40yr projection chart, holdings table.

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

## Next up (priority order)
1. WHT reclaim assistant — per-country/year summary + BZSt line items (🔴 URGENT: 2022 DE deadline Dec 31, 2026)
2. Add Matthias's IBKR data files + run end-to-end (needs actual Flex Query exports)
3. SAXO broker parser (brokers/saxo.py) — needs sample export from Matthias
4. Pytest test suite skeleton (tests/ with fixture CSVs)
5. Excel "Freedom" tab (static snapshot)
6. Manual cost basis override (config.yaml) for transferred positions
7. --regelbesteuerung flag
