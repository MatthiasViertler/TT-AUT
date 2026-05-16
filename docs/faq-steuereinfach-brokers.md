# FAQ: Do I still need this tool if I use a steuereinfach broker?

> Applies to: Trade Republic (AT steuereinfach since 2025), Austrian banks (Sparbuch, Festgeld,
> Anleihen), and any other broker that deducts KeSt at source on your behalf.

---

## "My broker already deducts the tax — why would I file anything?"

You're right that a steuereinfach broker handles KeSt automatically. You are **not required** to
declare those transactions in your E1kv tax return.

But "not required" is not the same as "nothing to gain." There are four situations where including
your steuereinfach broker in this tool puts real money back in your pocket.

---

## 1. You have accounts at multiple brokers (cross-broker Verlustausgleich)

This is the most impactful case for serious investors.

Austrian tax law allows losses from one broker to offset gains from another — but **brokers can
only see their own accounts**. Trade Republic withholds KeSt on every gain it sees, with no
knowledge of losses you incurred at IBKR, SAXO, or any other broker.

**Example:**
- IBKR: €5,000 loss on stock sales
- Trade Republic: €4,000 gain, KeSt already withheld = €1,100

Without filing: you've paid €1,100 KeSt to TR and have €5,000 of losses sitting unused at IBKR.
With filing: the €4,000 TR gain is offset by €4,000 of your IBKR losses → **€1,100 KeSt refund**.

This tool calculates the exact cross-broker netting and tells you precisely how much to claim back.
Your steuereinfach broker's **Jahressteuerbescheinigung** (annual tax certificate) is the input —
no need to re-enter every transaction manually.

---

## 2. Foreign withholding tax (WHT) reclaims

When foreign companies pay you dividends, the source country withholds a portion before you receive
anything — often more than the tax treaty allows.

**Your steuereinfach broker does not file these reclaims for you.**

Examples:
- Germany withholds 26.375% on dividends; the Austria–Germany treaty caps it at 15%. The 11.375%
  excess is yours to reclaim from the Bundeszentralamt für Steuern (BZSt).
- France withholds 30%; treaty rate is 15%. Reclaim from Direction Générale des Finances Publiques.

This tool identifies every excess WHT payment per country and produces a ready-to-file reclaim
report with the exact amounts, deadlines, and relevant stock ISINs. Without it, this money is
simply lost — most investors never claim it.

---

## 3. A unified FIRE / financial independence dashboard

If you are working toward financial independence, knowing your total passive income across all
accounts matters more than knowing it per broker.

This tool combines dividends, interest, and capital gains from every broker you hold — steuereinfach
or not — into one picture:

- Total gross income across all accounts
- Total post-tax net income (what you actually keep)
- Portfolio value and implied yield
- FIRE projection: at your current savings rate and yield, when do you reach your target?

Trade Republic alone can show you your TR account. This tool shows you the complete picture.

---

## 4. Steuereinfach brokers assume worst-case — and over-withhold

A steuereinfach broker applies KeSt automatically but cannot know your full tax picture. This
means they often withhold **more than necessary**:

- **No cross-broker loss offset**: as described in point 1, the broker sees only its own
  account. Losses you hold at IBKR or SAXO do not reduce its withholding.

- **Conservative Meldefonds assumptions**: a steuereinfach broker applies KeSt at the statutory
  27.5% rate on the full distribution or AE figure. It may not apply the specific WA (Withhaltungsabzug)
  that would reduce your KeSt, because it relies on simplified OeKB data processing.

- **Foreign WHT over-withholding**: brokers apply the full foreign withholding regardless of
  whether you are entitled to a reduced treaty rate. They cannot apply a DBA exemption on your
  behalf — that is the investor's responsibility to reclaim.

- **No NMF step-up**: if you hold Nichtmeldefonds (US REITs, BDCs) and previously paid AE-based
  KeSt, that step-up to your Anschaffungskosten is never reflected in a steuereinfach broker's
  cost basis — so at exit they will withhold on a gain larger than your actual taxable gain.

The consequence is that every year you do not file an E1kv return, these excess withholdings are
simply lost. Filing recaptures them.

---

## 5. You already file E1kv for another broker anyway

If you hold even one non-steuereinfach account (IBKR, SAXO, E*Trade, etc.), you are already
required to file an E1kv return. In that case, excluding your Trade Republic account makes no
sense — it only costs you the cross-broker netting benefit described in point 1.

Adding your TR Jahressteuerbescheinigung to the tool takes minutes and ensures the return is
complete and optimised.

---

## Summary

| Situation | Benefit from this tool |
|-----------|----------------------|
| Losses at non-steuereinfach broker + TR gains | Reclaim over-withheld KeSt (cross-broker netting) |
| Foreign dividends via TR | Identify and file excess WHT reclaims |
| Multiple brokers | Single unified FIRE dashboard |
| Already filing E1kv for another broker | Complete the return correctly at no extra effort |
| Steuereinfach broker withholding too much | Correct overpayment via E1kv filing (NMF step-up, WA, cross-broker losses) |

Even if Trade Republic is your only broker and you had no losses and no foreign dividends in a
given year, this tool produces your FIRE projection and WHT report — at which point the filing
question becomes: is this year's Verlustausgleich worth submitting? The tool answers that question
for you.

---

## What do I need from Trade Republic?

- **For tax filing**: your annual **Jahressteuerbescheinigung** (tax certificate PDF, available
  in the TR app under Documents → Tax Documents). This summarises gains, losses, KeSt paid,
  and foreign WHT per asset class — no need to import raw transactions.
- **For the FIRE dashboard**: the transaction history CSV export gives richer detail (per-stock
  dividend breakdown, portfolio holdings). Available in the TR app under Settings → Export.

*Trade Republic parser support: coming soon. Upvote or watch the
[GitHub project](https://github.com/MatthiasViertler/TT-AUT) to get notified.*
