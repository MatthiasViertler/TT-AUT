# Session Handoff — 2026-05-15

## What was done
- **ISIN auto-alias** (`core/tax_engine.py`): when a sell has no FIFO lots prior to the sell
  date under its own symbol, the engine finds a unique other symbol sharing the same ISIN with
  sufficient open qty and older lots → aliases silently (INFO log, no warning).
  - Trigger covers two cases: (a) no queue at all; (b) queue exists but only contains same-day-or-newer lots (same-day rebuy pattern — the key subtlety that required a second pass).
  - `_check_negative_positions` updated with same ISIN logic to suppress false negative warnings.
  - `symbol_aliases` now only needed for corporate actions where IB assigns a **new ISIN** (tender offers, mergers). Same-ISIN plain renames are auto-resolved.
- **Config cleanup**: `VER: OEWA` and `NOV: NOVd` removed from `users/matthias/config.local.yaml`; replaced with explanatory comments documenting why they're no longer needed.
- **6 new tests** replacing 4 old rename-hint tests (+2 net → 344 total).
- **Tagged and pushed** v0.3.1.

## Current state
- **Tests**: 344 passed, 0 failed
- **Matthias 2025 key figures** (unchanged from v0.3.0):
  - KZ 863 (foreign dividends + interest): EUR 11,340.73
  - KZ 994 (foreign gains): EUR 9,291.87
  - KZ 891 (domestic losses): EUR 1,107.12
  - KZ 892 (foreign losses): EUR 4,735.24
  - KeSt due: EUR 5,091.68 (incl. NMF)
  - WHT creditable: EUR 1,244.58
  - **KeSt remaining: EUR 3,267.63**
- **Known issues / open warnings**:
  - Negative positions: ADS, GAZ, HEN3, IFX, UNVB, SOLV — pre-2024 SAXO lots missing. Cosmetic only.
  - 33 total warnings (mostly WHT excess per stock, covered by WHT reclaim).

## Next session priorities
1. **WHT reclaim paper filings** (user action, not coding):
   - France: Cerfa n°12816 (Formulaire 5000 + 5001), deadline 2026-12-31, €12.06 excess
   - Germany: BZSt portal, €775.00 excess
   - Denmark: SKAT, €37.91 excess
2. **Jessie 2025 filing**: E1kv data ready; consider submitting ANV/L1 (~€106 refund)
3. **SAXO Holdings parser** — eliminate `portfolio_eur_supplement`; blocked on Holdings export sample
4. **E*Trade CSV parser** (`brokers/etrade_csv.py`) — `tradesdownload.csv` format
5. **OeKB data license** — email taxdata@oekb.at

## Blockers
- SAXO Holdings parser: waiting for user to export a sample Holdings xlsx from SAXO portal
- WHT filings: user has the Ansässigkeitsbescheinigung (ZS-AD) signed 2026-05-13 — ready to file
