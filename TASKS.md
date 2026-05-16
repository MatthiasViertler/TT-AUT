# Kapitalertrag — Task Backlog

Paste alongside CLAUDE.md at start of each session.
Move completed items to ## Done with the date.

---

## 🔴 URGENT — WHT Reclaim Forms

AT Ansässigkeitsbescheinigung (ZS-AD) received signed from Finanzamt 2026-05-13 ✓

- [ ] **File France 2024 WHT reclaim** — deadline 2026-12-31 (232 days). Excess: EUR 12.06.
      Cerfa n°12816 (Formulaire 5000 + 5001). Verify applicable WHT rate first.
      Stocks: MC (FR0000121014, EUR 7.00 excess), SAF (FR0000073272, EUR 5.06 excess).
- [ ] **File Germany WHT reclaim** — Erstattung Kapitalertragsteuer. Excess: EUR 775.00.
      File with Bundeszentralamt für Steuern (BZSt) — use their online portal or Erstattungsantrag form.
- [ ] **File Denmark WHT reclaim** — Excess: EUR 37.91. File with SKAT (Danish tax authority).
- [ ] **File Ireland Interest Reclaim** — form pending; amount TBD.

---

## ✅ Matthias's Tax Filing — DONE (2026-05-04, revised 2026-05-06)

- [x] **Add OPT filter to `brokers/ib_csv.py`** — silently drop AssetClass == 'OPT' *(2026-05-04)*
- [x] **Handle P911 Return of Capital** — "return of capital" in description → skip group *(2026-05-04)*
      P911 2024: EUR 2.31/sh (€115.50 total), P911 2025: EUR 1.49/sh (€74.66 total) — both skipped ✓
- [x] **Run Matthias end-to-end** — `python main.py --input data/matthias_*.csv --year 2025` ✓ *(2026-05-04)*
      Special cases resolved: BAYN reversal ✓, 1COV/1CO tender (symbol_aliases) ✓, VNA 'd' normalization ✓
      SOLV (Solventum spin-off): no buy record → cost basis 0, minor impact. Needs manual_cost_basis feature.
- [x] **FIFO ghost-lot fix** — prior-year sells now drain their lots; current-year sells use correct basis *(2026-05-06)*
      Bug: only tax-year sells processed → prior-year sells left "ghost" lots. Fix: all years' sells run through queue.
      1 regression test added (172 total).
- [x] **VER→OEWA symbol alias (Verbund AG)** — IB renamed ticker OEWA→VER in Dec 2025 *(2026-05-06)*
      Added `VER: OEWA` to symbol_aliases. KZ 891 now correctly shows €1,107 domestic loss.
      ⚠️ Remove this alias for 2026+ once all OEWA lots are consumed (150 shares sold 2025-12-17).
      Revised 2025 totals: KZ 891 €1,107 | KZ 994 €9,292 | KeSt remaining **€3,560** (was ~€3,914)
- [x] **FIFO diagnostic warnings** — ISIN rename hint + same-day round-trip detection *(2026-05-06)*
      (1) Unmatched sell: if same ISIN exists under a different buy symbol → suggests exact symbol_aliases entry.
      (2) Same-day round-trip with |gain| < 1% of proceeds (>€500) → warns of possible FIFO mismatch.
      Would have flagged both the ghost-lot and VER/OEWA bugs proactively. 9 tests added (180 total).
- [x] **WHT reclaim assistant output** (`generators/wht_reclaim.py`) *(2026-05-04)*
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

- [x] **Excel audit trail — per-transaction gain/loss** *(2026-05-06)*
      Trades tab: Gain/Loss EUR + Cost Basis EUR columns per sell; SUMPRODUCT summary rows
      (domestic/foreign gains + losses → KZ 981/994/891/892). Dividends tab: SUMIF summary rows
      (KZ 862/863 + total WHT). E1kv Summary: KZ cells + Saldo + Net Taxable now use cross-sheet
      formula references instead of hard-coded values. 4 new tests (170 total).

- [x] **Wire freedom dashboard into pipeline** — generate `output/{person}_{year}_freedom.html`
      auto-populated with real dividend data from that run. Sliders stay interactive. *(2026-05-01)*
- [x] **WHT reclaim assistant** — `generators/wht_reclaim.py`, wired into writer.py *(2026-05-04)*
      Per-country/year report with treaty rates, deadlines, per-stock breakdown.
