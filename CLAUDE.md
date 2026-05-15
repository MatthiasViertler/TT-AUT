# Kapitalertrag — Claude Context

## What / Repo
Austrian capital gains tax calculator (Python CLI).
Repo: https://github.com/MatthiasViertler/TT-AUT

## Stack
Python 3.11+, openpyxl, PyYAML, yfinance, pdfplumber. Venv: `.venv/`. ECB FX cached in `cache/fx_cache/`. Year-end prices in `cache/price_cache/`.

## Structure
```
main.py                      CLI (argparse) — --person, --year; --input optional
core/config.py               load_config() + scan_account_ids() + DEFAULTS
core/models.py               NormalizedTransaction, TaxSummary, enums
core/fx.py                   ECB FX fetcher + disk cache
core/tax_engine.py           KESt rules, FIFO matching, WHT crediting, correctness checks
core/nichtmeldefonds.py      § 186 InvFG pauschal AE calculation
core/price_fetcher.py        Yahoo Finance year-end price fetch + cache
core/pipeline.py             parse → FX → tax → output orchestration
brokers/ib_csv.py            IB Flex Query CSV parser (BOS/EOS + HEADER/DATA)
brokers/ibkr_flex_fetch.py   IBKR Flex Web Service auto-fetch (--fetch-ibkr / --force-fetch-ibkr)
brokers/ibkr_positions.py    IBKR Open Positions parser (auto-detected from activity statement or separate file)
brokers/saxo_xlsx.py         SAXO Bank xlsx parser (AggregatedAmounts + ShareDividends)
brokers/saxo_closedpos_xlsx.py  SAXO ClosedPositions xlsx parser (real quantities)
brokers/etrade_pdf.py        E*TRADE PDF parser (old E*TRADE Securities + new Morgan Stanley formats)
generators/writer.py             write_all() — orchestrates all output files
generators/freedom.py            Freedom dashboard HTML generator
generators/wht_reclaim.py        WHT reclaim report generator
generators/anv_checklist.py      Arbeitnehmerveranlagung deduction checklist (L1 form)
config.yaml                  universal settings — committed; NO personal data
users/{person}/              gitignored entirely — all sensitive data lives here
  config.local.yaml          person-specific overrides (account_id, anv, freedom_dashboard, …)
  data/{broker}/{year}/      broker exports
  output/                    generated output files
cache/fx_cache/              shared ECB FX rate cache (gitignored)
cache/price_cache/           shared year-end price cache (gitignored)
```

## User directory layout (canonical)
```
users/matthias/
  config.local.yaml
  data/IB/2025/matthias_2025.csv
  data/IB/matthias_ibkr_flex.csv        ← auto-fetched (--fetch-ibkr); picked up by rglob
  data/SAXO/2025/ClosedPositions_19999999_2025-01-01_2025-12-31.xlsx
  output/2025/matthias_2025_tax_summary.txt  ← generated
users/jessie/
  config.local.yaml
  data/IB/2025/jessie_2025.csv
  output/2025/jessie_2025_tax_summary.txt    ← generated
```

## Key behaviours
- FIFO cost basis — NO state between runs, pass ALL years via `--input` (or place all in data/)
- `--person` auto-detected: scan `users/*/config.local.yaml` for matching `account_id`
- `--input` optional: when omitted, scans `users/{person}/data/` recursively
- Output lands in `users/{person}/output/{year}/` by default
- WHT warning only fires if excess > €0.05 (suppresses rounding noise)
- Domestic = ISIN starts AT or exchange WBAG/XWBO
- **KZ 937 (Meldefonds AE)**: auto-calculated for ISINs configured in `meldefonds:` with verified values in `data/oekb_ae.yaml`. PLACEHOLDER entries produce zero — verify each AE/WA figure on my.oekb.at before filing.
- **OPT rows (AssetClass=OPT) — SKIPPED intentionally.** Derivatives KZ deferred.
- **Dynamic portfolio value**: IBKR Open Positions mark prices used when available (POST section in flex CSV, auto-detected). Falls back to FIFO lots × yfinance. SAXO AggregatedAmounts (`broker='saxo'`) and `manual_cost_basis` lots (`synthetic=True`) excluded. `portfolio_eur_supplement` adds SAXO manual estimate. IBKR Cash Report (CRTT section, optional) adds cash balance. Stored in `summary.portfolio_eur_computed`; `summary.ibkr_cash_eur` holds cash component separately.
- **Freedom FIRE model**: total return = `portfolio × (yield + growth)` — not dividends-only. Chart shows both total-return and dividends-only lines.
- **Cash interest**: parsed from CTRN section of IBKR Flex CSV automatically (no config needed). Deduplicated across multiple input files by `(currency, description)`. Adds to KZ 863 / net_taxable. Freedom dashboard shows net income = `gross × 0.725 − excess_WHT`.

