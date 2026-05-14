# Session Handoff — 2026-05-14

## What was done
- **E*Trade PDF parser completed** (`brokers/etrade_pdf.py`): both old (E*TRADE Securities LLC, quarterly) and new (Morgan Stanley, monthly) formats
- **2022 + 2023 E*Trade statements added** to `users/matthias/data/E*Trade/AccountStatements/`; NXPI FIFO chain is now complete 2020–2026 (47 deduplicated transactions)
- **`etrade_skip_transfers` config**: suppresses Sep 1 2023 account-migration "Transfer into Account" (123.977 NXPI) which is not a fresh RSU vest — cost basis traces to original 2020–2022 vesting lots
- **Standalone Recap PDF skip**: `_detect_format()` now returns `"unknown"` for annual "Recap of Cash Management Activity" PDFs (no `For the Period` header → unreliable year context). Monthly statements with an embedded recap section are unaffected.
- **CLAUDE.md**: added "Which reports to download from E*Trade" table; updated migration and recap notes
- **26 E*Trade parser tests** (up from 21); 326 total passing
- Tagged **v0.2.3**

## Current state
- Tests: **326 passed** ✓
- Key figures (Matthias 2025): KZ 863 €10,138 | KZ 891 €1,107 | KZ 994 €9,292 | KeSt remaining **€3,560**
  - Note: E*Trade 2024/2025 sells not yet included in those totals (those are IB+SAXO only)
- Known issues / open warnings:
  - `File 15.02.25, 16 59 26.pdf` (2023 folder) — permanently unrecognised; appears to be a non-E*Trade document. Safe to ignore or archive.
  - PLACEHOLDER AE/WA values in `data/oekb_ae.yaml` — verify on my.oekb.at before filing
  - ⚠️ Remove `VER: OEWA` alias from `config.local.yaml` before 2026 tax run (all OEWA lots consumed 2025-12-17)

## Next session priorities
1. **🔴 File France 2024 WHT reclaim** — deadline 2026-12-31 (231 days). Cerfa n°12816 (Formulaire 5000 + 5001); MC + SAF, €12.06 excess. AT Ansässigkeitsbescheinigung in hand ✓
2. **File Germany WHT reclaim** — €775.00 excess; Bundeszentralamt für Steuern portal
3. **File Denmark WHT reclaim** — €37.91 excess; SKAT
4. **SAXO Holdings parser** — eliminate `portfolio_eur_supplement` manual override; blocked on SAXO Holdings export sample
5. **OeKB data license inquiry** — email taxdata@oekb.at

## Blockers
- SAXO Holdings parser: need Holdings export sample from Matthias
- WHT reclaims: paper filings (not coding tasks); France deadline most urgent