- [x] **Excel "Freedom" tab** — tab in dashboard.xlsx: key metrics, per-symbol holdings,
      10-year projection table (portfolio × yield/growth + monthly contribution) *(2026-05-04)*
- [x] **Freedom tab — dynamic portfolio value** — remaining FIFO lots × Dec31 yfinance price × ECB FX
      → `summary.portfolio_eur_computed`. SAXO AggregatedAmounts (broker='saxo') and manual_cost_basis
      lots marked synthetic and excluded. HTML slider default = computed; dynamic max (no 500k cap);
      auto/config badge. Excel label distinguishes source. 16 tests. *(2026-05-12)*
- [x] **Freedom tab — dynamic dividend yield** — trailing yield = actual dividends / Dec31 portfolio value
      → `summary.dividend_yield_computed`. HTML yield slider defaults to computed; green "auto" / grey "config"
      badge. xlsx subtitle + projection use computed value. Warning when synthetic positions inflate yield.
      5 tests → 218 total. *(2026-05-12)*
- [x] **Freedom tab — per-symbol holdings table** *(2026-05-13)* — Symbol [Type] / Qty / EUR Value /
      Port% / Divs EUR / Yield% in both Freedom HTML and Excel tab. Synthetic lots: ~qty + —.
      Sold positions at bottom. Sort: value|yield|alpha. Optional group_by_type. 26 tests → 261 total.
- [x] **Multi-year dividend trend** *(2026-05-16, v0.3.5)* — openpyxl `BarChart` added below Overview
      table in `generators/writer.py`; shows when 2+ years of history exist.
- [ ] **FinanzOnline filing guide** — `docs/finanz-online-guide.md` with screenshots and
      step-by-step navigation for E1kv entry, KZ fields, and submission. FinanzOnline is
      non-obvious to navigate; a companion guide adds real value alongside the XML output feature.

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
- [x] **OPT rows warning** *(2026-05-16, v0.3.5)* — `brokers/ib_csv.py`: `log.info` → visible
      `[warn]` print when options trades are skipped.

---

## 🟡 Tax Features

- [x] **Arbeitnehmerveranlagung checklist** — `generators/anv_checklist.py`; L1 deduction reminder *(2026-05-05)*
      Werbungskosten (home office, Pendlerpauschale, union, training), Sonderausgaben,
      außerg. Belastungen, Familienbonus Plus. 21 tests. Config: `anv:` in config.local.yaml.
      ⚠️ Jessie: add `anv:` to config.local.yaml and re-run to generate checklist before 2026-06-30
- [x] **Verlustausgleich tracker** — Overview tab expanded: Dom Gains (KZ 981), Dom Losses (KZ 891),
      Fgn Gains (KZ 994), Fgn Losses (KZ 892) as separate columns; per-year netting visible at a glance.
      6 new sheet-rendering tests (197 total). *(2026-05-08)*
- [x] **Meldefonds/ETF AE support (KZ 936/937)** *(2026-05-13)*
      `core/meldefonds.py` + `data/oekb_ae.yaml` (curated dataset). Seed ETFs: VWRL (A1JX52),
      VWCE (A2PKXG), VFEM (A1JX51), VFEA (A2PLTC), IWDA (A0RPWH). 17 tests → 235 total.
      AE/WA per share from OeKB "Steuerliche Mitteilung"; WA offsets KeSt (tracked separately from WHT).
      KZ 936 (AT ISIN) / KZ 937 (foreign). Shares inferred from transaction history (symbol + ISIN fallback).
      Excel "Meldefonds" tab auto-generated when positions configured.
      ⚠ Verify PLACEHOLDER AE/WA values on my.oekb.at before filing — especially VWRL 2024 WA.
- [ ] **OeKB data license inquiry** — email taxdata@oekb.at; open-source tool may qualify for free
      structured AE/WA feed; do before building v2.0 ETF automation.
- [ ] **Nichtmeldefonds detection** — OeKB lookup + punitive tax calculation
- [ ] **Regelbesteuerungsoption mode** — `--regelbesteuerung` flag, recalculates
      at progressive income tax rate instead of flat 27.5% KESt
      Very low priority: very few AT investors have marginal rate < 27.5%; N/A for Jessie 2025.
