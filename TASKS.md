# Kapitalertrag — Task Backlog

Paste alongside CLAUDE.md at start of each session.
Move completed items to ## Done with the date.

---

## 🔴 BLOCKING — Jessie's Tax Filing

- [ ] **Add Matthias's IBKR account ID** to `config.yaml` account_map
- [ ] **Verify KZ 937** for any current open accumulating ETF/fund positions via oekb.at
- [ ] **Nichtmeldefonds check** — verify current open position ISINs at OeKB
      Punitive treatment if unregistered: 27.5% on 90% of annual price increase
- [ ] **Regelbesteuerungsoption** — Jessie has income in 2025 so standard 27.5% applies.
      Still add `--regelbesteuerung` flag to tool for future use / other users.

---

## 🟡 Dashboard & Output

- [ ] **Wire freedom dashboard into pipeline** — generate `output/{person}_{year}_freedom.html`
      auto-populated with real dividend data from that run. Sliders stay interactive.
- [ ] **Excel "Freedom" tab** — 5th tab in dashboard.xlsx: year-over-year dividend bars,
      freedom progress bar, projection chart (static at default assumptions)
- [ ] **WHT reclaim assistant** — per overwithheld dividend: country, authority,
      form, claimable amount, filing deadline
      DE: BZSt / Antrag auf Erstattung (4yr) → bzst.de
      DK: SKAT / Form 06.003 (3yr) → skat.dk

---

## 🟡 Tool: Correctness & Robustness

- [ ] **Manual cost basis override** — config.yaml entry for positions transferred
      from another broker (no purchase record in IB exports)
      ```yaml
      manual_cost_basis:
        - symbol: EXAMPLE
          isin: XX0000000000
          purchase_date: 2022-03-15
          quantity: 100
          cost_eur: 5000.00
      ```
- [ ] **Cross-check vs IB FifoPnlRealized** — compare our FIFO P&L against IB's
      per-trade value, warn if difference > €1.00
- [ ] **Negative position check** — warn if net holding goes negative (sell > bought)
- [ ] **FX rate sanity check** — warn if ECB rate deviates >20% from prior day
- [ ] **Automated test suite** (`tests/`) — fixture CSVs covering:
      - Dividend + WHT matching
      - Multi-year FIFO (buy 2024, sell 2026)
      - Domestic vs foreign classification
      - Duplicate row deduplication
      - WHT warning threshold

---

## 🟡 Tax Features

- [ ] **Regelbesteuerungsoption mode** — `--regelbesteuerung` flag, recalculates
      at progressive income tax rate instead of flat 27.5% KESt
- [ ] **Verlustausgleich tracker** — year-by-year gain/loss table
- [ ] **KZ 937 semi-automation** — OeKB API per ISIN for Ausschüttungsgleiche Erträge
- [ ] **Nichtmeldefonds detection** — OeKB lookup + punitive tax calculation
- [ ] **Arbeitnehmerveranlagung checklist** — per-person deduction checklist output
      (Werbungskosten, Pendlerpauschale, Sonderausgaben, außerg. Belastungen)

---

## 🔵 v2.x — New Brokers (after Jessie's filing complete)

- [ ] SAXO parser (`brokers/saxo.py`) — need sample export first
- [ ] E*Trade parser (`brokers/etrade.py`) — need sample export first
- [ ] REIT/BDC handling (US return of capital, §199A dividends, 1099-DIV boxes)
- [ ] `--compare` mode — merge self + jessie into one dashboard
- [ ] Prior-year loss carryforward input

---

## 📋 Start-of-Session Checklist

1. Paste `CLAUDE.md` + `TASKS.md`
2. Confirm today's focus task
3. `git pull` if working across machines

## 📋 End-of-Session Checklist

1. Update `CLAUDE.md` if any behaviour changed
2. Update `TASKS.md` (completed → Done, add newly discovered)
3. Regenerate `docs/` if user-facing behaviour changed
4. Commit + push

---

## ✅ Done

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
      TODO: wire into pipeline + Excel tab (in 🟡 above)