## Security rule — NEVER violate
**Never write real account IDs, API keys, passwords, or any PII into committed files.**
Real values live ONLY in `users/{person}/config.local.yaml` (gitignored via `users/`).

Placeholders to use in all committed files:
- IB: `U11111111` (Jessie), `U22222222` (Matthias)
- SAXO DK: `19999999` | SAXO SG: `8888888`
- E*Trade and future brokers: pick an obviously fake ID in the same format

A pre-commit hook enforces this automatically. After a fresh clone, install it once:
```bash
cp .hooks/pre-commit .git/hooks/ && chmod +x .git/hooks/pre-commit
```

## accounts in users/{person}/config.local.yaml
```yaml
account_id:           # scalar or list — supports multi-broker and migrated accounts
  - U99999999         # IB account (placeholder)
  - "19999999"        # SAXO DK account (placeholder)
```

Account IDs are **placeholders only** in this file — real IDs are in `users/{person}/config.local.yaml`.
- Jessie: account configured, `anv:` set (45 HO days, 10km commute public, €350 tax advisor, €30k income) ✓ (2026-05-05)
- Matthias: IB + SAXO DK + E*Trade accounts configured, nichtmeldefonds added (O,EPR,OHI,WPC,ARCC) ✓ (2026-05-05)
  2025 run: KZ 863 €11,340.73 | KZ 891 €1,107 | KZ 994 €9,292 | KZ 892 €4,735 | NMF KeSt €985 | KeSt remaining **€4,251.72** (IB+SAXO+E*Trade+interest+NMF)
  E*Trade 2022-2023 statements obtained ✓; NXPI FIFO chain complete 2020–2026. Sep 2023 account migration handled via `etrade_skip_transfers`.
- Matthias Nichtmeldefonds: O, EPR, OHI, WPC, ARCC
- **Special cases**: P911 RoC skipped ✓, BAYN reversal netting ✓, ALVd→ALV DE normalization ✓,
  1COV/1CO Covestro tender (symbol_aliases — different ISIN, must stay explicit) ✓, SOLV spin-off (manual_cost_basis, cost=0) ✓,
  VER→OEWA Verbund AG ticker rename (same ISIN → ISIN auto-alias, no config needed) ✓
  NOV→NOVd Novo Nordisk German listing (same ISIN → ISIN auto-alias, no config needed) ✓
- GAZ (Russian ADR) — held, likely worthless, no tax impact yet
- **New 2025**: HENSOLDT, RENK, RHEINMETALL, TKMS, 4SC, DRONESHIELD, BLACKSKY

## Run
```bash
# Recommended — auto-discovers all files in users/{person}/data/
python main.py --person matthias --year 2025
python main.py --person jessie   --year 2025

# Explicit files (power user / non-standard layout)
python main.py --person matthias --input users/matthias/data/IB/2025/file.csv --year 2025

# Auto-detect person from account_id (when --person not given, path must be under users/)
python main.py --input users/matthias/data/IB/2025/file.csv --year 2025
```

