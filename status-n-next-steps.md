# Status & Next Steps — as of 2026-05-06

Handoff document for resuming after a context-limit break.
Start each new session by reading CLAUDE.md + TASKS.md alongside this file.

---

## What was completed in the last two sessions (2026-05-06)

### Session 1 — Excel audit trail + FIFO bug + Verbund alias
- **Excel audit trail**: per-sell Gain/Loss EUR + Cost Basis EUR columns in Trades tab; SUMPRODUCT summary rows (KZ 981/994/891/892 linkage); Dividends tab SUMIF rows; E1kv Summary uses cross-sheet formula references. Commit `d39ae84`.
- **FIFO ghost-lot fix**: prior-year sells now drain FIFO lots; current-year sells get correct cost basis. Bug was `_process_capital_gains` only receiving `year_sells` → prior lots stayed "ghost". Fixed by passing `all_sells`; `year_sell_ids = {id(s) for s in year_sells}` gates accumulation. Regression test added. Commit `bd9d6f2`.
- **VER→OEWA alias**: IB renamed Verbund AG ticker OEWA→VER in Dec 2025. Loss-harvest sell 2025-12-17 (150 sh) was under VER, all lots under OEWA → -€15 vs expected -€1,107. Added `VER: OEWA` to `users/matthias/config.local.yaml`. Commit `bd9d6f2`.
  - **⚠️ 2026 action**: remove `VER: OEWA` alias before running `--year 2026` (OEWA lots fully consumed).
- **Matthias 2025 final numbers**: KZ 863 €10,138 | KZ 891 €1,107 | KZ 994 €9,292 | KZ 892 €2,628 | KeSt remaining **€3,560** (filed).

### Session 2 — FIFO diagnostic warnings (2026-05-06)
- **ISIN rename hint**: if an unmatched sell's ISIN exists under a different buy symbol → warning suggests exact `symbol_aliases` entry. Catches future ticker renames before you even look at the numbers.
- **Same-day round-trip detection**: sell + same-day repurchase of same symbol with |gain| < 1% of proceeds (>€500) → warning flags possible FIFO mismatch against new buy instead of older lots.
- 9 new tests in `tests/test_fifo_diagnostics.py`. Total: **180 tests**, all green.
- Commit `222412b`, pushed to `github.com:MatthiasViertler/TT-AUT.git` main.

---

## Current codebase state (2026-05-06)

### Filing status
- **Matthias 2025**: FILED ✓. Numbers confirmed. No open items.
- **Jessie 2025**: Tool ready. She needs to run it and file via FinanzOnline.
  - ⚠️ Jessie: add `anv:` section to her `config.local.yaml` before 2026-06-30 deadline.

### Active config notes (users/matthias/config.local.yaml)
- `symbol_aliases: {1CO: 1COV, VER: OEWA}` — **remove VER: OEWA for 2026+**
- `saxo_skip_agg_dividends: true` — AA+SD anti-double-count
- `at_residency_start_year: 2024` — WHT reclaim covers 2024+
- `manual_cost_basis` — 44 SAXO SG pre-2024 positions seeded (qty=1 convention)

### Test suite
- `python -m pytest tests/` — 180 tests across: IB parsers (BOS/EOS + HEADER/DATA), SAXO parsers (AA + SD + ClosedPositions), WHT reclaim, ANV checklist, FIFO (ghost-lot regression, cross-check, negative position, ISIN rename, round-trip), FX sanity, Nichtmeldefonds, Verlustausgleich

---

## Open tasks (priority order)

### 🔴 Urgent
1. **France 2024 WHT reclaim** — deadline **2026-12-31** (241 days from 2026-05-06).
   - Cerfa n°12816 = Formulaire 5000 (domicile cert) + Formulaire 5001 (claim).
   - Stocks: MC (FR0000121014, €7.00 excess), SAF (FR0000073272, €5.06 excess). Total: **€12.06**.
   - Ansässigkeitsbescheinigung (ZS-AD) already filed at Finanzamt 2026-05-03 — get it stamped and attach.
   - Nothing blocking this from a code perspective; it's a paper filing task.

