# Session Handoff — 2026-05-16

## What was done
- **NMF share count bug fixed** (`core/nichtmeldefonds.py`): SAXO qty=1 convention caused
  `_net_shares_at_year_end` to return 1 instead of real share count. Added `shares_held_override`
  per-year dict in nichtmeldefonds config. Matthias 2024: 1 phantom position (€1 KeSt) →
  5 real positions (€841 KeSt). 2025: €985 KeSt. 2025 KeSt remaining: €3,268 → **€4,252**.
- **9 new tests** in `tests/test_nichtmeldefonds.py` (353 total): `_net_shares_at_year_end`
  edge cases, override per year, fallback to transactions, 10%/90% AE rule correctness.
- **Per-year NMF output files** written to `users/matthias/output/{year}/matthias_{year}_nichtmeldefonds.txt`
  for 2024 and 2025 — user to compare against manual Excel.
- **3 FAQ docs** created in `docs/`:
  - `faq-steuereinfach-brokers.md` — why TR users still benefit from this tool (cross-broker
    Verlustausgleich, WHT reclaims, unified FIRE dashboard)
  - `faq-meldefonds-etfs.md` — accumulating ETF phantom income explained; dist vs acc comparison
    table; cost basis step-up; when to choose each
  - `faq-nichtmeldefonds-reits.md` — US REIT double taxation mechanics; when they work for
    AT investors; embedded tax loss recovery; AT-friendly alternatives table; exit strategy
- **TASKS.md** expanded: Portfolio Intelligence section (AT tax efficiency analyzer, NMF
  alternative suggestions, portfolio health scraper); bonds/Anleihen tracking; savings interest;
  steuereinfach architecture; Trade Republic parser; physical metals; crypto; FinanzOnline guide;
  multi-year dividend trend; NMF AE cost basis step-up on sale.

## Current state
- **Tests**: 353 passed, 0 failed
- **Matthias 2025 key figures** (updated):
  - KZ 863 (foreign dividends + interest): EUR 11,340.73
  - KZ 994 (foreign gains): EUR 9,291.87
  - KZ 891 (domestic losses): EUR 1,107.12
  - KZ 892 (foreign losses): EUR 4,735.24
  - NMF KeSt 2025 (O/EPR/OHI/WPC/ARCC): EUR 985.39
  - WHT creditable: EUR 1,244.58
  - **KeSt remaining: EUR 4,251.72**
- **Matthias 2024 NMF** (for user to verify vs Excel):
  - O 150sh / EPR 110sh / OHI 150sh / WPC 100sh / ARCC 110sh
  - AE total EUR 3,058.53 / KeSt EUR 841.10
  - See `users/matthias/output/2024/matthias_2024_nichtmeldefonds.txt`
- **Known issues / open warnings**:
  - Negative positions: ADS, GAZ, HEN3, IFX, UNVB, SOLV — pre-2024 SAXO lots missing. Cosmetic.
  - 33 total warnings (mostly WHT excess per stock, covered by WHT reclaim).
  - **NMF AE cost basis step-up NOT YET IMPLEMENTED** — when O/EPR/WPC/ARCC are sold in 2026,
    FIFO will overstate the taxable gain. Fix required before 2026 year-end filing.

## Next session priorities
1. **AT tax efficiency analyzer** (HIGH — first coding task): per-position flag for NMF burden,
   embedded tax loss estimate, WHT-excess countries, suggested alternatives. All data already
   available — no new APIs. See TASKS.md → Portfolio Intelligence.
2. **NMF AE cost basis step-up on sale**: accumulate AE per symbol across years; apply as
   cost-basis adjustment in FIFO engine before sells. Required before Matthias 2026 filing.
3. **WHT reclaim paper filings** (user action): France deadline 2026-12-31 (€12.06 excess);
   Germany BZSt (€775); Denmark SKAT (€37.91).
4. **2024 NMF comparison**: user to check `matthias_2024_nichtmeldefonds.txt` vs manual Excel.

## Blockers
- 2024 NMF verification: waiting for user to compare output file against Excel figures.
- SAXO Holdings parser: waiting for user to export Holdings xlsx sample.
- NMF AE cost basis step-up: design decision needed — accumulate AE in pipeline and inject
  into FIFO lots, or separate adjustment pass at sell time.
