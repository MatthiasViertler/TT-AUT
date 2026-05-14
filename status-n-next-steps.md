# Session Handoff — 2026-05-15

## What was done
- **File scanner bug fixed** (`main.py`): `.pdf` added to `_BROKER_EXTENSIONS` (E*Trade PDFs were silently skipped since the tool launched); `.txt` removed (iOS AirDrop artifacts were crashing the pipeline). A test that was encoding the bug as correct behavior was fixed; `test_pdf_included` and `test_txt_excluded` added.
- **Unrecognised file handling** (`brokers/__init__.py`): crash-on-unknown → skip+warn. `(None, None)` sentinel; pipeline prints `[skip] N file(s)` summary. Portfolio PDFs, ReleaseConfirmations, Trade Confirmations all silently skipped.
- **Data coverage report** (`core/pipeline.py`): `_print_coverage()` prints date range per broker after each run, labelled "(by transaction date, not statement date)". Immediately caught 3 missing NXPI quarterly dividends (Apr/Jul/Oct 2025) — added after user fetched the missing statements.
- **IBKR error 1001** (`brokers/ibkr_flex_fetch.py`): actionable message "wait ~10 minutes, then re-run with --force-fetch-ibkr" instead of generic error text.
- **E*Trade CSV parser** added to TASKS.md backlog.
- **CLAUDE.md Next up** section updated with IBKR Cash Report parser as #2 priority.

## Current state
- Tests: **328 passed** ✓ (up from 326; 2 new scanner tests)
- Tagged **v0.2.4**
- Matthias 2025 final figures (all brokers including E*Trade):
  - KZ 862 €1,613 | KZ 863 €10,661 | KZ 994 €9,292 | KZ 891 €1,107 | KZ 892 €2,628
  - KeSt remaining **€3,660.30** ✓ (includes 3 NXPI quarterly dividends previously missing)
- Jessie 2025: KeSt remaining **€44.59** ✓ — clean run, all FX resolved
- Known issues / open warnings:
  - PLACEHOLDER AE/WA values in `data/oekb_ae.yaml` — verify on my.oekb.at before filing (KZ 937 = €4.71)
  - ⚠️ Remove `VER: OEWA` alias from `config.local.yaml` before 2026 tax run
  - IBKR Cash Report section added to flex query but parser side not yet implemented (cash not in portfolio value)
  - `tradesdownload.csv` (×2) skipped — E*Trade CSV parser not yet built

## Next session priorities
1. **🔴 File WHT reclaims** (user plans next week) — France deadline 2026-12-31; Germany €775; Denmark €37.91
2. **IBKR Cash Report parser** — ready to implement; flex query already updated with Currency + EndingCash fields
3. **Verify OeKB AE/WA** on my.oekb.at before filing (manual task, not coding)
4. **SAXO Holdings parser** — blocked on Holdings export sample from Matthias
5. **E*Trade CSV parser** — parse `tradesdownload.csv`; eliminates iPhone-scan PDF dependency

## Blockers
- SAXO Holdings parser: need Holdings export sample
- WHT reclaims: paper filings (France most urgent, deadline 2026-12-31)
- OeKB AE/WA: manual verification on my.oekb.at required before filing