## Output files (per run)
All land in `users/{person}/output/{year}/`:
- `{person}_{year}_tax_summary.txt`   — E1kv Kennziffern for FinanzOnline
- `{person}_{year}_transactions.csv`  — full transaction log
- `{person}_{year}_dashboard.xlsx`    — E1kv Summary, Overview, Transactions, Dividends, Trades, Freedom, [Nichtmeldefonds], [Meldefonds]
- `{person}_{year}_freedom.html`      — interactive financial independence dashboard (sliders)
- `{person}_{year}_wht_reclaim.txt`   — WHT reclaim report (if at_residency_start_year set)
- `{person}_{year}_anv_checklist.txt` — L1 deduction checklist (if anv: section in config)
- `{person}_{year}_summary.json`      — machine-readable snapshot; drives the multi-year Overview tab
- `{person}_{year}_nichtmeldefonds.txt` — per-symbol NMF breakdown (shares, prices, AE, KeSt); generated on demand via script, not pipeline

## Key config knobs (users/{person}/config.local.yaml)
- `account_id: [...]` — account ID(s); scalar or list; drives auto-detection
- `at_residency_start_year: 2024` — enables WHT reclaim report
- `anv: {home_office_days, commute_km, commute_type, kirchenbeitrag_eur, ...}` — enables ANV checklist
- `manual_cost_basis: [{symbol, isin, purchase_date, quantity, cost_eur}]` — seeds FIFO for spin-offs
- `symbol_aliases: {NEWTICKER: OLDTICKER}` — **only needed for corporate actions where IB assigns a new ISIN** (tender offers, mergers). Plain broker ticker renames (same ISIN, new symbol) are resolved automatically by ISIN auto-alias — no entry needed.
- `freedom_dashboard: {portfolio_eur, monthly_expenses_eur, monthly_contribution_eur, yield_pct, growth_pct}`
- `meldefonds: [{isin, symbol}]` — OeKB-registered funds; AE/WA looked up from `data/oekb_ae.yaml`
- `nichtmeldefonds: [{symbol, isin, name, type, currency, shares_held_override: {year: count}}]`
  — `shares_held_override` required for SAXO positions (qty=1 convention makes transaction count unreliable)
- `portfolio_eur_supplement: N` — added on top of IBKR auto-computed value (e.g. manual SAXO estimate)
- `saxo_closedpos_skip_buy_open_dates: [...]` — skip BUY lots on these open dates (manual_cost_basis covers them)
- `saxo_skip_agg_trades: true` — AggregatedAmounts emits dividends only (use with ClosedPositions)
- `saxo_skip_agg_dividends: true` — AggregatedAmounts emits trades only (use when ShareDividends also loaded for same period — prevents double-counting)

## Correctness checks (warnings, never block output)
- **FIFO cross-check**: warns if our gain differs from IB's FifoPnlRealized by > €1.00 (HEADER/DATA only)
- **Negative position**: warns if total sells > total buys per symbol across all input years
- **FX sanity**: warns (log) if ECB rate deviates >20% from prior cached day
- **FIFO all-years**: all years' sells are processed through FIFO queue in date order (prior-year sells drain lots correctly); only current-year gains/losses added to summary
- **ISIN auto-alias** (`core/tax_engine.py`): when a sell has no lots prior to the sell date under its own symbol, the engine searches for a unique other symbol sharing the same ISIN with sufficient open qty → aliases silently (log only). Covers plain broker ticker renames (e.g. VER→OEWA, NOV→NOVd) including same-day rebuy patterns. Ambiguous (multiple candidates) or qty-insufficient cases still warn and fall through to the rename hint below.
- **ISIN rename hint**: unmatched sell where ISIN matches lots under a different symbol but auto-alias couldn't resolve (ambiguous or qty mismatch) → suggests exact `symbol_aliases` entry
- **Same-day round-trip**: sell + same-day repurchase of same symbol with |gain| < 1% of proceeds (>€500) → warns FIFO may have matched against new buy instead of older lots

## Nichtmeldefonds (§ 186 InvFG)
AE = max(90% × annual gain, 10% × Dec31 price) per share × FX. KeSt = 27.5% × AE.
Prices auto-fetched via yfinance, cached in `cache/price_cache/`. Add symbol under `nichtmeldefonds:` in person config.
- **shares_held_override required for SAXO positions**: SAXO qty=1 convention means transaction history returns 1 share instead of real count. Set `shares_held_override: {2024: N, 2025: N}` per symbol.
- **AE cost basis step-up (gap)**: each year's AE must be added to steuerliche Anschaffungskosten at FIFO sell time. NOT YET IMPLEMENTED — sells will overstate gain. Fix required before Matthias 2026 filing (plans to exit O/EPR/WPC/ARCC).
- **Double taxation note**: dividends taxed as KZ 863 AND AE charged separately. 10% minimum fires even when price flat/down.

