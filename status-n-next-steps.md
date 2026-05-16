# Session Handoff — 2026-05-16

## What was done

- **AT tax efficiency analyzer** (`generators/tax_efficiency.py`) — new generator, wired into pipeline and writer.
  - Section 1: per-NMF-position breakdown — annual KeSt burden, cumulative AE step-up (re-runs `_calc_position` for each year from purchase to now), embedded P&L, KeSt credit estimate if sold in current year.
  - Section 2: dividend payment frequency — monthly / quarterly / semi-annual / annual per symbol, deduplicating same-month rows.
  - Section 3: summary action items with total credit pool and minimum gains needed to absorb it.
  - Auto-generates `{person}_{year}_tax_efficiency.txt` whenever NMF positions exist.
  - 13 new tests → **366 total** (all green).
- **Investment strategy doc** (`docs/investment-strategy-matthias-2026.md`) — hold/sell matrix for O/EPR/WPC/OHI/ARCC, after-all-costs yield comparison, redeployment options (VHYL vs individual stocks), idle cash strategy, notes on existing holdings (Allianz, MunichRe, OMV, Verbund, Rio Tinto, BASF), phase-by-phase action plan.
- **NMF FAQ expanded** (`docs/faq-nichtmeldefonds-reits.md`) — added full after-all-costs yield breakdown table (US REIT 6% gross → 1.7% net; VHYL 3.5% gross → 2.0% net), TER comparison, decision framework by Austrian residency duration.

## Current state

- Tests: **366 passed**, 0 failed
- Key figures: KZ 863 €11,340.73 | KZ 891 €1,107 | KZ 994 €9,292 | KZ 892 €4,735 | NMF KeSt €985 | KeSt remaining **€4,251.72**
- Known issues / open warnings:
  - **NMF AE cost basis step-up NOT YET IMPLEMENTED** — FIFO engine will overstate gain when O/EPR/WPC are sold in 2026. Required before filing.
  - OeKB AE/WA PLACEHOLDER values in `data/oekb_ae.yaml` for some funds — verify before filing Meldefonds rows.

## Next session priorities

1. **NMF AE cost basis step-up** — FIFO engine must use original cost + cumulative AE paid to date when a NMF position is sold. Core mechanic: accumulate AE per symbol per year in pipeline, inject as cost-basis delta into FIFO lots before processing sells. Required for correct O/EPR/WPC exit calculation in 2026.
2. **WHT reclaim paper filings** (user action): France deadline 2026-12-31 (Cerfa n°12816, €12.06); Germany BZSt (€775); Denmark SKAT (€37.91). AT Ansässigkeitsbescheinigung received 2026-05-13 ✓.
3. **Verify OeKB AE/WA PLACEHOLDER values** in `data/oekb_ae.yaml` for any fund before filing Meldefonds KZ 937.

## Blockers

- NMF AE step-up requires design decision: (a) inject AE as cost-basis delta into FIFO lots in pipeline pre-processing, or (b) post-processing adjustment at sell-match time. Option (a) is cleaner. Needs user alignment before implementation.
- Matthias 2024 NMF comparison (`users/matthias/output/2024/matthias_2024_nichtmeldefonds.txt` vs manual Excel) — pending from prior session; not critical since 2024 filing is done.