### 🟡 Medium priority
2. **E\*Trade parser** (`brokers/etrade.py`) — needed to capture Matthias's E*Trade holdings.
   - Blocker: no sample export yet. Matthias needs to export from E*Trade and provide it.
   - Pattern to follow: `brokers/ib_csv.py` or `brokers/saxo_xlsx.py` as reference.
   - Output: `NormalizedTransaction` list, same as other parsers.
   - Auto-detect in `brokers/__init__.py`: add file pattern match (likely `.csv` with E*Trade headers).

3. **Freedom tab — dynamic portfolio value** — aggregate real holdings across all brokers instead of static `portfolio_eur` in config. Requires building a "current holdings" model (running balance of buys minus sells per symbol). No such model yet; needs design first.

4. **Freedom tab — dynamic dividend yield** — compute trailing yield from actual dividend transactions instead of static `yield_pct`. Simple: sum(dividends in last 12 months) / estimated portfolio value.

5. **Verlustausgleich tracker** — year-by-year gain/loss table. Already partially there via the Overview tab multi-year JSON; may just need a dedicated output section or improved display.

### 🔵 Low priority / future
- Remove `VER: OEWA` alias from Matthias config before 2026 tax run
- `--input-dir` folder scanning
- IBKR Flex Web Service auto-fetch
- Local web UI (Flask/FastAPI)
- FinanzOnline XML output
- KZ 937 semi-automation (OeKB API)
- Nichtmeldefonds detection (OeKB lookup)
- `--regelbesteuerung` flag
- REIT/BDC handling (US §199A, 1099-DIV boxes)
- `--compare` mode (Matthias + Jessie combined dashboard)

---

## Architecture notes for cold start

### FIFO correctness — how it works now
`_process_capital_gains(all_buys, year_sells, all_sells, summary)` in `core/tax_engine.py`:
1. Builds FIFO queues from ALL buys (all years) + `manual_cost_basis` entries in chronological order.
2. Processes ALL sells (all years) chronologically through the queue — prior-year sells drain their lots.
3. Uses `year_sell_ids = {id(s) for s in year_sells}` to only accumulate KZ/gain-loss for the target tax year.

### Diagnostic warnings — where they live
Both in `_process_capital_gains`, `core/tax_engine.py`:
- **ISIN rename hint** (~line 186): fires inside the `if qty_to_match > ZERO and is_year_sell:` block.
  Looks up `sell.isin` in `isin_to_symbols` dict (built from all buys + manual_cost_basis). Suggests `symbol_aliases` entry.
- **Round-trip check** (~line 216): fires after `net_gain` computed. Uses `same_day_buy_syms` set (built from all buys). Condition: proceeds > 500 AND |gain| < 1% of proceeds AND same-day buy exists.

### SAXO qty=1 convention — critical design note
SAXO AggregatedAmounts has no per-share quantity. Every trade stored as `quantity=1`, `cost_per_unit = total_eur`. FIFO consumes one lot per sell — correct given the data. `manual_cost_basis` entries must also use `quantity: 1`.

---

## Known limitations / future footguns

- **VER→OEWA alias removal**: must be done manually before `--year 2026`. TASKS.md has the reminder (🔵 section).
- **SOLV cost basis**: set to 0 (spin-off, no buy record). Real 3M spin-off allocation ratio not yet confirmed. May need updating.
- **E*Trade holdings**: not captured at all yet. Matthias has holdings there; 2025 filing was done without them (unknown gap).
- **Round-trip warning false positives**: the 1%/€500 threshold can fire on genuine day trades. Warning is clearly labeled "possible" — user should verify. Threshold is in `_process_capital_gains`, easy to tune if too noisy.
- **KZ 937**: all Nichtmeldefonds (O, EPR, OHI, WPC, ARCC) are computed, but OeKB-registered funds still need manual OeKB lookup.

---

## WHT reclaim status (Matthias)

| Country | Amount | Status |
|---------|--------|--------|
| DE | €775.00 | ZS-AD filed 2026-05-03 at Finanzamt; await processing |
| DK | €37.91 | No action yet |
| FR | €39.24 | **⚠️ Deadline 2026-12-31** — €12.06 excess (2024 only); Cerfa n°12816 |

---

## Session startup checklist (next time)

1. `git pull` (confirm on latest main)
2. Read CLAUDE.md + TASKS.md + this file
3. `python -m pytest tests/ -q` — confirm 180 tests green
4. Confirm today's focus with Matthias before starting work
5. Create feature branch + push immediately before coding
