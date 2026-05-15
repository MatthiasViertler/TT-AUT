# FAQ: Accumulating ETFs (Meldefonds) and the phantom income tax

> Applies to: any OeKB-registered accumulating fund held in a non-steuereinfach account
> (IBKR, SAXO, E*Trade, etc.). Examples: VWRL, VWCE, IWDA, VFEM, VFEA and most
> Vanguard/iShares/Xtrackers ETFs listed on Euronext or XETRA.

---

## What is the "phantom income tax" on accumulating ETFs?

Accumulating ETFs reinvest dividends internally — you receive no cash distribution. Under Austrian
tax law (§ 186 InvFG), OeKB-registered funds must nonetheless report a notional annual income
figure called **Ausschüttungsgleiche Erträge (AE)**: the income the fund *would have distributed*
if it had paid out its dividends and interest.

You owe KeSt (27.5%) on this AE **every year**, even though you received no cash. This is the
"phantom income" effect: a real tax bill on a number you cannot spend.

**Example (VWCE, approximate):**
- You hold 100 shares of VWCE at year-end
- OeKB reports AE = €3.20/share for 2024
- Notional income = 100 × €3.20 = €320
- KeSt due = €320 × 27.5% = **€88 — payable in April, whether or not you sold anything**

OeKB also reports a **Werbungskosten-Anteil (WA)** — a notional cost deduction that partially
offsets the KeSt due. The net KeSt after WA is typically lower than the gross 27.5%.

---

## Why do some investors avoid accumulating ETFs in Austria?

The combination of:
1. Annual phantom income tax (cash outflow with no corresponding cash inflow from the fund)
2. Manual lookup burden (AE/WA figures must be retrieved from my.oekb.at each year)
3. Risk of forgetting → underpayment penalty

…makes accumulating ETFs administratively burdensome compared to distributing ETFs or individual
dividend stocks, where the tax only arises when cash is actually received.

Many Austrian FIRE investors therefore prefer:
- **Distributing ETFs** (same KeSt, but at least you received the cash to pay it)
- **Individual dividend stocks** (clear cash → tax timing)
- **Nichtmeldefonds** (punitive pauschal treatment, but simpler record-keeping for some portfolios)

This is a personal tax-efficiency choice, not a legal restriction. Accumulating ETFs are perfectly
legal — they just require discipline and correct annual reporting.

---

## How does this tool handle it?

**Automatic AE/WA calculation** for any ISIN configured in your `meldefonds:` config block.
You provide the ISIN and symbol; the tool looks up the AE/WA figures from its curated dataset
and calculates:

- KeSt due on AE (KZ 937 for foreign funds, KZ 936 for AT-domiciled funds)
- WA credit (offsets KeSt, tracked separately from foreign WHT)
- Net KeSt remaining after WA

Results appear in the **E1kv summary**, the **Excel Meldefonds tab**, and the
**transactions CSV** alongside your other income.

```yaml
# In users/{person}/config.local.yaml
meldefonds:
  - isin: IE00B3RBWM25   # VWRL
    symbol: VWRL
  - isin: IE00BD4TXV59   # VWCE
    symbol: VWCE
```

No manual lookup, no separate spreadsheet. Run the tool → get the correct KZ figures.

---

## Current limitations

