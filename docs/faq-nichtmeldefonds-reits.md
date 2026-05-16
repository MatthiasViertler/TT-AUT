# FAQ: US REITs and BDCs as Nichtmeldefonds — when do they work for AT investors?

> Applies to: any OeKB-unregistered investment fund held in a non-steuereinfach account.
> In practice: US REITs (O, EPR, OHI, WPC, VNQ, …), US BDCs (ARCC, MAIN, …), and most
> US/non-EU ETFs not registered with OeKB.

---

## Why are US REITs taxed as Nichtmeldefonds?

Austria's § 186 InvFG applies the Nichtmeldefonds treatment to any investment fund not registered
with OeKB — regardless of where it is listed. US REITs qualify as investment funds under Austrian
law, so even though they trade like stocks on NYSE, Austrian residents must apply the punitive
pauschal AE calculation in addition to standard dividend taxation.

---

## The double-taxation problem

This is the core issue. Holding a US REIT as an AT resident triggers **two separate tax charges**
in every calendar year you hold the position:

| Tax event | Base | Rate | When |
|---|---|---|---|
| Dividend income | Gross dividend received | 27.5% KeSt | When dividend is paid |
| Pauschal AE (§ 186 InvFG) | max(90% × annual price gain, **10% × Dec31 price**) | 27.5% KeSt | Year-end (E1kv) |

The dividend and AE are computed on **different bases** — dividends on cash received, AE on price
movement — so they do not cancel each other out. You owe both.

**Example (O, Realty Income, 150 shares, 2024):**
- Dividends received: ~$4.68/share × 150 = ~$702 → KeSt ~€148
- AE (10% minimum, price flat): $4.94/share × 150 = $741 → KeSt €196
- **Total KeSt: ~€344 — on a position that went nowhere in price**

A comparable OeKB-registered distributing ETF (e.g. a European REIT ETF) would pay tax only
on the OeKB-reported AE/WA, which encompasses all income in one calculation. No double charge.

---

## Can you recover the NMF tax burden when you sell?

Partially — but not fully. Here is the mechanism and the limits.

### The cost basis step-up (what protects you from double taxation at exit)

Each year's AE amount is added to your *steuerliche Anschaffungskosten* (tax cost basis). This
ensures you are not taxed again on the same phantom income when you eventually sell. If you paid
AE on $10/share over two years, your cost basis rises by $10/share, reducing the future capital gain.

### The recoverable portion — only if the position underperformed

**Embedded tax loss** = (adjusted cost basis) − (sale price)
where adjusted cost basis = original purchase price + cumulative AE paid to date.

If the position's price appreciation was less than the cumulative AE, you end up with an embedded
tax loss — a KeSt credit against same-year capital gains.

**Example (O, selling in 2026):**

| | Per share |
|---|---|
| Original purchase price (Dec 2023) | ~$54.67 |
| + AE step-up 2024 | +$4.94 |
| + AE step-up 2025 | +$5.54 |
| **Adjusted cost basis** | **~$65.15** |
| Dec 31 2025 price | $55.41 |
| **Embedded loss** | **~−$9.74/share** |

For 150 shares: ~−$1,461 loss → **~€311 KeSt credit** (at Dec 2025 FX, 27.5%).

### What cannot be recovered

The fraction of AE tax that corresponded to real price appreciation is fair tax — it is not
refunded. OHI (Omega Healthcare) rose from $25.68 → $43.06 in 2024–2025; its AE step-up
($15.64/share) was less than the actual gain ($17.38/share), so it remains above water. Selling
OHI would generate a taxable gain, not a credit.

### The Austria rule: same-year offsetting only

The loss from selling an underwater NMF position can **only offset same-year capital gains**.
There is no loss carryforward under standard KeSt. If you sell in a year with no other gains,
the loss credit is wasted. **This means the exit year matters enormously** — sell underwater
NMF positions in years when you have realised gains elsewhere to absorb the credit.

