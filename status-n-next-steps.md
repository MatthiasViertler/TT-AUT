# Session Handoff — 2026-05-17

## What was done
- **Root cause diagnosed**: IBKR Flex "last 365 days" window caused two distinct double-counting bugs:
  1. Multiple Flex files with different to_dates → different raw_ids for the same dividend
  2. 365-day Flex spanning May 2025–May 2026 → 2025 dividends re-imported at trade_date=2026-05-15 → counted again in 2026
- **Three-rule suppression logic** in `core/pipeline.py`:
  - Rule 1 (Flex vs Flex): keep dividends from latest Flex per year only
  - Rule 2 (cross-year Flex): if Flex.from_date.year has a full TT-AUT, suppress Flex dividends
  - Rule 3 (TT-AUT partial vs YTD Flex): suppress TT-AUT, Flex is authoritative
- **`get_ib_file_info()`** added to `brokers/ib_csv.py`: BOF pre-scan → (is_flex, from_date, to_date)
- **`suppress_cash` parameter** added to `parse()` and threaded through `brokers/__init__.py`
- **10 new tests** in `tests/test_ib_flex_taut_dedup.py`
- **IBKR Flex query changed to "Year to Date"** by user — new Flex from=2026-01-01; cross-year rule no longer fires
- Real account ID in docs caught and fixed by pre-commit hook ✓

## Current state
- Tests: 394/394 passing
- 2025: KZ 862 €1,613.10 | KZ 863 €11,381.01 | KZ 994 €9,291.87 | KZ 891 €1,107.12 | KZ 892 €4,735.24 | KZ 899 €443.60 | KeSt remaining **€3,808.12**
- 2026 YTD (2026-05-17): KZ 862 €472.50 | KZ 863 €8,741.04 | KZ 994 €17,598.67 | KZ 899 €129.94 | KZ 998 €1,100.14
- Known issues: NMF year-end prices unavailable for 2026 (expected); AIRD 404 warning (delisted)

## Next session priorities
1. **WHT reclaim paper filings** — France deadline 2026-12-31 is top urgency
2. **SAXO Holdings parser** — blocked on Holdings xlsx export sample
3. **E*Trade CSV parser** (`tradesdownload.csv`) — removes PDF dependency
4. **OeKB data license** — email taxdata@oekb.at

## Blockers
- SAXO Holdings parser: waiting on Holdings export sample from user
- WHT reclaims: user action (paper filings), no code needed
