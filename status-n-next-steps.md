# Session Handoff — 2026-05-12

## What was done
- **Dynamic portfolio value** (`feat: dynamic portfolio value from FIFO remaining lots × Dec31 prices`):
  - `TaxEngine` now exposes `remaining_positions` (symbol → {qty, has_synthetic}) and `symbol_meta` after all FIFO processing.
  - Synthetic flag: `broker='saxo'` (SAXO AggregatedAmounts, qty=1 convention) and `manual_cost_basis` entries — excluded from market valuation.
  - `pipeline._compute_portfolio_value()`: fetches Dec 31 yfinance price + ECB FX for each non-synthetic remaining position → sums to `summary.portfolio_eur_computed`.
  - Freedom HTML: computed value as slider default; dynamic slider max `max(2M, 3× portfolio)` — no 500k cap; green **auto** / grey **config** source badge.
  - Excel Freedom tab: "Portfolio Value (computed)" / "(config)" label; projection footnote updated.
  - 16 new tests → **213 total**, all green.

## Current state
- Tests: **213 passed** in ~2s.
- Matthias 2025 filing: FILED ✓. KZ 863 €10,138 | KZ 891 €1,107 | KZ 994 €9,292 | KZ 892 €2,628 | KeSt remaining **€3,560**.
- Known issues / open warnings:
  - SOLV cost_eur=0 (spin-off allocation ratio unconfirmed — minor impact).
  - `VER: OEWA` alias in Matthias config — remove before `--year 2026` (all OEWA lots consumed by 2025-12-17 sell).
  - E*Trade holdings not captured (no parser yet — needs sample export).

## Next session priorities
1. **🔴 France WHT reclaim** — deadline **2026-12-31** (233 days). MC + SAF, €12.06 excess. Cerfa n°12816 (Formulaire 5000 + 5001). Paper filing; tool could help generate a pre-filled data sheet.
2. **E*Trade parser** — blocked on sample export from Matthias.
3. **Freedom tab — dynamic dividend yield** — compute trailing yield from actual dividend transactions (natural follow-on to today's portfolio value work; replaces static `yield_pct`).
4. **Freedom tab — per-symbol holdings table** — expand today's `remaining_positions` data into a detailed holdings breakdown in HTML/Excel.

## Blockers
- E*Trade parser: needs sample export file from Matthias.
- France WHT reclaim: paper filing — Matthias must initiate; tool can prepare data but cannot file.
