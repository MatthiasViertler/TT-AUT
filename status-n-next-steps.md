# Session Handoff — 2026-05-15

## What was done
- **IBKR cash interest parser**: reads CTRN section from existing Flex CSV automatically; no new flex query section or manual config needed. Deduplicates across multiple input files using `(currency, description)` key (same monthly payment appears in full-year and per-month exports). Adds to KZ 863 / net_taxable / kest_due.
- **Freedom dashboard — net income**: replaced pre-tax dividend display with post-tax `net_monthly_income = (dividends + interest) × 0.725 − excess_WHT`. New "Income After Tax" breakdown panel shows dividends, cash interest, gross total, and a reclaimable WHT note.
- **Output directory restructure**: `users/{person}/output/{year}/` (was flat `users/{person}/output/`). Updated main.py, CLAUDE.md, README.md.
- **NOV/NOVd ticker alias** (user config, gitignored): Novo Nordisk held as `NOV.d` on German exchange → IB normalises to `NOVd`; 2025 sell/rebuy parsed as `NOV`. Added `NOV: NOVd` to `symbol_aliases` in `users/matthias/config.local.yaml`. Round-trip warning gone; KeSt remaining dropped €579.
- **7 new tests** for `parse_ibkr_interest` (BOS/EOS EUR+USD, year filtering, no-interest, no-CTRN, HEADER/DATA, missing file, full-year sum) → 342 total.
- Jessie 2025 tax questions answered: ANX/EMWE warnings safe to ignore (2024 data, nothing held 2025); dental costs below Selbstbehalt; ANV/L1 worth filing (~€485 Werbungskosten → ~€106 refund).

## Current state
- **Tests**: 342 passed, 0 failed
- **Matthias 2025 key figures** (after NOV alias + interest):
  - KZ 863 (foreign dividends + interest): EUR 11,340.73
  - KZ 994 (foreign gains): EUR 9,291.87
  - KZ 891 (domestic losses): EUR 1,107.12
  - KZ 892 (foreign losses): EUR 4,735.24
  - KeSt due: EUR 4,512.21
  - WHT creditable: EUR 1,244.58
  - **KeSt remaining: EUR 3,267.63**
  - Cash interest: EUR 679.29 (24 unique payments)
- **Known issues / open warnings**:
  - Negative positions: ADS, GAZ (Russian ADR), HEN3, IFX, UNVB, SOLV — pre-2024 SAXO lots missing from IB history. Cosmetic only (no effect on tax).
  - SOLV spin-off negative position — expected (manual_cost_basis cost=0).
  - 33 total warnings in last run (mostly WHT excess per stock, covered by WHT reclaim).

## Next session priorities
1. **WHT reclaim paper filings** (user action, not coding):
   - France: Cerfa n°12816 (Formulaire 5000 + 5001), deadline 2026-12-31, €12.06 excess
   - Germany: BZSt portal, €775.00 excess
   - Denmark: SKAT, €37.91 excess
2. **Jessie 2025 filing**: E1kv data ready; consider submitting ANV/L1 (~€106 refund)
3. **SAXO Holdings parser** — eliminate `portfolio_eur_supplement`; blocked on Holdings export sample from user
4. **E*Trade CSV parser** (`brokers/etrade_csv.py`) — `tradesdownload.csv` format
5. **OeKB data license** — email taxdata@oekb.at

## Blockers
- SAXO Holdings parser: waiting for user to export a sample Holdings xlsx from SAXO portal
- WHT filings: user has the Ansässigkeitsbescheinigung (ZS-AD) signed 2026-05-13 — ready to file