---

## When can US REITs (Nichtmeldefonds) still make sense for an AT investor?

They can work, but only under specific conditions — all of which must hold simultaneously:

### ✅ Condition 1: Yield premium large enough to outweigh the tax drag

The AE minimum (10% of year-end price per year) is a permanent, unavoidable annual overhead.
At a 10% AE minimum, the additional KeSt = 27.5% × 10% = **2.75% of position value per year**,
regardless of performance. To break even vs a Meldefonds alternative, the REIT must yield at
least 2.75% *more* after all other taxes than the alternative.

US REITs typically yield 4–8%, which sounds attractive. But once you subtract:
- 15% US WHT on dividends (non-recoverable for most AT residents without treaty filing)
- 27.5% AT KeSt on the net dividend
- 2.75% annual AE overhead (if the 10% minimum fires)

…the effective after-tax yield is often comparable to or below a Meldefonds ETF that is simpler
to hold and report.

### ✅ Condition 2: A clear exit strategy in a high-gain year

If you cannot plan the exit year, you risk selling in a low-gain year and losing the embedded
tax loss credit entirely. This requires active management, which defeats the passive-income
rationale for holding REITs in the first place.

### ✅ Condition 3: Strong expected price appreciation

If the REIT significantly outperforms (like OHI: +68% in 2 years), the AE tax is a small
fraction of a large gain — it is less painful. Flat or declining REITs combined with the 10%
minimum AE are the worst outcome: paying tax on phantom income while losing real value.

### ✅ Condition 4: You will definitely hold a non-steuereinfach account anyway

If you file E1kv for other reasons (IBKR, SAXO), the administrative overhead of adding NMF
calculations is marginal. If REITs were your only investment, the annual calculation burden
(OeKB lookup, AE computation, E1kv line) would be disproportionate.

---

## When are they clearly not worth it?

- **Flat or declining markets**: the 10% minimum fires regardless; you pay tax on value that
  does not exist.
- **No same-year gains to absorb the exit loss**: the embedded tax credit is wasted.
- **An OeKB-registered alternative exists with similar yield**: European REIT ETFs registered
  with OeKB (e.g. some iShares, Amundi, Xtrackers REIT ETFs) provide similar exposure with
  one unified AE/WA calculation and no double-taxation of dividends.
- **You want truly passive management**: NMF positions require annual manual lookup and
  E1kv reporting; Meldefonds with an automated tool (or steuereinfach via TR) do not.

---

## Why gross yield comparisons mislead — the full cost breakdown

The most common mistake when evaluating US REITs vs OeKB-registered alternatives is comparing
**gross yield** figures without accounting for all the layers of cost on each side.

### Step-by-step for US REITs (e.g. Realty Income at 6% gross, AT resident)

| Layer | Impact | Note |
|---|---|---|
| Gross dividend yield | +6.0% | Starting point |
| − US WHT on dividends (15%) | −0.9% | Withheld at source; partially creditable against AT KeSt |
| − AT KeSt on net dividend (27.5%) | −1.4% | On the post-WHT amount |
| − NMF pauschal AE KeSt (≈2% of position value) | −2.0% | 27.5% × 10% minimum × Dec31 price — even if price fell |
| **Effective after-all-taxes yield** | **≈1.7%** | What actually flows into your account |

### Step-by-step for an OeKB-registered world ETF (e.g. VHYL at 3.5% gross)

| Layer | Impact | Note |
|---|---|---|
| Gross dividend yield | +3.5% | |
| − TER (ongoing fund cost) | −0.22% | e.g. VHYL: 0.22%/yr; iShares EU REIT: 0.40% |
| − WHT at fund level (blended ~10%) | −0.35% | Fund recovers much of this via treaty; lower than REIT direct |
| − AT KeSt on distributions (27.5%) | −0.89% | Unified AE/WA calculation from OeKB |
| **Effective after-all-taxes yield** | **≈2.0%** | |

