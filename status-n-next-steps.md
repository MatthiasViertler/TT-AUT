# Session Handoff — 2026-05-16

## What was done

- **IBKR flex CTRN symbol/ISIN extraction** (`brokers/ib_csv.py`)
  - Added `_DESC_SYMBOL_ISIN_RE` regex fallback: extracts symbol + ISIN from description strings
    when the Flex Query CTRN section lacks those columns (format: `"SYMBOL(ISIN) ..."`).
  - Fixes: "unknown country" WHT warnings, ALV 2026 dividend not appearing in Freedom Excel tab.
  - Emits a single `[warn]` per file when columns are absent, with the exact IBKR fix path.
  - 2 new tests added (380 total).

- **KZ 899 credit in KeSt remaining** (`core/tax_engine.py` + `core/pipeline.py`)
  - KZ 899 (AT domestic KeSt withheld at source) now correctly subtracted from `kest_remaining`.
  - Was missing from all 3 recalculation sites (after NMF, after Meldefonds, after interest).
  - 2025 remaining corrected: **€4,251.72 → €3,808.12** (Δ €443.60 = 27.5% × KZ 862 €1,613.10).

- **SOLV cost basis** (`users/matthias/config.local.yaml`, gitignored)
  - Allocated cost_eur=366.56 via FMV-ratio method (BMF §78 EStG Abspaltung).
  - Was 0, causing a phantom €306 gain on the spin-off sell.

- **Pre-2021 IBKR lots** (`users/matthias/config.local.yaml`, gitignored)
  - Added ADS/GAZ/HEN3/IFX/UNVB to `manual_cost_basis` with real quantities and EUR cost.
  - Source: old pre-2021 IBKR account 2020-12-31 portfolio report (account migrated in early 2021).
  - Clears all 5 negative position warnings.

- **Freedom Excel portfolio supplement** (`generators/writer.py`)
  - `_fill_freedom_sheet` now adds `portfolio_eur_supplement` to the IBKR computed value,
    matching the behaviour in `generators/freedom.py` (HTML).
  - Excel Freedom tab now shows full portfolio (~€603k) instead of IBKR-only (~€331k).
  - Matthias supplement updated 250k → 272k in config.

## Current state

- Tests: **380 passed**, 0 failed
- Matthias 2025: KZ 862 €1,613.10 | KZ 863 €11,340.73 | KZ 899 €443.60 | KZ 994 €9,292 | KZ 892 €4,735 | KeSt remaining **€3,808.12**
- Matthias 2026 (as of 2026-05-16): KZ 862 €2,085.60 | KZ 863 €12,882.68 | KZ 994 €17,598.66 | KZ 899 €573.54 | KZ 998 €1,449.48 | KeSt remaining **€6,932.89**
- Known issues / open warnings:
  - OeKB AE/WA PLACEHOLDER values in `data/oekb_ae.yaml` — verify on my.oekb.at before filing Meldefonds KZ 937.
  - IBKR Flex Query CTRN: Matthias's query lacks Symbol/ISIN fields → `[warn]` fires each run. Fix in IBKR settings or leave (fallback is correct).
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
- IBKR interest WHT (Ireland domicile): user filing Ansässigkeitsbescheinigung with IBKR soon — no code change until confirmed.
