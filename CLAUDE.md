# Kapitalertrag — Claude Context

## What / Repo
Austrian capital gains tax calculator (Python CLI).
Repo: https://github.com/MatthiasViertler/TT-AUT

## Stack
Python 3.11+, openpyxl, PyYAML. Venv: `.venv/`. ECB FX rates cached in `data/fx_cache/`.

## Structure
```
main.py               CLI (argparse) — --person optional, defaults to "auto"
core/config.py        loads config.yaml + defaults
core/models.py        NormalizedTransaction, TaxSummary, enums
core/fx.py            ECB FX fetcher + disk cache
core/tax_engine.py    KESt rules, FIFO matching, WHT crediting
core/pipeline.py      parse → FX → tax → output orchestration
brokers/__init__.py   auto-detects broker format, returns (txns, account_id)
brokers/ib_csv.py     IB Flex Query CSV parser
output/writer.py      CSV / TXT / Excel output
config.yaml           account_map: {account_id: person_name}
docs/                 Word documentation
```

## Key behaviours
- FIFO cost basis — NO state between runs, pass ALL years via `--input`
- `--person` auto-detected from account ID via `account_map` in config.yaml
- WHT warning only fires if excess > €0.05 (suppresses rounding noise)
- Domestic = ISIN starts AT or exchange WBAG/XWBO
- KZ 937 NOT auto-calculated (needs OeKB data)

## IB Flex Query format quirks
- BOF row col[1] = account ID
- Section codes: TRNT=Trades, CTRN=Cash Transactions
- Field names: CurrencyPrimary, DateTime, TradePrice, IBCommission, AssetClass
- Date format: `yyyy-MM-dd;HH:mm:ss`
- Type strings (CTRN): "Dividends", "Withholding Tax", "Broker Interest Received"
- Duplicate rows: same trade with CostBasis ±1.00 → deduped via raw_id

## Accounts
- U11111111 → jessie (IBKR) — tested 2024/2025/2026 ✓
- Matthias's IBKR account ID → still needs adding to config.yaml

## Run
```bash
source .venv/bin/activate  # VS Code terminal: auto-activated
python main.py --input data/2024.csv data/2025.csv --year 2025
```

## Output files (per run)
- `output/{person}_{year}_tax_summary.txt`   — E1kv Kennziffern for FinanzOnline
- `output/{person}_{year}_transactions.csv`  — full transaction log
- `output/{person}_{year}_dashboard.xlsx`    — 4-tab Excel workbook
- `output/{person}_{year}_freedom.html`      — dividend freedom dashboard (TODO)

## Freedom dashboard (HTML)
Built as interactive widget this session. Pre-populated with real dividend data.
Sliders: monthly expenses, monthly contribution, portfolio yield, annual growth.
Shows: passive income salary, freedom %, milestones, projection chart, holdings breakdown.
TODO: wire into Python pipeline as generated output file + add Excel tab.

## Next up (priority order)
1. Wire freedom dashboard HTML into pipeline output
2. Add Excel "Freedom" tab (static snapshot of projection)
3. Manual cost basis override (config.yaml) for transferred positions
4. Cross-check vs IB FifoPnlRealized field
5. Automated test suite
