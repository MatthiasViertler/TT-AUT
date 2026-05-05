# Kapitalertrag — Claude Context

## What / Repo
Austrian capital gains tax calculator (Python CLI).
Repo: https://github.com/MatthiasViertler/TT-AUT

## Stack
Python 3.11+, openpyxl, PyYAML, yfinance. Venv: `.venv/`. ECB FX cached in `data/fx_cache/`. Year-end prices in `data/price_cache/`.

## Structure
```
main.py                      CLI (argparse) — --person optional, defaults to "auto"
core/config.py               loads config.yaml + deep-merge with config.local.yaml
core/models.py               NormalizedTransaction, TaxSummary, enums
core/fx.py                   ECB FX fetcher + disk cache
core/tax_engine.py           KESt rules, FIFO matching, WHT crediting, correctness checks
core/nichtmeldefonds.py      § 186 InvFG pauschal AE calculation
core/price_fetcher.py        Yahoo Finance year-end price fetch + cache
core/pipeline.py             parse → FX → tax → output orchestration
brokers/ib_csv.py            IB Flex Query CSV parser (BOS/EOS + HEADER/DATA)
brokers/saxo_xlsx.py         SAXO Bank xlsx parser (AggregatedAmounts + ShareDividends)
brokers/saxo_closedpos_xlsx.py  SAXO ClosedPositions xlsx parser (real quantities)
output/writer.py             write_all() — orchestrates all output files
output/freedom.py            Freedom dashboard HTML generator
output/wht_reclaim.py        WHT reclaim report generator
config.yaml                  account_map, freedom_dashboard defaults, output flags
config.local.yaml            NEVER committed — real account IDs, personal settings
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
- `output/{person}_{year}_dashboard.xlsx`    — E1kv Summary, Overview (Verlustausgleich), Transactions, Dividends, Trades, Freedom, [Nichtmeldefonds]
- `output/{person}_{year}_freedom.html`      — interactive financial independence dashboard (sliders)
- `output/{person}_{year}_wht_reclaim.txt`   — WHT reclaim report (if at_residency_start_year set)
- `output/{person}_{year}_summary.json`      — machine-readable snapshot; drives the multi-year Overview tab

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
Negative-position check accounts for manual lots.

## Testing
- `python -m pytest tests/` — 118 tests, all green
- **Rule**: every new feature ships with at least one test
- Ground truth: 2025 DE €3,808.73 gross / €1,003.18 WHT / €431.87 excess (IBKR report 126354004/20251231)

## SAXO parser notes

### Which reports to export
| Need | Export | Notes |
|------|--------|-------|
| Trades (buys/sells) | **ClosedPositions** (preferred, real quantities) or **AggregatedAmounts** (qty=1 fallback) | |
| Best dividend detail | **ShareDividends** (richer WHT/currency data) or **AggregatedAmounts** as fallback | |
| Do NOT mix | ClosedPositions + AggregatedAmounts trades simultaneously — double-counts sells | set `saxo_skip_agg_trades: true` |

**Recommended workflow (DK account, 2024+):**
1. Export **ClosedPositions** for capital gains (real share quantities, correct FIFO).
2. Export **AggregatedAmounts** for dividends only (set `saxo_skip_agg_trades: true`).
3. Pass both to `--input`; auto-detect routes each to the right parser.

### ClosedPositions parser (`brokers/saxo_closedpos_xlsx.py`)
Emits SELL with real `QuantityClose` and BUY with real `Quantity Open` per lot.
Deduplication: `raw_id = saxo_cp_buy_{OpenPositionId}` — the pipeline's existing raw_id
dedup handles partial closes that span multiple ClosedPositions files (same lot, multiple years).

**SG-transferred lots** (open_date = 2024-03-07): SAXO's `Trade Date Open` is the transfer date,
not the original SG purchase date — wrong FX date for Austrian KeSt. These lots are handled by
`manual_cost_basis` (qty=1 convention). Add the transfer date to the skip list:
```yaml
saxo_closedpos_skip_buy_open_dates:
  - "2024-03-07"   # SG → DK transfer date: all 44 SG-era positions
  - "2024-06-10"   # NVDA 10:1 split lot creation date