- **AE/WA dataset** (`data/oekb_ae.yaml`) is manually curated. Currently includes seed data
  for: VWRL, VWCE, VFEM, VFEA, IWDA. ISINs not in the dataset produce a PLACEHOLDER warning
  and zero AE — **you must verify on [my.oekb.at](https://my.oekb.at) before filing.**
- **Future**: automated OeKB data feed (pending data license from taxdata@oekb.at) will extend
  coverage to all registered funds with no manual steps required.

---

## I see a ⚠ PLACEHOLDER warning — what do I do?

1. Go to [my.oekb.at](https://my.oekb.at) → Fonds → search by ISIN
2. Find the **Steuerliche Mitteilung** for the relevant year
3. Note the **Ausschüttungsgleiche Erträge (AE) per Anteil** and **Werbungskosten-Anteil (WA) per Anteil**
4. Enter them in `data/oekb_ae.yaml`:

```yaml
IE00BD4TXV59:   # VWCE
  name: "Vanguard FTSE All-World UCITS ETF (Acc)"
  years:
    2024:
      ae_per_share: 3.20     # from OeKB Steuerliche Mitteilung
      wa_per_share: 0.18     # from OeKB Steuerliche Mitteilung
      currency: EUR
```

5. Re-run the tool — the PLACEHOLDER warning disappears and KZ 937 is populated correctly.

---

## Distributing vs. accumulating ETFs — AT tax comparison

Both types are taxed at **27.5% KeSt** on the same income base. The difference is timing,
cash flow, and administrative effort — not the total tax owed over the holding period.

| | Distributing ETF | Accumulating ETF (Meldefonds) |
|---|---|---|
| **When is income taxed?** | When the distribution is paid out | Annually, on the notional AE figure — even without cash distribution |
| **Cash available to pay the tax?** | Yes — you received the distribution | No — you must fund the KeSt from other sources |
| **What triggers the tax?** | Each distribution event | End of each calendar year (OeKB reporting date) |
| **KZ in E1kv** | KZ 863 (foreign) / KZ 862 (domestic) | KZ 937 (foreign fund) / KZ 936 (AT-domiciled fund) |
| **Annual admin burden** | Low — amounts come from broker statements | Medium — AE/WA must be looked up on my.oekb.at per fund per year |
| **Compounding effect** | Slightly lower — dividends leave the fund before being reinvested | Slightly higher — full gross amount reinvested before tax is paid |
| **Capital gains on sale** | KeSt on (sale price − cost basis); cost basis unchanged by distributions | KeSt on (sale price − cost basis); **cost basis increases by AE paid** each year, reducing future gain |
| **Total lifetime tax** | Identical — same income, same rate, different timing | Identical — AE payments reduce the eventual capital gain by the same amount |
| **Steuereinfach broker eligible?** | Yes (TR, AT banks deduct at source) | Yes for distributions; AE still requires E1kv filing for non-steuereinfach accounts |
| **Foreign WHT reclaim possible?** | Yes — on WHT excess per country | Yes — OeKB Steuerliche Mitteilung includes foreign WHT component |

### The key insight: total tax is the same

Accumulating ETFs do not save tax — they defer the *distribution* component while collecting the
phantom AE tax annually. The cost basis step-up (AE paid each year reduces the eventual capital
gain) ensures you are not taxed twice. Over a long holding period, the total KeSt paid converges
to the same amount as for a distributing ETF with the same underlying.

The real trade-off is:

- **Distributing**: tax paid from cash you received → no out-of-pocket surprise; slightly less
  compounding because dividends leave the fund
- **Accumulating**: maximum compounding; but you owe KeSt each April from your own pocket, and
  you must track AE/WA figures manually until automated OeKB feeds are available

### What this tool does for each type

| | Distributing | Accumulating |
|---|---|---|
| Parses dividend income | ✅ All supported brokers | ✅ (distributions, if any) |
| Calculates AE phantom income | N/A | ✅ from `data/oekb_ae.yaml` |
| WA cost offset | N/A | ✅ tracked separately |
| Correct KZ output | KZ 862/863 | KZ 936/937 |
| Foreign WHT reclaim report | ✅ | ✅ |
| Cost basis step-up on sale | N/A | ✅ AE paid reduces taxable gain |

## Should I switch to accumulating ETFs?

This tool does not give investment advice. But it does remove the *administrative* barrier:
once your AE/WA figures are in the dataset (or once the automated OeKB feed is live), the annual
phantom income calculation is fully automatic. The only remaining consideration is the cash-flow
timing — you pay KeSt each April without having received a distribution.

If you hold both distributing and accumulating ETFs, this tool handles both in the same run and
produces a single combined E1kv figure.
