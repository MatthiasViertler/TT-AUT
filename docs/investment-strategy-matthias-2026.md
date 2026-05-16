# Investment Strategy — Matthias, 2026

> Personal tracking document. This is not financial advice.
> Updated: 2026-05-16. Review when market conditions materially change.

---

## Context snapshot

| Item | Detail |
|------|--------|
| Goal | FIRE portfolio — still accumulation phase; cash flow not required yet |
| Tax regime | Austrian resident; non-steuereinfach (E1kv) |
| Key constraint | Nichtmeldefonds (§ 186 InvFG) punishes US REITs/BDCs with ~2.75%/yr AE overhead |
| Brokers | IBKR (primary, auto-reported) + SAXO DK (NMF positions) |
| Idle cash | ~€20k SAXO + IBKR cash (see `summary.ibkr_cash_eur` in latest run) |
| Market view | Expensive across most equity classes (2026); rate outlook uncertain due to Middle East tensions (Iran war risk) → inflation pressure → higher rates than pre-2022 baseline |
| Country-move | Not ruled out; optionality has real value in REIT hold-vs-sell decision |

---

## Current NMF positions (decision status)

| Symbol | Type | Status | Action |
|--------|------|--------|--------|
| O (Realty Income) | REIT | Underwater — 10% AE min fires annually | **Sell candidate** — crystallize KeSt credit |
| EPR (EPR Properties) | REIT | Likely underwater | **Sell candidate** |
| WPC (W.P. Carey) | REIT | Likely underwater | **Sell candidate** |
| OHI (Omega Healthcare) | REIT | Above water (+68% in 2 years) | **Keep** — no embedded loss; strong total return |
| ARCC (Ares Capital) | BDC | Assess: check embedded P&L in tax_efficiency.txt | **Tentatively keep** — BDC; different thesis from REITs |

**Why sell O/EPR/WPC:** After all AT-specific costs (US WHT 15% + AT KeSt on dividend 27.5% + 10% AE minimum 2.75%/yr), effective net yield is ~1.7%. A VHYL ETF at 3.5% gross nets ~2.0% for an Austrian resident. The yield premium of holding individual US REITs is eliminated by the NMF overhead.

**Why keep OHI:** Already above water — selling generates a taxable gain, not a credit. Total return has been strong. AE overhead is proportionally smaller against a large gain.

**When to sell O/EPR/WPC:** Only in a year with sufficient realized capital gains elsewhere to absorb the embedded KeSt credit (same-year Verlustausgleich only — no carryforward under AT standard KeSt). Check `_tax_efficiency.txt` for current credit estimates per symbol.

**Before selling:** The NMF AE cost basis step-up fix must be implemented (see TASKS.md) — without it, the FIFO engine will overstate the taxable gain / understate the credit. Planned for the next coding session.

---

## After-all-costs yield comparison (at-a-glance)

| Instrument | Gross yield | After AT costs (approx) | Notes |
|------------|------------|--------------------------|-------|
| US REIT individual (e.g. O) | 5–7% | ~1.7% | US WHT 15% + AT KeSt on div + NMF AE 2.75%/yr |
| VHYL (Vanguard FTSE All-World High Div) | 3.5% | ~2.0% | TER 0.22%; blended WHT at fund level; OeKB AE single calculation |
| European REIT ETF (e.g. IQQP) | 3–4% | ~2.2% | TER 0.40%; OeKB Meldefonds |
| AT/DE individual dividend stocks (e.g. Allianz, MunichRe) | 4–6% | ~3.0% | DE WHT 26.4% → 15% treaty (11.4% reclaimable); no AE overhead |
| ENI, TotalEnergies | 5–7% | ~3.5% | IT/FR WHT treaty; better net yield; reclaimable excess WHT |
| Cash / IBKR interest (EUR) | 3–4% | ~2.9% | KZ 863; simple; zero duration risk |

**Key insight:** For long-term Austrian residents, individual AT/DE/IT dividend stocks net more than US REITs. The NMF tax overhead erases the yield premium entirely. Cash at 3–4% gross currently beats US REITs after AT costs.