```
For skipped lots: SELL emitted with qty=1 (compatible with manual_cost_basis qty=1); no BUY.

**Config keys:**
- `saxo_closedpos_skip_buy_open_dates: [...]` — open dates where manual_cost_basis covers the cost
- `saxo_skip_agg_trades: true` — AggregatedAmounts emits dividends only (suppresses duplicate trades)

**Commissions:** ClosedPositions carries no per-trade commission; set to ZERO in parser.

### Folder structure (recommended)
```
data/{person}/{broker}/{year}/
  data/matthias/SAXO/2024/AggregatedAmounts_18801362_2024-01-01_2024-12-31.xlsx
  data/matthias/SAXO/2025/ClosedPositions_18801362_2025-01-01_2025-12-31.xlsx
  data/matthias/SAXO/2025/AggregatedAmounts_18801362_2025-01-01_2025-12-31.xlsx
  data/matthias/IB/2024/matthias_2024.csv
```

### qty=1 convention — design decision (reviewed 2026-05-05, no change for AggregatedAmounts)
SAXO AggregatedAmounts exports carry no per-share quantity. Each row is one trade (buy or sell) with a total EUR amount. The parser stores every trade as `quantity=1`, making `cost_per_unit = total_cost`. The FIFO engine's `use_qty = min(lot.qty_remaining, sell.qty_to_match)` then consumes exactly one lot per sell — correct given the available data.

**Consequences for `manual_cost_basis`:**
- Use `quantity: 1` (NOT the real share count). Real share count is only used to compute `cost_eur`.
- One sell transaction = one manual lot consumed. For N sells on the same position, create N lots with cost split proportionally and dates ordered so FIFO consumes them in the right sequence.

**Why not redesign?** Alternatives considered: (a) side-file with actual share counts — requires manual per-transaction data entry, no accuracy gain since SAXO still doesn't export it; (b) amount-based FIFO — requires engine refactor, breaks IB compatibility; (c) separate SAXO FIFO engine — complexity without benefit. qty=1 is the correct model for the available data.

### Other parser notes
- **No quantity in AggregatedAmounts** — trades use quantity=1; pre-2024 positions need `manual_cost_basis`
- **ClosedPositions has real quantities** — use for 2024+ DK account capital gains
- **2020 SG account** (8839666): symbols missing in export → parsed as `UIC{n}`; add `symbol_aliases` to remap
- **Account migration 2024**: SG account (8839666) → DK account (18801362); pre-2024 cost basis seeded via `manual_cost_basis` from 2023 Holdings report (Portfolio_8839666_2023-01-01_2023-12-31.pdf)
- **Corporate acquisitions**: "Corporate Actions - Cash Compensation" rows → treated as SELL (e.g. SWAV acquired by JNJ Jun 2024 for €3695.01)
- **Matthias SAXO pre-2024 positions**: all 44 positions seeded in `config.local.yaml` via `manual_cost_basis`; cost basis = avg open price from 2023 Holdings, FX at ECB 2023-12-31 (EUR/USD 1.1050, EUR/HKD 8.5238)

## Next up (priority order)
1. **Arbeitnehmerveranlagung checklist** — Jessie filing due 2026-06-30; E1kv figures ready
2. `--regelbesteuerung` flag — low priority (Matthias progressive rate > 27.5%; N/A Jessie 2025)

## WHT reclaim status (Matthias)
- Total reclaimable: **EUR 852.14** (DE: 775.00, DK: 37.91, FR: 39.24)
- ⚠️ **France 2024 deadline: 2026-12-31** — Cerfa n°12816, MC + SAF, €12.06 excess
- Ansässigkeitsbescheinigung (ZS-AD): filed at Finanzamt 2026-05-03