The ETF's 3.5% gross yield nets **more** than the REIT's 6% gross yield for an Austrian
resident, purely because the NMF overhead consumes nearly the entire yield premium.

### The TER comparison

| Alternative | TER | Cost on €50k | Net yield after TER |
|---|---|---|---|
| VHYL (Vanguard FTSE All-World High Div Yield) | 0.22% | €110/yr | ≈3.3% |
| iShares European Property Yield (IQQP) | 0.40% | €200/yr | ≈3.1% |
| STOXX Europe Select Dividend 30 (EXSB) | 0.30% | €150/yr | ≈4.2% |
| US REIT individual stocks | 0% TER | €0 | 6% gross → ≈1.7% net (AT) |

Individual stocks have zero TER — a real, compounding advantage. But the NMF overhead
erases it entirely while you are an Austrian tax resident.

---

## The decision framework: how long are you staying in Austria?

This is the single most important question, because the NMF overhead is entirely
Austria-specific. The moment you become a tax resident of Germany, Switzerland, the US,
or almost any other country, it disappears.

### Arguments for keeping US REITs despite the NMF overhead

**1. Country-move option value**
If there is any non-negligible probability you will leave Austria within 3–5 years, the
gross yield advantage (6% vs 3.5%) fully materialises the moment you move. Switching to
VHYL today and then moving abroad locks in the lower yield for your Austrian years, and
you can simply switch back after — but you lose the optionality. The option has real value
if your tenure in Austria is uncertain.

**2. No TER drag — ever**
Individual stocks have no ongoing management fee. The longer you hold, the more this
compounds. VHYL at 0.22%/yr is cheap as ETFs go, but €110/yr on €50k is €1,100 over
ten years before compounding.

**3. Monthly cash flow (structural rarity)**
Realty Income (O), ARCC, and similar US names pay monthly. This is genuinely rare for
OeKB-registered instruments — most ETFs pay quarterly. For a FIRE investor who wants
smooth monthly income without maintaining a cash buffer, monthly payers have utility that
quarterly ETFs don't replicate without active management.

**4. Individual position control**
With individual stocks you can make targeted decisions: sell the underwater ones for tax
credits, keep the outperformers, add on dips. An ETF packages everything together and
removes that optionality.

**5. The 10% minimum already fired — the damage is done**
For existing positions bought years ago, the past AE KeSt is a sunk cost. The forward
question is whether the remaining NMF drag justifies exiting *now* vs waiting.

### Arguments for switching to OeKB-registered alternatives

**1. After-all-costs math says switch (for long-term AT residents)**
As shown above, the effective net yield of a 6% REIT is approximately 1.7% after all
Austrian-specific costs. A 3.5% OeKB ETF nets approximately 2.0%. You earn more
*while* being an Austrian resident by switching.

**2. The 10% minimum fires on flat or declining assets**
This is the most painful scenario: prices go nowhere or fall, but you owe KeSt on 10%
of the Dec-31 price every year. Rising interest rates (which suppress REIT valuations)
combined with the 10% minimum AE create a double loss: paper losses plus phantom tax.

**3. No annual NMF calculation overhead**
Every year you hold NMF positions: fetch prices, compute AE, file E1kv KZ 937, track
cost basis step-up. Automating this (as this tool does) reduces but doesn't eliminate
the burden.

**4. High-dividend equity ETFs have their own problems**
Worth stating clearly: high-dividend equity ETFs are not a clean substitute. They tend
to overweight mature or declining industries (utilities, tobacco, telecoms, legacy banks)
that pay dividends *because* they cannot reinvest profitably. Over 10–15 year periods,
broad-market accumulating ETFs (VWCE) have significantly outperformed dividend-focused
indices in total return. If you are still in the accumulation phase, optimising for
dividend yield at the expense of total return is often a mistake.

### Recommended framework by situation

