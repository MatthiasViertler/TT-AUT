# Session Handoff — 2026-05-16

## What was done

- **NMF AE cost basis step-up** (`core/nichtmeldefonds.py`, `core/tax_engine.py`, `core/pipeline.py`)
  - `compute_nmf_cumulative_ae(config, tax_year, all_txns, fx)` — sums `ae_total_eur` per NMF symbol
    for `range(purchase_year, tax_year)` (prior years only; current year excluded — AE assessed on Dec-31 holdings).
  - `_get_nmf_purchase_year()` — resolves earliest year from `manual_cost_basis` or BUY transactions.
  - `TaxEngine.__init__` now accepts `nmf_ae_step_up: dict[str, Decimal]`.
  - In `_process_capital_gains`, before building FIFO queues: for each NMF lot, adds
    `cumulative_ae × (lot_cost / total_symbol_cost) / lot_qty` to `cost_per_unit`.
    Proportional by cost fraction → correct for both SAXO qty=1 (single lot) and real-qty multi-lot cases.
  - Pipeline pre-computes step-up after FX enrichment and passes to TaxEngine.
    Prints `[nmf-adj] Cost-basis step-up: N symbol(s), EUR X.XX cumulative prior-year AE` when active.
  - `tests/test_nmf_step_up.py` — 12 new tests (378 total).

## Current state

- Tests: **378 passed**, 0 failed
- Key figures (Matthias 2025): KZ 863 €11,340.73 | KZ 891 €1,107 | KZ 994 €9,292 | KZ 892 €4,735 | NMF KeSt €985 | KeSt remaining **€4,251.72**
- Known issues / open warnings:
  - OeKB AE/WA PLACEHOLDER values in `data/oekb_ae.yaml` for some funds — verify on my.oekb.at before filing Meldefonds KZ 937.
  - None blocking for Matthias 2026 exit of O/EPR/WPC — step-up fix is in place.

## Next session priorities

1. **WHT reclaim paper filings** (user action, not coding):
   - France deadline **2026-12-31** — Cerfa n°12816 (Formulaire 5000+5001), MC + SAF, €12.06 excess.
   - Germany — BZSt portal or Erstattungsantrag form, €775.00 excess.
   - Denmark — SKAT, €37.91 excess.
   - AT Ansässigkeitsbescheinigung received 2026-05-13 ✓.
2. **SAXO Holdings parser** — blocked on Holdings xlsx export sample from user.
3. **E*Trade CSV parser** (`brokers/etrade_csv.py`) — `tradesdownload.csv` format.
4. **OeKB data license inquiry** — email taxdata@oekb.at.

## Blockers

- SAXO Holdings parser needs a Holdings xlsx export sample from Matthias.
- No coding blockers for the NMF 2026 exit — the step-up is implemented and tested.
