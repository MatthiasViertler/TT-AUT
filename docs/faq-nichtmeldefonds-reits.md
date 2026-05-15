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

## What are the AT-friendly alternatives for dividend / passive income?

| Alternative | Yield range | Tax treatment | Admin burden |
|---|---|---|---|
| European REIT ETF (OeKB-registered, distributing) | 2–4% | Single OeKB AE/WA; KeSt on distributions | Low (OeKB automated) |
| European high-dividend equity ETF (OeKB-registered) | 2–4% | Same as above | Low |
| AT-listed individual stocks (Erste, OMV, Verbund, Telekom) | 3–5% | Steuereinfach if via AT bank; domestic KeSt | Very low |
| European individual stocks (BMW, Allianz, Nestlé, etc.) | 3–5% | KeSt via E1kv; treaty WHT rates apply | Medium |
| Bonds / Anleihen | 3–5% currently | KeSt on interest (KZ 863); no AE complexity | Low–medium |
| Distributing US ETF (if OeKB-registered) | 1.5–3% | OeKB AE/WA, no double charge | Low |

**The income gap from exiting US REITs**: if O, EPR, OHI, WPC generated ~$3,000–4,000 USD gross
dividends annually (5–7% yield on ~$55k position), replacing them with a European dividend ETF
at 3% yield on the same capital produces ~$1,600–2,000 USD — roughly half. To maintain the same
gross income, you either accept a higher allocation to equities or seek higher-yielding European
alternatives (e.g. European infrastructure, utilities, or individual high-yielders).

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