## Manual cost basis
`manual_cost_basis` in person config seeds FIFO lots in date order alongside real buys.
Negative-position check accounts for manual lots.

## Testing
- `python -m pytest tests/` — 353 tests, all green
- **Rule**: every new feature ships with at least one test
- Ground truth: 2025 DE €3,808.73 gross / €1,003.18 WHT / €431.87 excess (IBKR report 126354004/20251231)

## SAXO parser notes

### Which reports to export
| Need | Export | Notes |
|------|--------|-------|
| Trades (buys/sells) | **ClosedPositions** (preferred, real quantities) or **AggregatedAmounts** (qty=1 fallback) | |
| Best dividend detail | **ShareDividends** (richer WHT/currency data) or **AggregatedAmounts** as fallback | |
| Do NOT mix | ClosedPositions + AggregatedAmounts trades simultaneously — double-counts sells | set `saxo_skip_agg_trades: true` |
| Do NOT mix | AggregatedAmounts + ShareDividends for same period — double-counts dividends | set `saxo_skip_agg_dividends: true` |

**Recommended workflow (DK account, 2024+):**
1. Export **ClosedPositions** for capital gains (real share quantities, correct FIFO).
2. Export **AggregatedAmounts** for dividends only (set `saxo_skip_agg_trades: true`).
3. Pass both to `--input` (or place in `users/{person}/data/SAXO/{year}/`); auto-detect routes each to the right parser.

**If using AggregatedAmounts (trades) + ShareDividends (dividends):**
- Set `saxo_skip_agg_dividends: true` — suppresses dividend rows from AA so only ShareDividends provides them.
- Example: Matthias 2024/2025 — no ClosedPositions available, uses AA for trades + SD for WHT detail.

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

**Commissions:** ClosedPositions carries no per-trade commission; set to ZERO in parser.

### qty=1 convention — design decision (reviewed 2026-05-05, no change for AggregatedAmounts)
SAXO AggregatedAmounts exports carry no per-share quantity. Each row is one trade (buy or sell) with a total EUR amount. The parser stores every trade as `quantity=1`, making `cost_per_unit = total_cost`. The FIFO engine's `use_qty = min(lot.qty_remaining, sell.qty_to_match)` then consumes exactly one lot per sell — correct given the available data.

**Consequences for `manual_cost_basis`:**
- Use `quantity: 1` (NOT the real share count). Real share count is only used to compute `cost_eur`.
- One sell transaction = one manual lot consumed. For N sells on the same position, create N lots with cost split proportionally and dates ordered so FIFO consumes them in the right sequence.

**Why not redesign?** Alternatives considered: (a) side-file with actual share counts — requires manual per-transaction data entry, no accuracy gain since SAXO still doesn't export it; (b) amount-based FIFO — requires engine refactor, breaks IB compatibility; (c) separate SAXO FIFO engine — complexity without benefit. qty=1 is the correct model for the available data.

### Other parser notes
- **No quantity in AggregatedAmounts** — trades use quantity=1; pre-2024 positions need `manual_cost_basis`
- **ClosedPositions has real quantities** — use for 2024+ DK account capital gains
- **2020 SG account** (8888888): symbols missing in export → parsed as `UIC{n}`; add `symbol_aliases` to remap.
  `AggregatedAmounts_8888888_2020-01-01_2020-06-19.xlsx` moved to `users/matthias/archive/SAXO/2020/` — do not put in `data/`; pre-2024 cost basis is fully covered by `manual_cost_basis`.
