# Kapitalertrag — Task Backlog

Paste alongside CLAUDE.md at start of each session.
Move completed items to ## Done with the date.

---

## 🔴 URGENT — France 2024 Reclaim Deadline

- [ ] **File France 2024 WHT reclaim** — deadline 2026-12-31 (241 days). Excess: EUR 12.06.
      Cerfa n°12816 (Formulaire 5000 + 5001). Verify applicable WHT rate first.
      Stocks: MC (FR0000121014, EUR 7.00 excess), SAF (FR0000073272, EUR 5.06 excess).

---

## ✅ Matthias's Tax Filing — DONE (2026-05-04)

- [x] **Add OPT filter to `brokers/ib_csv.py`** — silently drop AssetClass == 'OPT' *(2026-05-04)*
- [x] **Handle P911 Return of Capital** — "return of capital" in description → skip group *(2026-05-04)*
      P911 2024: EUR 2.31/sh (€115.50 total), P911 2025: EUR 1.49/sh (€74.66 total) — both skipped ✓
- [x] **Run Matthias end-to-end** — `python main.py --input data/matthias_*.csv --year 2025` ✓ *(2026-05-04)*
      Special cases resolved: BAYN reversal ✓, 1COV/1CO tender (symbol_aliases) ✓, VNA 'd' normalization ✓
      SOLV (Solventum spin-off): no buy record → cost basis 0, minor impact. Needs manual_cost_basis feature.
- [x] **WHT reclaim assistant output** (`output/wht_reclaim.py`) *(2026-05-04)*
      Total reclaimable EUR 852.14 (DE: 775.00, DK: 37.91, FR: 39.24)
      ⚠️ France 2024 deadline 2026-12-31 — moved to 🔴 above.

---

## ✅ Jessie's 2025 Filing — Tool is ready

Jessie's portfolio is individual stocks + cash transactions only. No accumulating ETFs,
no funds, no REITs/BDCs. The following items are N/A for her current holdings and
therefore not blocking her filing. Keeping them here for when fund support is added.

- **KZ 937** — N/A (only applies to accumulating funds reporting via OeKB)
- **Nichtmeldefonds check** — N/A (only applies to OeKB-unregistered funds)
      Punitive treatment if ever relevant: 27.5% on 90% of annual price increase
- **Regelbesteuerungsoption** — Jessie uses standard 27.5% KESt for 2025.
      `--regelbesteuerung` flag still useful for future / other users → moved to 🟡 below.

---

## 🟡 Dashboard & Output

- [x] **Wire freedom dashboard into pipeline** — generate `output/{person}_{year}_freedom.html`
      auto-populated with real dividend data from that run. Sliders stay interactive. *(2026-05-01)*
- [x] **WHT reclaim assistant** — `output/wht_reclaim.py`, wired into writer.py *(2026-05-04)*
      Per-country/year report with treaty rates, deadlines, per-stock breakdown.
- [x] **Excel "Freedom" tab** — tab in dashboard.xlsx: key metrics, per-symbol holdings,
      10-year projection table (portfolio × yield/growth + monthly contribution) *(2026-05-04)*
- [ ] **Freedom tab — dynamic portfolio value** — aggregate real holdings across all brokers
      (IB + SAXO positions) instead of static `portfolio_eur` config value; use as starting
      point for 10-year projection. Requires "current holdings" model (no such model yet).
- [ ] **Freedom tab — dynamic dividend yield** — compute trailing yield from actual dividend
      transactions instead of static `yield_pct` config; apply to projection table.

---

## 🟡 Tool: Correctness & Robustness

- [x] **Manual cost basis override** — `manual_cost_basis` in config.local.yaml; lots injected
      into FIFO queue in date order alongside real buys. 8 tests. *(2026-05-04)*
      SOLV configured as cost_eur=0 until 3M spin-off allocation ratio confirmed.
- [x] **Cross-check vs IB FifoPnlRealized** — `broker_fifo_pnl_eur` field captured from
      HEADER/DATA SELL rows; warns if diff > €1.00. 8 tests. *(2026-05-04)*
- [x] **Negative position check** — warns if total sells > total buys per symbol (all years);
      respects symbol_aliases. 5 tests. *(2026-05-04)*
- [x] **FX rate sanity check** — warns (log) if ECB rate deviates >20% from prior day;
      only fires if prior day is in cache (no extra fetches). 5 tests. *(2026-05-04)*
- [x] **Pytest skeleton** (`tests/`) — 65 tests across parser, WHT reclaim, sanity, manual
      cost basis, FIFO cross-check, position check, FX sanity. *(2026-05-04)*

---

## 🟡 Tax Features

- [ ] **Arbeitnehmerveranlagung checklist** — per-person deduction checklist output
      (Werbungskosten, Pendlerpauschale, Sonderausgaben, außerg. Belastungen)
      ⚠️ Jessie filing due 2026-06-30 — E1kv figures ready, checklist missing