**Country-move optionality:** If you leave Austria (Germany, Switzerland, US), the NMF tax disappears. The 5–7% gross yield on O/OHI/ARCC fully materializes. Selling now locks in the lower-yield alternative for your Austrian years. If departure is plausible within 2–3 years, holding NMF positions has option value.

---

## Existing holdings (do not ignore these in redeployment)

### Already held — no action needed (assess position sizes)

| Symbol | Type | Quality | AT tax treatment | Note |
|--------|------|---------|-----------------|------|
| Allianz (ALV.DE) | Insurance | High quality, consistent dividend grower | E1kv; DE WHT 25%→15% treaty (reclaimable excess) | Core holding; no action |
| Munich Re (MUV2.DE) | Reinsurance | Top tier; Buffett-adjacent quality | Same as above | Core holding; no action |
| OMV (OMV.VI) | Energy | Austrian; AT domicile = KZ 891/862 | Steuereinfach-friendly; domestic | AT-domiciled; no WHT complexity |
| Verbund (OEWA/VER.VI) | Utilities | AT renewable energy | Domestic | AT-domiciled |
| Rio Tinto (RIO) | Mining | High dividend; cyclical; UK-listed | BE WHT 30%→15%? Check treaty | Commodities exposure; high yield when prices strong |
| BASF (BAS.DE) | Chemicals | Value trap risk; restructuring 2024-2026 | DE WHT reclaim applies | Currently undergoing cost-cut transformation; watch closely |

### Holdings to watch (not owned yet, but on radar)

| Symbol | Thesis | AT tax treatment | Current valuation caution |
|--------|--------|-----------------|--------------------------|
| ERSTE Group (EBS.VI) | AT/CEE banking; domestic | Domestic; no E1kv complexity | Attractive but cyclical; banking regulation risk |
| ENI (ENI.MI) | Italian oil major; high yield 6%+ | IT WHT 26%→15% (some reclaimable via Cerfa) | Good value; energy geopolitics tailwind |
| TotalEnergies (TTE.PA) | French integrated energy | FR WHT 30%→15% (reclaimable, see WHT reclaim report) | Good fundamentals; geopolitical tailwind |
| Novo Nordisk (NOVd.DE) | GLP-1/Ozempic; strong moat | DK WHT 27%→15% (reclaimable via SKAT) | Expensive; re-entry after pullback |

---

## Redeployment strategy — if exiting O/EPR/WPC

### Phase 1: Crystallize the tax credits (do this first)
- **Prerequisite**: implement NMF AE cost basis step-up in FIFO engine (next coding session)
- **Timing**: sell O/EPR/WPC in a year where realized capital gains (from other sells) ≥ embedded NMF loss
  - Otherwise the credit is wasted — no AT carryforward
- **Target**: run `_tax_efficiency.txt` to get current KeSt credit estimates per position
- Keep OHI (above water, good total return)
- Tentatively keep ARCC (BDC thesis different from REIT thesis; review separately)

### Phase 2: Idle cash deployment (€20k SAXO + IBKR cash)
Don't rush into an expensive market. Stagger deployment over 3–6 months.

**Option A — Core ETF position (simplest, lowest admin)**
- VHYL (IE00B8GKDB10) or similar OeKB-registered world high-dividend distributing ETF
- 3.5% gross → ~2.0% net after AT costs; single OeKB AE/WA calculation; no annual NMF lookup
- Good for: "set and forget" redeployment of REIT proceeds with Meldefonds simplicity

**Option B — Individual stocks (more control, better tax treatment)**
- Concentrate in AT/DE/IT names with reclaimable WHT and no NMF overhead
- Add positions in ENI or TotalEnergies when energy dips (Iran conflict premium may fade)
- Avoid adding more names from high-WHT countries where the treaty reclaim process is burdensome