| Your situation | Recommendation |
|---|---|
| Likely leaving Austria within 2–3 years | Keep REITs. NMF overhead is temporary; gross yield advantage real. |
| Definite long-term AT resident, income-focused | Switch to OeKB Meldefonds. Net yield is higher; no AE overhead. |
| Definite long-term AT resident, accumulation phase | VWCE (accumulating, no distributions) + individual stocks opportunistically. Ignore dividend yield — focus on total return. |
| Uncertain; underwater positions (O/EPR/WPC) | Sell the underwater ones in a high-gain year to crystallise the credit; keep the above-water performer (OHI). Redeploy thoughtfully. |
| Mixed portfolio (some NMF, some Meldefonds, some stocks) | Reduce NMF to just positions you would hold anyway on fundamentals; let this tool track the rest. |

### The partial exit strategy

A full exit is not the only option. A targeted partial exit can:
1. Crystallise the embedded KeSt credit on underwater positions (O, EPR, WPC)
2. Keep outperformers or positions above water (OHI, ARCC)
3. Redeploy into OeKB-registered alternatives gradually (avoid deploying all at once into an expensive market)

The key constraint: the loss credit from selling underwater NMF positions **only offsets
same-year capital gains**. There is no AT carryforward under standard KeSt. Sell in a
year when you have at least as much in realised gains as the embedded loss.

---

## What are the AT-friendly alternatives for dividend / passive income?

| Alternative | Gross yield | TER | AT tax treatment | Admin burden |
|---|---|---|---|---|
| European REIT ETF, dist. (e.g. IQQP — if OeKB) | 3–4% | 0.40% | OeKB AE/WA single calculation | Low |
| Vanguard FTSE All-World High Div Yield, dist. (VHYL) | 3.5% | 0.22% | OeKB AE/WA | Low |
| iShares Core MSCI World (IWDA), dist. | 1.5–2% | 0.20% | OeKB AE/WA | Low |
| AT/EU individual stocks (Allianz, MunichRe, OMV, ENI) | 4–6% | 0% | KeSt via E1kv; treaty WHT (DE 25%→15%, IT 26%→15%) | Medium |
| AT-listed stocks via AT bank (steuereinfach) | 3–5% | 0% | KeSt deducted at source; no E1kv | Very low |
| Bond / Anleihen ETF (short duration, OeKB) | 3–5% (rising rate env.) | 0.10–0.20% | KeSt on interest (KZ 863); no AE complexity | Low |
| Cash / money market (IBKR interest) | 3–4% (rising rates) | 0% | KeSt on interest (KZ 863) | Very low |

**The income gap from exiting US REITs**: if O, EPR, WPC generated ~$2,400–3,000 USD gross
dividends annually (5–6% yield on ~$45k position), replacing them with VHYL at 3.5% on the
same capital produces ~$1,575 USD gross — but after NMF costs are removed, the effective
income is similar or slightly higher. The real gap only appears if you leave Austria.

One practical middle ground: check whether any European REIT ETF covering US real estate
is registered with OeKB. The exposure is similar, the tax treatment is Meldefonds (single AE/WA),
and the dividend flow is preserved — minus the punitive minimum AE overhead.

---

## Recovering past NMF overpayments — practical steps

1. **Identify the exit year**: sell underwater positions in a year with large realised gains
   elsewhere (the credit only helps in the same calendar year).
2. **Calculate the adjusted cost basis**: original purchase price + every year's AE step-up
   since purchase. This tool tracks AE per year in the Nichtmeldefonds tab of the dashboard.
3. **Run the tool for the exit year**: the FIFO engine will calculate the gain/loss against
   the adjusted cost basis (once the AE step-up feature is implemented — see TASKS.md).
4. **Include in E1kv**: the loss flows into KZ 892 (foreign losses) and offsets KZ 994
   (foreign gains) automatically.
5. **Do not sell in December and immediately repurchase**: the same-day round-trip detection
   in this tool will warn you; Austrian wash-sale equivalent rules apply.
