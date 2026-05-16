# Session Handoff — 2026-05-16

## What was done

- **Freedom yield recomputed against full portfolio** (`generators/writer.py`, `generators/freedom.py`)
  - `dividend_yield_computed` is stored against the IBKR-only portfolio base. When
    `portfolio_eur_supplement` is set (e.g. €272k SAXO estimate), the displayed yield and FIRE
    projection were overstated (example: 4.42% on €331k vs correct 2.43% on €603k).
  - Both the Excel Freedom tab (`_fill_freedom_sheet`) and the HTML dashboard (`write_freedom_html`)
    now recompute yield as `total_dividends_eur / (ibkr_computed + supplement)` when a computed
    portfolio is available. Falls back to `dividend_yield_computed` (no supplement) or config
    `yield_pct` (no computed portfolio) as before.
  - 3 new tests: supplement case, no-supplement case, config fallback.

- **CTRN missing-columns warning** (`brokers/ib_csv.py`)
  - Single `[warn]` per file when Flex Query CTRN lacks Symbol/ISIN columns.
  - Actionable message: IBKR Reports → Flex Queries → Cash Transactions → add Symbol + ISIN.

- **All v0.4.0 fixes** (from previous sub-session):
  - IBKR flex CTRN symbol/ISIN description fallback (fixes "unknown country" + Freedom tab)
  - KZ 899 credit in KeSt remaining (2025: €4,251 → €3,808)
  - SOLV cost basis = €366.56 (was 0)
  - Pre-2021 IBKR lots ADS/GAZ/HEN3/IFX/UNVB added
  - Freedom Excel supplement applied (shows ~€603k not ~€331k)

## Current state

- Tests: **383 passed**, 0 failed
- Matthias 2025: KZ 862 €1,613.10 | KZ 863 €11,340.73 | KZ 899 €443.60 | KZ 994 €9,292 | KZ 892 €4,735 | KeSt remaining **€3,808.12**
- Matthias 2026 (as of 2026-05-16): KZ 862 €2,085.60 | KZ 863 €12,882.68 | KZ 994 €17,598.66 | KZ 899 €573.54 | KZ 998 €1,449.48 | KeSt remaining **€6,932.89**
- Freedom dashboard: portfolio ~€603k, yield ~2.43% (both now correct after this fix)
- Known issues / open warnings:
  - IBKR Flex Query CTRN: Matthias's query lacks Symbol/ISIN → `[warn]` fires each run. Fix in IBKR settings or leave (fallback is correct).
  - OeKB AE/WA PLACEHOLDER values in `data/oekb_ae.yaml` — verify on my.oekb.at before filing Meldefonds KZ 937.
  - NMF O: Dec 31 2026 price unavailable (year in progress) → O AE = 0 for 2026 until year-end.

## Next session priorities

1. **WHT reclaim paper filings** (user action, not coding):
   - France deadline **2026-12-31** — Cerfa n°12816 (Formulaire 5000+5001), MC + SAF, €12.06 excess.
   - Germany — BZSt portal, €775.00 excess.
   - Denmark — SKAT, €37.91 excess.
2. **SAXO Holdings parser** — blocked on Holdings xlsx export sample from user.
3. **E*Trade CSV parser** (`brokers/etrade_csv.py`) — `tradesdownload.csv` format.
4. **OeKB data license inquiry** — email taxdata@oekb.at.

## Blockers

- SAXO Holdings parser needs a Holdings xlsx export sample from Matthias.
- IBKR interest WHT (Ireland domicile): user filing Ansässigkeitsbescheinigung with IBKR — no code change until confirmed.