- [ ] **Verlustausgleich tracker** — year-by-year gain/loss table
- [ ] **KZ 937 semi-automation** — OeKB API per ISIN for Ausschüttungsgleiche Erträge
- [ ] **Nichtmeldefonds detection** — OeKB lookup + punitive tax calculation
- [ ] **Regelbesteuerungsoption mode** — `--regelbesteuerung` flag, recalculates
      at progressive income tax rate instead of flat 27.5% KESt
      Low priority: Matthias income level → progressive rate likely worse than 27.5%;
      N/A for Jessie 2025. Useful only if a user's marginal rate < 27.5%.

---

## 🔵 Usability & Automation

- [ ] **`--input-dir` folder scanning** — accept a directory instead of individual files;
      auto-detect broker per file; load all years for FIFO, filter output to `--year`
      Foundation for GUI folder-picker later.
- [ ] **IBKR Flex Web Service auto-fetch** — configure token + query_id in config.local.yaml,
      `python main.py --fetch-ibkr --year 2025` pulls report directly, no browser needed
- [ ] **Local web UI** — Flask/FastAPI + HTML; folder picker, pipeline progress, inline results,
      download buttons. One command to start. No CLI knowledge required.
- [ ] **FinanzOnline XML output** — machine-readable upload format for direct e-filing

---

## 🔵 v2.x — New Brokers

- [x] SAXO parser — `brokers/saxo_xlsx.py` (AggregatedAmounts) + `brokers/saxo_closedpos_xlsx.py`
      (ClosedPositions, real quantities); `saxo_skip_agg_trades` flag; 131 tests *(2026-05-05)*
- [ ] E*Trade parser (`brokers/etrade.py`) — need sample export first
- [ ] REIT/BDC handling (US return of capital, §199A dividends, 1099-DIV boxes)
- [ ] `--compare` mode — merge self + jessie into one dashboard
- [ ] Prior-year loss carryforward input

---

## 📋 Start-of-Session Checklist

1. Paste `CLAUDE.md` + `TASKS.md`
2. Confirm today's focus task
3. `git pull` if working across machines
4. Create a feature branch and push immediately:
   `git checkout -b feature/name && git push -u origin feature/name`

## 📋 End-of-Session Checklist

1. **Update `CLAUDE.md`** — always, every session (keep it concise; remove stale info)
2. **Update `TASKS.md`** — completed → Done with date, add newly discovered tasks
3. **Run tests** — `pytest tests/` (once test suite exists; failing tests block commit)
4. **Commit meaningful checkpoints** — don't wait until end of session; commit after each feature
5. **Open a PR and merge via GitHub:**
   ```
   gh pr create --title "feature title" --body "summary of changes"
   gh pr merge <number> --merge --delete-branch
   ```
   This keeps full branch + diff history visible on GitHub.
6. **Push** `main` to remote: `git push origin main`
7. **Update `README.md`** — reflect any new features, config options, or output files
8. Regenerate `docs/` only if user-facing CLI behaviour changed

---

## ✅ Done

- [x] Matthias end-to-end run — TT-AUT BOS/EOS parser, OPT filter, P911 RoC, DE 'd' normalization *(2026-05-04)*
      symbol_aliases for tender offers (1COV/1CO Covestro); VNA FIFO fix; all years 2021–2026
- [x] WHT reclaim assistant — `output/wht_reclaim.py`; EUR 852.14 total reclaimable *(2026-05-04)*
- [x] Extended E1kv output — full 1.3.1–1.7 structure + Saldo 1.3 in Excel + TXT *(2026-05-02)*
- [x] Nichtmeldefonds support (§ 186 InvFG) — pauschal AE, auto price-fetch via yfinance *(2026-05-02)*
      Config: symbol + type + currency only; prices cached in data/price_cache/
- [x] Initial build — parser, FX, tax engine, Excel output *(2026-05-01)*
- [x] Fix IB Flex Query format (BOF/HEADER/DATA, field name mismatches) *(2026-05-01)*
- [x] Fix FX cache returning strings not Decimals *(2026-05-01)*
- [x] Fix openpyxl import structure *(2026-05-01)*
- [x] Fix duplicate IB rows (CostBasis ±1.00 tiebreaker in raw_id) *(2026-05-01)*
- [x] Fix WHT warning threshold — suppress rounding noise < €0.05 *(2026-05-01)*
- [x] Auto-detect --person from account ID via account_map in config.yaml *(2026-05-01)*
- [x] Git repo, GitHub SSH, VS Code workspace configured *(2026-05-01)*
- [x] CLAUDE.md, CLAUDE-archive.md, SESSION-TEMPLATE.md, TASKS.md *(2026-05-01)*
- [x] Jessie 2024/2025/2026 tested and producing correct output *(2026-05-01)*
- [x] Full setup + usage documentation (Word) *(2026-05-01)*
- [x] ANX/EMWE — confirmed non-issue (transferred positions, below threshold) *(2026-05-01)*
- [x] Dividend freedom dashboard — interactive HTML with sliders built *(2026-05-01)*
      Shows: passive salary, freedom %, milestones, projection, holdings breakdown
- [x] Wire freedom dashboard into pipeline output *(2026-05-01)*
      Generates output/{person}_{year}_freedom.html with real dividend data