- [ ] **Options / Termingeschäfte (KZ 802)** — full support: separate FIFO queue, KZ 802 output,
      loss segregation (AT law: option losses cannot offset stock gains — separate loss bucket).
      Prerequisite: OPT rows warning (above). Complex — future session.
- [ ] **Bond / Anleihen income tracking** — Anleihen interest is KeSt 27.5% (same as dividends)
      but not yet broken out separately. Add to KZ 863 with "interest" source label. Popular
      among AT FIRE investors; distinct from dividend income in reporting.
- [ ] **Savings account interest** (Sparbuch/Festgeld) — manual config block `savings_accounts:`
      with `steuereinfach: true` and `net_interest_eur`. Steuereinfach = KeSt already deducted
      at source, no E1kv entry needed; net amount feeds Freedom dashboard net income.
- [ ] **Prior-year loss carryforward input** — allow user to specify prior-year unabsorbed losses
      via config (e.g. `loss_carryforward_dom_eur`, `loss_carryforward_fgn_eur`); deducted from
      current-year gains before KeSt. Note: AT standard KeSt has no carryforward (losses offset
      same-year gains only); Regelbesteuerung allows it. Higher priority for users with 2022-2024 losses.
- [x] **Nichtmeldefonds AE cost basis step-up on sale** *(2026-05-16, v0.3.4)*
      `compute_nmf_cumulative_ae()` in `nichtmeldefonds.py` sums prior-year AE per symbol
      (range(purchase_year, tax_year)). TaxEngine receives `nmf_ae_step_up` dict; injects
      AE proportionally by cost fraction into FIFO lot `cost_per_unit` before sell matching.
      Handles both SAXO qty=1 and real-qty IB lots. 12 new tests → 378 total.

---

## ~~🟡 ISIN-based auto-alias~~ ✅ Done (v0.3.1, 2026-05-15)

- [x] **Auto-resolve ticker renames via ISIN matching** — `_try_isin_auto_alias()` in `core/tax_engine.py`.
      Trigger: sell has no prior-dated lots under its own symbol (covers no-queue AND same-day-rebuy pattern).
      Rule: same ISIN → auto-alias silently. Different ISIN → still requires `symbol_aliases`.
      Qty plausibility + older-lot filter applied. VER→OEWA and NOV→NOVd entries removed from matthias config.
      `symbol_aliases` now only for corporate actions (different ISIN). 6 tests → 344 total.
      Future GUI hook: expose ambiguous/unresolved cases as "conflict cards" — deferred.

---

## 🔵 Usability & Automation

- [x] **Remove `VER: OEWA` alias** — no longer needed; ISIN auto-alias handles it. Removed 2026-05-15. *(v0.3.1)*
- [x] **`--input-dir` folder scanning** — `--input` already accepts directories; `_resolve_inputs()`
      uses `rglob` to scan recursively, auto-detects broker per file, loads all years for FIFO.
      11 tests added (191 total). *(2026-05-08)*
- [x] **IBKR Flex Web Service auto-fetch** — `--fetch-ibkr` / `--force-fetch-ibkr` flags *(2026-05-13)*
      Config: `ibkr_flex: {token, query_id}` in `users/{person}/secrets.local.yaml` (layer 4, gitignored).
      Two-step IBKR API (SendRequest → GetStatement); auto-retry on 1019; saves to
      `users/{person}/data/IB/{person}_ibkr_flex.csv`; pre-commit hook blocks token leaks.
      21 tests → 282 total.
- [x] **IBKR Open Positions parser + total-return FIRE + secrets layer** *(2026-05-14)*
      `brokers/ibkr_positions.py`: parses POST section (BOS/EOS, HEADER/DATA, Classic); uses mark prices
      directly — bypasses yfinance, solving European ticker issues (RENK, RHM, TKMS, …).
      FIRE model: `portfolio × (yield + growth)`; chart shows total-return + div-only lines.
      `secrets.local.yaml`: 4th config layer for credentials (gitignored; pre-commit scans all values ≥ 6 chars).
      `portfolio_eur_supplement`: SAXO manual add-on on top of IBKR auto-computed value.
      18 new tests → 300 total. Tagged v0.2.2.
- [ ] **Steuereinfach broker architecture** — add `kest_already_withheld: true` flag at broker/
      config level. Steuereinfach brokers (Trade Republic, AT banks) deduct KeSt at source →
      no E1kv entry, net amounts used directly in Freedom dashboard. Prerequisite for Trade Republic
      and Sparbuch/Festgeld parsers. Design in before adding those brokers.