- **Account migration 2024**: SG account (8888888) → DK account (19999999); pre-2024 cost basis seeded via `manual_cost_basis` from 2023 Holdings report (Portfolio_8888888_2023-01-01_2023-12-31.pdf)
- **Corporate acquisitions**: "Corporate Actions - Cash Compensation" rows → treated as SELL (e.g. SWAV acquired by JNJ Jun 2024 for €3695.01)
- **Matthias SAXO pre-2024 positions**: all 44 positions seeded in `users/matthias/config.local.yaml` via `manual_cost_basis`; cost basis = avg open price from 2023 Holdings, FX at ECB 2023-12-31 (EUR/USD 1.1050, EUR/HKD 8.5238)

## E*Trade parser notes

### Two format generations
- **Old (2020-2021)**: E*TRADE Securities LLC, quarterly statements. Sections: "TRANSACTION HISTORY" (sells/buys), "OTHERACTIVITY" (RSU Receive rows, no price), "DIVIDENDS & INTEREST ACTIVITY". RSU cost basis fetched from yfinance (closing price on vesting date).
- **New (2024+)**: E*TRADE from Morgan Stanley, monthly. Sections: "CASH FLOW ACTIVITY BY DATE" (sells/buys + dividends), "SECURITY TRANSFERS" (RSU vestings with FMV amount). RSU cost basis = FMV amount ÷ qty from statement.

### RSU treatment (NXPI / NXP Semiconductors)
- Sell-to-cover shares are withheld by NXP payroll off-statement — **not visible** in E*Trade exports.
- Only net-issued shares appear as "Transfer into Account" (new) or "Receive" (old).
- Cost basis = FMV at vesting date (from statement or yfinance). KeSt = 27.5% × (sale price − FMV).
- NXPI: ISIN NL0009538784, NL domicile, 15% WHT.

### Which reports to download from E*Trade
Log in → **Documents → Account Statements**. Download **monthly** statements (not quarterly, not annual recaps).

| Period | Account | Where to get |
|--------|---------|--------------|
| 2020–2021 (quarterly) | old E*TRADE Securities (XXXX0725) | Documents → Account Statements → 2020, 2021 |
| 2022–Aug 2023 (monthly) | old E*TRADE Securities (XXXX0725) | same; covers up to Aug 2023 closing statement |
| Sep 2023+ (monthly) | E*Trade from Morgan Stanley (XXXX201) | Documents → Account Statements → 2023, 2024, 2025 |

**Do NOT download** standalone "Recap of Cash Management Activity" PDFs — these are informational only, have no year context, and are correctly skipped by the parser. Download only the regular monthly/quarterly statements.

### Practical notes
- Account IDs are extracted from PDF text dynamically (never hardcoded). E*Trade accounts in `users/{person}/config.local.yaml` under `account_id:`.
- Old format: "E*TRADE Securities" is CID-encoded on page 1; `detect()` checks first + last 2 pages.
- Old format sell regex: AMOUNT PURCHASED column is empty for sells; only one amount appears in text.
- Annual December recap re-lists all prior-year Security Transfers — same `raw_id`s, pipeline dedup handles it.
- Standalone annual "Recap of Cash Management Activity" PDFs (no "For the Period" header) → `_detect_format` returns `"unknown"` and skips them. These have no reliable year context; monthly statements cover the same data.
- **`etrade_skip_transfers`** config key (list of YYYY-MM-DD): suppresses "Transfer into Account" entries on those dates. Use for account migrations (e.g. Sep 1 2023 old→Morgan Stanley migration of 123.977 NXPI). Genuine vestings on other dates are unaffected.

## IBKR Flex Web Service auto-fetch
- **CLI**: `python main.py --person matthias --year 2025 --fetch-ibkr`
- **Force re-download**: `--force-fetch-ibkr`
- **Credentials** in `users/{person}/secrets.local.yaml` (gitignored, edit rarely):
  ```yaml
  ibkr_flex:
    token: "your_token"      # IB Client Portal → Settings → Flex Web Service → Manage Tokens
    query_id: 123456         # Reports → Flex Queries → (open query) → numeric ID in URL
    # positions_query_id: 234567  # optional: separate Open Positions query
  ```
- Saves to `users/{person}/data/IB/{person}_ibkr_flex.csv`; picked up by rglob automatically.
- Pre-commit hook scans `secrets.local.yaml` and blocks all its values from leaking into committed files.

