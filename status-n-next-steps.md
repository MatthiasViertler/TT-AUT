# Session Handoff — 2026-05-14

## What was done
- **Total-return FIRE model**: freedom dashboard now projects `portfolio × (yield + growth)` as primary income; dividends-only shown as a second dashed line for transparency. Portfolios with significant growth (e.g. 7%) now correctly show FIRE NOW when expenses are covered.
- **IBKR Open Positions parser** (`brokers/ibkr_positions.py`): reads the POST/OpenPositions section from IBKR Flex CSV (BOS/EOS, HEADER/DATA, Classic formats). Uses broker mark prices directly — bypasses yfinance entirely, solving European stock ticker issues (RENK, RHM, TKMS, …). Auto-detected from any input file; no new config or flags needed. 38 positions parsed, €272k IBKR portfolio computed.
- **`portfolio_eur_supplement`** config key: adds a manual SAXO estimate on top of the IBKR auto-computed value; freedom dashboard uses the combined total.
- **`secrets.local.yaml`** architecture: new 4th config layer (gitignored) holds IBKR token/query_id and future broker credentials; never touched during routine config edits. Pre-commit hook extended to scan all string values (len ≥ 6) from this file.
- **18 new tests** for the positions parser (300 total, all green).
- Documentation: README, CLAUDE.md updated for all new features.
- Tagged **v0.2.2**.

## Current state
- Tests: **300 passed**, 0 failed
- Matthias 2025 KeSt figures (unchanged): KZ 863 €10,138 | KZ 891 €1,107 | KZ 994 €9,292 | KZ 892 €2,628 | KeSt remaining **€3,560**
- Portfolio value computed: €272k IBKR (35 positions) + €250k SAXO supplement (manual estimate) = ~€522k
- Known issues / open warnings:
  - SAXO supplement (€250k) is a manual estimate — replace with real value or SAXO Holdings parser
  - oekb_ae.yaml PLACEHOLDER AE/WA values for VWRL/VWCE/VFEM/VFEA/IWDA — verify before filing KZ 937
  - VER→OEWA alias must be removed before running `--year 2026`

## Next session priorities
1. **WHT reclaim form submissions** — Ansässigkeitsbescheinigung signed 2026-05-13, France deadline 2026-12-31 (Cerfa n°12816). Germany €775, DK €37.91, FR €39.24 (excl. France €12.06 net).
2. **E*Trade parser** — blocked on sample export from Matthias; branch `feature/etrade-parser`
3. **SAXO Holdings parser** — eliminate `portfolio_eur_supplement` manual override; blocked on SAXO Holdings export sample
4. **OeKB data license** — email taxdata@oekb.at (one email unlocks automated AE/WA for v2.0)
5. Verify oekb_ae.yaml PLACEHOLDER values on my.oekb.at before next filing

## Blockers
- E*Trade parser: needs sample export from Matthias
- SAXO Holdings parser: needs SAXO Holdings export sample from Matthias
- WHT forms: all documents now in hand, paper filing by user (not a code task)