- [ ] **Local web UI** — Flask/FastAPI + HTML; folder picker, pipeline progress, inline results,
      download buttons. One command to start. No CLI knowledge required. Priority: after core features.
- [ ] **FinanzOnline XML output** — machine-readable upload format for direct e-filing.
      Pair with filing guide (see Dashboard section above).
- [x] **Household view** *(2026-05-16, v0.3.5)* — `generators/household.py` + `--household` CLI flag.
      Reads per-person `summary.json`, freshness-checks (7-day threshold, legacy path fallback),
      writes `users/household/output/{year}/household_{year}_{persons}.xlsx`.

---

## 🔵 Portfolio Intelligence

- [x] **AT tax efficiency analyzer** *(2026-05-16, v0.3.3)* — `generators/tax_efficiency.py` + 13 tests (366 total).
      Section 1: per-NMF-symbol: annual KeSt, cumulative AE step-up, embedded P&L, KeSt credit if sold.
      Section 2: dividend frequency (monthly/quarterly/semi-annual/annual). Section 3: summary + action items.
      Auto-generates `{person}_{year}_tax_efficiency.txt` whenever NMF positions exist.
- [ ] **Nichtmeldefonds alternative suggestions** — when a position is flagged as Nichtmeldefonds,
      suggest OeKB-registered equivalents (e.g. European REIT ETF instead of US REIT). Requires
      a curated mapping file (nichtmeldefonds_isin → suggested_meldefonds_alternative). Start small.
- [ ] **Portfolio health scraper** — automated fetch of key metrics per holding: OeKB registration
      status (Meldefonds/Nichtmelde), dividend yield, domicile, WHT treaty rate. Uses OeKB public
      registry CSV + yfinance. Produces a per-holding "AT investor score" (tax drag, yield, simplicity).
      More complex: needs scraping + curation. Scope carefully before building.

---

## 🔵 v2.x — New Brokers

- [x] SAXO parser — `brokers/saxo_xlsx.py` (AggregatedAmounts + ShareDividends) + `brokers/saxo_closedpos_xlsx.py`
      (ClosedPositions, real quantities); `saxo_skip_agg_trades` + `saxo_skip_agg_dividends` flags; 166 tests *(2026-05-05)*
- [x] **E\*Trade PDF parser** (`brokers/etrade_pdf.py`) *(2026-05-14)*
      Two formats: old (2020-2021, E*TRADE Securities LLC) + new (2024+, Morgan Stanley).
      Parses sells, buys, RSU vestings (FMV cost basis from statement or yfinance), dividends + WHT.
      Account IDs extracted dynamically from PDF text (never hardcoded); added to config.local.yaml.
      pdfplumber dependency uncommented in requirements.txt. 26 tests → 326 total.
      `etrade_skip_transfers` config: suppresses account-migration "Transfer into Account" entries
      (e.g. Sep 1 2023 old→Morgan Stanley migration of 123.977 NXPI — not a fresh RSU vest).
      Standalone "Recap of Cash Management Activity" PDFs correctly skipped (no year header).
      2022 + 2023 statements obtained and in data/; NXPI FIFO chain complete 2020–2026.
- [ ] **Trade Republic parser** — widely used in AT; steuereinfach broker (KeSt deducted at source).
      Parse TR account statements/exports. High value for AT user base. Requires steuereinfach
      architecture flag (see Usability section above) as prerequisite.
- [ ] **Physical metals** (gold/silver) — AT §30 EStG: gains tax-free if held > 1 year.
      Add SELL transactions for metals with automatic KeSt-free flag based on FIFO holding period.
      Spot price for portfolio value via yfinance (gold/silver futures). Low complexity, high AT completeness.
- [ ] **SAXO Holdings parser** — eliminate `portfolio_eur_supplement` manual override; blocked on SAXO
      Holdings export sample from Matthias. Would make SAXO portfolio value automatic.
- [ ] **E\*Trade CSV parser** (`brokers/etrade_csv.py`) — parse `tradesdownload.csv` exports (currently
      skipped as unrecognised). Would eliminate reliance on iPhone-scanned PDFs for Morgan Stanley
      account statements; cleaner data source for dividends and RSU vests.
