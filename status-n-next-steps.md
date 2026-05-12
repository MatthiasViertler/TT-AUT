# Session Handoff — 2026-05-12

## What was done
- **Dynamic dividend yield** — trailing yield (actual dividends / Dec31 portfolio value) computed in pipeline and surfaced in Freedom dashboard and xlsx Freedom tab
  - `TaxSummary.dividend_yield_computed` field added to `core/models.py`
  - `_compute_dividend_yield()` helper in `core/pipeline.py` (testable, same pattern as `_compute_portfolio_value`)
  - Freedom HTML: yield slider defaults to computed value; green "auto" / grey "config" badge added (parallel to portfolio badge)
  - xlsx Freedom tab: computed yield in projection table and subtitle text
  - Warning printed when synthetic positions are excluded (inflated yield)
  - 5 new tests → **218 total**, all green
- **OeKB / Meldefonds research** — investigated data accessibility for future ETF/KZ 937 support
  - Public fund registry CSV (no auth): `https://my.oekb.at/kms-reporting/public?report=steuerdaten-liste-mf-gesamt&format=CSV` — confirms Meldefonds status by ISIN
  - Per-fund AE/WA figures are behind authenticated Angular SPA — no public API discovered
  - Decision: v1.0 via curated `data/oekb_ae.yaml`; v2.0 via OeKB data license (taxdata@oekb.at)
- **Roadmap updated** — CLAUDE.md Next up, memory, README, status handoff all reflect new priorities
- **Product strategy aligned** — v1.0 = reliable KeSt for AT stock investors (IB + SAXO + ETFs via curated dataset); website/blog post-v1.0

## Current state
- Tests: **218 passed**, 0 failed
- Key figures (Matthias 2025): KZ 863 €10,138 | KZ 891 €1,107 | KZ 994 €9,292 | KZ 892 €2,628 | KeSt remaining €3,560
- Computed portfolio: €63,914 (IB FIFO only; SAXO synthetic excluded) → trailing yield 18.39% (inflated — noted in output; resolves once portfolio snapshot parsers built)
- Known issues:
  - Yield inflated when SAXO positions excluded from portfolio valuation
  - `VER→OEWA` alias in Matthias config — remove before `--year 2026`
  - SOLV cost_eur=0 (spin-off allocation ratio unconfirmed — minor impact)
  - E*Trade holdings not captured (no parser yet — needs sample export)

## Next session priorities
1. **E*Trade parser** — waiting on sample export from Matthias; start immediately once available
2. **Meldefonds/ETF KZ 937** — begin with curated `data/oekb_ae.yaml` for top ~15 ETFs; same module pattern as `core/nichtmeldefonds.py`
3. **OeKB data license email** — one email to taxdata@oekb.at before v2.0 ETF automation work
4. **🔴 France WHT reclaim** — deadline 2026-12-31; paper filing; tool could pre-fill data sheet

## Blockers
- E*Trade parser: needs sample broker export from Matthias
- Meldefonds AE/WA data: no public API; curated dataset requires manual sourcing from fund "Steuerliche Mitteilung" PDFs
- France WHT: paper filing — Matthias must initiate; tool can prepare data but cannot file