**Option C — Short-duration bond ETF / money market (defensive in uncertain market)**
- IBKR currently paying 3–4% on EUR cash (KZ 863; simple; no duration risk)
- Short-dated EUR government bond ETF (e.g. Lyxor EUR 1–3Y, if OeKB-registered)
- Appropriate if equity valuations still feel stretched; interest income taxed simply as KZ 863

**Recommended blend (conservative 2026 environment):**
- 30–40% VHYL or equivalent (establish baseline world diversification)
- 30–40% individual AT/DE/IT dividend stocks (ENI, TotalEnergies — energy tailwind; ERSTE if valuation resets)
- 20–30% keep in cash/IBKR interest until equity markets offer better entry points

### Phase 3: Improve dividend payment frequency (medium-term)
Current portfolio is overweight annual payers (most European stocks pay once/year).
Check `_tax_efficiency.txt` Section 2 (Dividend Payment Frequency) for current breakdown.

To improve cash flow smoothing without chasing monthly payers at premium valuation:
- Stagger DE/AT stock buys across stocks with different payment months (ALV pays May, MUV2 pays May, OMV pays Apr — add ENI/TTE which pay ~May/Jun for similar timing)
- VHYL pays quarterly (March, June, September, December) — adds quarterly baseline
- If monthly income becomes important later: ARCC and OHI already in portfolio; consider adding after country-move decision is made

### Phase 4: BASF — watch list
BASF is undergoing deep cost restructuring. Dividend was cut. Thesis: cheap European chemicals if restructuring succeeds by 2026–2027.
- Do not add meaningfully at current prices until Q2/Q3 2026 restructuring update
- Tax treatment: DE WHT reclaim applies (same BZSt channel as existing DE stocks)
- Size position conservatively; this is a value/recovery bet, not a yield play

### Phase 5: Rio Tinto — assess sizing
Rio Tinto is a high-yield cyclical (5–7% yield when metals strong). Current holding:
- Copper exposure → EV transition tailwind (structural demand)
- Iron ore exposure → China growth dependency (risk)
- UK-domiciled: check WHT treaty (AT–UK, post-Brexit); may have complex WHT treatment
- For FIRE purposes: high average yield but volatile; don't size up unless metals thesis remains intact

---

## Summary decision table

| Asset | Action | When | Why |
|-------|--------|------|-----|
| O, EPR, WPC | Sell (crystallize credit) | Year with ≥ same-size cap gains | NMF overhead kills net yield |
| OHI | Hold | Until above-water gains are taken | Still compounding; good total return |
| ARCC | Hold | Review after O/EPR/WPC exit | Different BDC thesis; re-evaluate separately |
| €20k SAXO cash | Deploy gradually | Q2–Q4 2026 | Stagger: VHYL + energy names + keep buffer |
| IBKR cash | Keep 50% in EUR interest | Ongoing | 3–4% gross = ~2.9% net; beats US REITs after AT costs |
| BASF | Watch (don't add) | After Q3 2026 restructuring update | Cheap but uncertain; wait for confirmation |
| Rio Tinto | Hold at current size | Ongoing | Cyclical; don't concentrate; review WHT treatment |
| ENI / TotalEnergies | Add on weakness | Energy market dips | Better net AT yield than US REITs; reclaimable WHT |
| ERSTE | Watchlist | If P/E resets to 6–7× | Austrian banking; domestic = no WHT complexity |
| Allianz, Munich Re | Hold | Core; no action | Quality; WHT reclaim already in pipeline |

---

## AT tax admin impact of strategy

| Move | Admin consequence |
|------|-----------------|
| Sell O/EPR/WPC | One-time FIFO exit (once AE step-up fix in place). KeSt credit absorbed same year. |
| Buy VHYL | Add to `meldefonds:` config; verify OeKB AE/WA annually; low burden |
| Buy ENI/TTE | Standard E1kv dividends; file WHT reclaim (IT/FR process already set up) |
| Keep IBKR cash | Already captured as KZ 863 in pipeline — zero extra work |
| Keep OHI/ARCC | Annual NMF lookup already automated by tool |
