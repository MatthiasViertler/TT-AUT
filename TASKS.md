# Kapitalertrag — Task Backlog

Paste alongside CLAUDE.md at start of each session.
Move completed items to ## Done with the date.

---

## 🔴 BLOCKING — Matthias's Tax Filing

Do these in order before the first end-to-end run:

- [ ] **Add OPT filter to `brokers/ib_csv.py`** — silently drop rows where AssetClass == 'OPT';
      log count at INFO level. Derivatives KZ deferred intentionally.
- [ ] **Handle P911 Return of Capital** — detect `Type == "Return of Capital"` in CTRN section;
      treat as cost basis adjustment (skip taxing as dividend). Log warning if encountered.
- [ ] **Run Matthias end-to-end** — `python main.py --input data/matthias_*.csv --year 2025`
      Account ID U7251654 already in config.local.yaml. Exports: 2021–2025 (no 2020).
      Expected special cases: BAYN reversal (2021), GAZ (Russian ADR, worthless), P911 RoC (2025).
- [ ] **WHT reclaim assistant output** — per-country/year dividend summary + per-dividend
      line items formatted for BZSt attachment (and equivalent for other countries).
      ⚠️  RESIDENCY CORRECTION: Matthias was German tax resident 2020–2023, Austrian from 2024.
      Claimable years = **2024 and 2025 only**. Earlier docs showing 2022–2025 are WRONG.
      DE (BZSt): file for 2024 + 2025. Deadline 2028/2029 — no urgency.
      DK (SKAT Form 06.003): Novo Nordisk confirmed → 12% excess (27% − 15% DBA). 3yr window (2024 → deadline 31.12.2027).
      FR: skip — French WHT ~12.8% already below 15% DBA cap.
      2026: file in Jan 2027 for complete year (deadline 2030).
      ZS-AD (AT residency cert): being filed at Finanzamt 2026-05-03.

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
- [ ] **Excel "Freedom" tab** — 5th tab in dashboard.xlsx: year-over-year dividend bars,
      freedom progress bar, projection chart (static at default assumptions)
- [ ] **WHT reclaim assistant** 🔴 HIGH PRIORITY — Matthias has 4 years of DE excess WHT
      to reclaim (BZSt 4yr window: 2022–2025 all still valid). Data already computed.
      Output: per-country per-year summary + per-dividend line items ready for BZSt form.
      Also needed: Ansässigkeitsbescheinigung (Austrian Finanzamt) + broker tax certs (manual).
      DE: BZSt / "Antrag auf Erstattung der deutschen Kapitalertragsteuer" (4yr) → bzst.de
      DK: SKAT / Form 06.003 (3yr) → skat.dk
      NL: Belastingdienst (3yr), US: generally N/A if DBA 15% already applied

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
- [ ] **Pytest skeleton** (`tests/`) — start this session, grow with each feature.
      Fixture CSVs to cover:
      - Dividend + WHT matching
      - Multi-year FIFO (buy 2024, sell 2026)
      - Domestic vs foreign classification
      - Duplicate row deduplication
      - WHT warning threshold
      Rule: every new feature ships with at least one test.

---

## 🟡 Tax Features

- [ ] **Regelbesteuerungsoption mode** — `--regelbesteuerung` flag, recalculates
      at progressive income tax rate instead of flat 27.5% KESt
      (N/A for Jessie 2025 — standard 27.5% applies; useful for future / other users)
- [ ] **Verlustausgleich tracker** — year-by-year gain/loss table
- [ ] **KZ 937 semi-automation** — OeKB API per ISIN for Ausschüttungsgleiche Erträge
- [ ] **Nichtmeldefonds detection** — OeKB lookup + punitive tax calculation
- [ ] **Arbeitnehmerveranlagung checklist** — per-person deduction checklist output
      (Werbungskosten, Pendlerpauschale, Sonderausgaben, außerg. Belastungen)

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