- [ ] **IB NAV Statement parser** — alternative route to portfolio value; lower priority than IBKR Open Positions (already solved via mark prices in POST section).
- [ ] REIT/BDC handling (US return of capital, §199A dividends, 1099-DIV boxes)
- [ ] **Crypto** — AT crypto tax: held >1yr was tax-free pre-Mar 2022; post-Mar 2022 taxed as
      capital income at 27.5% (same KZ as stocks). Complex rules, mixed lot treatment.
      Low-medium priority; high complexity. Future session.

---

- [x] **Freedom tab — per-symbol holdings table** *(2026-05-13)* — see 🟡 Dashboard section above.

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

- [x] **NMF share count fix — `shares_held_override`** *(2026-05-16)* — `core/nichtmeldefonds.py`.
      SAXO qty=1 convention caused _net_shares_at_year_end() to return 1 instead of real count.
      Added optional `shares_held_override: {year: count}` per nichtmeldefonds entry; falls back
      to transaction history when not set. Matthias 2024: 1 position (€1 KeSt) → 5 (€841).
      2025: €985 KeSt. KeSt remaining updated €3,268 → €4,252. 9 tests → 353 total. v0.3.2.
- [x] **FAQ docs** *(2026-05-16)* — `docs/faq-steuereinfach-brokers.md`, `docs/faq-meldefonds-etfs.md`,
      `docs/faq-nichtmeldefonds-reits.md`. Cover steuereinfach cross-broker Verlustausgleich value,
      accumulating ETF phantom income, dist vs acc comparison, NMF double-taxation, exit strategy.

- [x] **IBKR cash interest parser + Freedom net income** *(2026-05-15)* — `parse_ibkr_interest()` in `brokers/ib_csv.py`.
      Reads CTRN section (Cash Transactions) — already in standard Activity Flex Query, no new config needed.
      Deduplicates across multiple input files by `(currency, description)` key. Adds to KZ 863 / net_taxable.
      Freedom dashboard now shows post-tax net income: `(divs + interest) × 0.725 − excess_WHT`.
      New "Income After Tax" breakdown panel. 7 new tests → 342 total. Tagged v0.3.0.
- [x] **Output directory restructure** *(2026-05-15)* — `users/{person}/output/{year}/` (was flat).

- [x] **IBKR Cash Report parser** *(2026-05-15)* — `parse_ibkr_cash_report()` in `brokers/ib_csv.py`.
      Parses CRTT section (BOS/EOS + HEADER/DATA + Classic). Uses `BASE_SUMMARY` EndingCash (IB pre-converts
      to EUR). Adds to `portfolio_eur_computed`; shows as "IBKR Cash" position in Freedom dashboard.
      Re-normalises `portfolio_pct`. Fully optional — absent CRTT = no change to tax output.
      `summary.json` now also includes `portfolio_eur_computed`, `ibkr_cash_eur`, `dividend_yield_computed`,
      `portfolio_positions`. 7 tests → 335 total. Tagged v0.2.5.

- [x] **Per-user directory structure refactor** — `users/{person}/data/`, `users/{person}/output/`, `users/{person}/config.local.yaml`; `cache/fx_cache/`, `cache/price_cache/` shared; `generators/` package rename *(2026-05-05)*
      3-layer config merge (DEFAULTS → config.yaml → config.local.yaml); `account_id` scalar/list; scan_account_ids() auto-detection; `--input` optional; 14 new config tests
- [x] **SAXO AggregatedAmounts + ShareDividends double-counting fix** — `saxo_skip_agg_dividends: true` config knob; suppresses dividend rows from AA when SD loaded for same period *(2026-05-05)*
      Root cause: 114 duplicate dividends in 2025 (different raw_id formats evaded dedup). Matthias 2025 corrected.
- [x] **Matthias + Jessie user configs fully set up** — account_ids, nichtmeldefonds (O,EPR,OHI,WPC,ARCC), Jessie ANV checklist, 2020 SG file archived *(2026-05-05)*
- [x] Matthias end-to-end run — TT-AUT BOS/EOS parser, OPT filter, P911 RoC, DE 'd' normalization *(2026-05-04)*
      symbol_aliases for tender offers (1COV/1CO Covestro); VNA FIFO fix; all years 2021–2026
- [x] WHT reclaim assistant — `generators/wht_reclaim.py`; EUR 852.14 total reclaimable *(2026-05-04)*
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