### Open Positions (portfolio value)
- **Recommended**: add "Open Positions" section to the existing Activity Flex Query — no new config needed.
  - IBKR: Reports → Flex Queries → edit existing query → tick **Open Positions**
  - Required fields: **Symbol**, **ISIN**, **Position**, **Mark Price**, **Currency**, **Asset Class**, **Level of Detail**
  - Run `--force-fetch-ibkr` once to re-download with the new section; auto-detected thereafter.
- **Alternative**: separate query → set `ibkr_flex.positions_query_id` + `--fetch-ibkr-positions` flag.
- Pipeline priority: explicit positions file → Open Positions section in any input file → FIFO × yfinance fallback.
- Solves European stock ticker issues (RENK, RHM, TKMS, etc.) where yfinance returns no price.

### Cash Transactions (interest, automatic)
- **Already included** in the standard Activity Flex Query (CTRN section) — no new config needed.
- The pipeline parses "Broker Interest Received" rows automatically; deduplicates across files.
- Adds interest to KZ 863 / net_taxable / kest_due. Shown in Freedom "Income After Tax" breakdown.

### Cash Report (portfolio value, optional)
- **Optional**: add "Cash Report" section to the existing Activity Flex Query.
  - IBKR: Reports → Flex Queries → edit existing query → tick **Cash Report** (trade date basis)
  - Required fields: **Currency**, **Ending Cash** (EndingCash column — the others are optional)
  - Run `--force-fetch-ibkr` once; auto-detected thereafter from the `CRTT` section.
- Uses the `BASE_SUMMARY` row: IB's own EUR-equivalent of all cash balances (no ECB FX lookup needed).
- Adds cash to `portfolio_eur_computed`; shows as "IBKR Cash" position in Freedom dashboard.
- **Fully optional**: if CRTT section is absent, tax output is unchanged — only affects FIRE dashboard.
- ⚠️ **Privacy note**: users who prefer not to expose full portfolio value can omit Cash Report entirely.
- Error 1001 on `--fetch-ibkr`: cooldown between consecutive fetches (~10 min). Not a query structure issue.

## Next up (priority order)
1. **🔴 AT tax efficiency analyzer** — per-position NMF flag + embedded loss estimate + alternatives.
   Data already available; no new APIs. Most urgent coding task next session.
2. **🔴 NMF AE cost basis step-up on sale** — FIFO must use original cost + cumulative AE at sell time.
   Required before Matthias 2026 filing (plans to exit O/EPR/WPC/ARCC for tax-loss harvesting).
3. **WHT reclaim forms** — paper filings (user action). France deadline 2026-12-31.
4. **Jessie 2025 filing** — E1kv data entered; considered done.
5. **SAXO Holdings parser** — blocked on Holdings export sample.
6. **E*Trade CSV parser** — `tradesdownload.csv` format.
7. **OeKB data license inquiry** — email taxdata@oekb.at.

## Done this session (v0.3.2)
- **NMF share count fix** ✅ — `shares_held_override` per year; 2025 KeSt remaining €3,268 → **€4,252**.
- **FAQ docs** ✅ — 3 new files in `docs/`: steuereinfach brokers, Meldefonds, Nichtmeldefonds REITs.
- **TASKS.md** ✅ — 12+ new tasks: Portfolio Intelligence section, bonds, savings interest, Trade Republic, physical metals, crypto, FinanzOnline guide, etc.

## Done this session (v0.3.1)
- **ISIN auto-alias** ✅ — same-ISIN ticker renames resolved without any config; `symbol_aliases` now only for corporate actions (different ISIN). VER→OEWA and NOV→NOVd entries removed.

## WHT reclaim status (Matthias)
- Total reclaimable: **EUR 852.14** (DE: 775.00, DK: 37.91, FR: 39.24)
- ⚠️ **France 2024 deadline: 2026-12-31** — Cerfa n°12816, MC + SAF, €12.06 excess
- Ansässigkeitsbescheinigung (ZS-AD): signed confirmation from AT Finanzamt received 2026-05-13 ✓
