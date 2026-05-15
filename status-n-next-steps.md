# Session Handoff — 2026-05-15

## What was done
- **IBKR Cash Report parser** (`parse_ibkr_cash_report` in `brokers/ib_csv.py`) — parses the CRTT section (BOS/EOS, HEADER/DATA, Classic formats). Uses the `BASE_SUMMARY` row (IB pre-converts to EUR; no ECB FX lookup needed). Adds cash to `portfolio_eur_computed` and shows as "IBKR Cash" in the Freedom holdings table. Re-normalises `portfolio_pct` across all positions after adding cash.
- **`TaxSummary.ibkr_cash_eur`** — new optional field; stores cash component separately from securities value.
- **`summary.json` enriched** — now serialises `portfolio_eur_computed`, `ibkr_cash_eur`, `dividend_yield_computed`, and full `portfolio_positions` list (all were missing before).
- **CLAUDE.md + README.md updated** — Cash Report setup documented as optional IBKR Flex Query section. Privacy note explicit: omit CRTT if you prefer not to expose cash balances.
- **7 new tests → 335 total**. Tagged v0.2.5.

Confirmed at session start: IBKR error 1001 is usage-related (consecutive fetch cooldown ~10 min), not a query structure issue.

## Current state
- Tests: **335 passed**, 0 failed
- Tagged **v0.2.5**
- Matthias 2025 portfolio (with cash): EUR 387,124.89 (36 equity positions + EUR 82,830.65 cash)
- Matthias 2025 tax figures unchanged: KZ 863 €10,138 | KZ 891 €1,107 | KZ 994 €9,292 | KZ 892 €2,628 | KeSt remaining **€3,560**
- Known issues / open warnings:
  - PLACEHOLDER AE/WA values in `data/oekb_ae.yaml` — verify on my.oekb.at before filing (KZ 937 = €4.71)
  - ⚠️ Remove `VER: OEWA` alias from `config.local.yaml` before 2026 tax run
  - `tradesdownload.csv` (×2) skipped — E*Trade CSV parser not yet built

## Next session priorities
1. **🔴 WHT reclaim paper filings** — France deadline 2026-12-31 (Cerfa n°12816, €12.06 excess); Germany BZSt (€775.00); Denmark SKAT (€37.91). AT Ansässigkeitsbescheinigung in hand ✓
2. **SAXO Holdings parser** — auto-compute SAXO portfolio value; eliminate manual `portfolio_eur_supplement`. Blocked on Holdings export sample from user.
3. **E*Trade CSV parser** (`brokers/etrade_csv.py`) — `tradesdownload.csv` format; eliminates PDF scan dependency for Morgan Stanley statements.
4. **OeKB data license inquiry** — email taxdata@oekb.at for structured AE/WA feed.

## Blockers
- SAXO Holdings parser: need a Holdings export sample from SAXO Client Portal.
- WHT paper filings: action on user side (forms + mailing).
