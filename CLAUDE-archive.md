# Kapitalertrag — Archive

Full historical context. Not needed in daily sessions — paste CLAUDE.md instead.

---

## How we built this (session history)

Built from scratch in a single Claude session. Key decisions:
- Python over VBA/Excel macros: portable, version-controllable, extensible
- Stateless design: no DB, no memory — pass all years' files together for FIFO
- ECB FX API: free, no key, daily rates back to 1999, cached as JSON per currency/year
- openpyxl for Excel: pure Python, no COM dependency, works on Linux

## Austrian tax law implemented

§ 27 EStG 1988 — Einkünfte aus Kapitalvermögen:
- KESt 27.5% on dividends, capital gains, interest (since 2016)
- FIFO for cost basis (§27 Abs. 4) — mandatory for foreign depots
- WHT crediting: min(actual_wht, treaty_rate × gross) — max 15% for most countries
- Loss offsetting within same category allowed
- Domestic = ISIN prefix AT or Vienna exchange (WBAG/XWBO)

WHT treaty rates (Austria DBA):
- US: 15%, DE: 15%, NL: 15%, CH: 15%, GB: 15%, DK: 15%, etc.
- DE actually withholds 25% → excess 10% must be reclaimed via BZSt (bzst.de)
- NL sometimes withholds >15% → reclaim via Belastingdienst

KZ 937 (Ausschüttungsgleiche Erträge): NOT implemented.
Requires OeKB fund data per ISIN. Must be entered manually from oekb.at.

## E1kv Kennziffern reference
| KZ  | Description                              |
|-----|------------------------------------------|
| 862 | Inländische Dividendenerträge            |
| 863 | Ausländische Dividendenerträge           |
| 981 | Inländische Kursgewinne                  |
| 994 | Ausländische Kursgewinne                 |
| 891 | Inländische Kursverluste                 |
| 892 | Ausländische Kursverluste                |
| 898 | Ausschüttungen (Ausland)                 |
| 937 | Ausschüttungsgleiche Erträge (Ausland)   |
| 899 | KESt für inländ. WP im Ausland           |
| 998 | Quellensteuer für ausländ. Dividenden    |

## IB Flex Query setup (exact field names)

### General
- Date Format: yyyy-MM-dd
- Date/Time Separator: semicolon (;)
- Include Header and Trailer Records: YES
- Include Column Headers: YES
- Include Section Code: YES
- Include Canceled Trades: NO

### Trades (TRNT) fields
Symbol, ISIN, Description, AssetClass, Buy/Sell, DateTime, TradeDate,
Quantity, TradePrice, Proceeds, IBCommission, IBCommissionCurrency,
CurrencyPrimary, Exchange, Conid, CostBasis, FifoPnlRealized,
Open/CloseIndicator

### Cash Transactions (CTRN) fields
Symbol, ISIN, Description, AssetClass, Date/Time, Amount, CurrencyPrimary,
Type, Conid, TransactionID

## Bugs fixed during development

1. FX cache returned strings not Decimals → fixed in `_load_cache()`
2. openpyxl Font/PatternFill imported inside function, used at module level → moved to top
3. IB exports duplicate rows with CostBasis ±1.00 → included CostBasis in raw_id
4. Date format `yyyy-MM-dd;HH:mm:ss` (semicolon) → normalise before parsing
5. Field name mismatches: Asset Category→AssetClass, T.Price→TradePrice, etc.
6. WHT warnings firing on rounding differences → threshold of €0.05 added
7. `--person` required even though account ID is in every file → now auto from account_map
8. .venv created one level up (~/tax/AUT/ instead of ~/tax/AUT/kapitalertrag/) → moved
9. **FIFO ghost-lot bug** (2026-05-06) — `_process_capital_gains` only received current-year sells.
   Prior-year sells left their lots unconsumed, so 2025 sells matched against "ghost" lots from
   prior years instead of the correct (later) purchases. Fix: pass all_sells to the function and
   process every year chronologically; use `year_sell_ids = {id(s) for s in year_sells}` to skip
   gain/loss accumulation for prior-year sells. Affected symbol: NVDA (prior-year 2024 transfer sell).
10. **Verbund AG ticker rename OEWA→VER** (2026-05-06) — IB renamed Verbund AG's ticker from OEWA to
    VER in December 2025. The 2025-12-17 loss-harvest sell (150 shares) was booked under VER, but all
    buy lots were under OEWA → sell matched same-day VER repurchase → -€15 instead of -€1,107 loss.
    Fix: added `VER: OEWA` to `symbol_aliases` in Matthias config.local.yaml.
    ⚠️ Alias must be removed before running 2026 tax year once all OEWA lots are consumed.

## FIFO diagnostic warnings (added 2026-05-06)

Two proactive warnings in `_process_capital_gains` to catch future ticker-rename / mismatch issues:

**ISIN rename hint**: when an unmatched sell has an ISIN that appears in the buy history under a
different symbol, the warning suggests the exact `symbol_aliases` entry: e.g.
`"ISIN AT0000746409 has lots under OEWA — possible broker ticker rename; add 'VER: OEWA' to symbol_aliases."`
Fires when there are NO lots at all for the sell symbol.

**Same-day round-trip**: if a sell has a same-day repurchase of the same symbol AND |gain| < 1% of
proceeds (threshold: > €500), warns that FIFO may have matched against the new buy. Fires when lots
exist but are from the same-day purchase (the scenario where the ticker rename bug manifests as
a tiny delta rather than zero lots).

## Project / machine setup

```
~/tax/AUT/kapitalertrag/    ← project root + git repo
  .venv/                    ← Python virtual environment
  data/                     ← broker exports (gitignored)
  data/fx_cache/            ← ECB rate cache (gitignored)
  output/                   ← generated files (gitignored)
  docs/                     ← Word documentation
```

Git remote: git@github.com:MatthiasViertler/TT-AUT.git (SSH)
VS Code workspace settings: python.defaultInterpreterPath + terminal PATH injection

## People / accounts tested
- jessie (U11111111): IBKR, 2024+2025+2026 exports, all years produce correct output
- self (Matthias): IBKR 2025 tested; multi-broker (SAXO, E*Trade) pending

---

## IB Flex Query format quirks

**TT-AUT export (BOS/EOS format)** — Matthias's exports (2021–2026):
- BOF col[1] = account ID; BOF col[5] = year-end date (fallback for CTRN rows with no DateTime)
- BOS/EOS markers wrap each section; row after BOS = plain header, rows after = plain data
- CTRN rows have NO Date/Time → grouped by (symbol, per_share_str, currency) and netted
- WHT amounts are negative in source; `wht_held = -sum(whts)` to get positive withheld amount
- Return of Capital detected via description substring "return of capital" → entire group skipped
- PER_SHARE_RE: `r'([A-Z]{3}\s+\d+(?:\.\d+)?\s+PER\s+SHARE)'`
- BAYN 2021 reversal/re-booking: netting resolves [70, −70, 70.01] → 70.01

**HEADER/DATA format** — Jessie's exports:
- BOF row col[1] = account ID
- Section codes: TRNT=Trades, CTRN=Cash Transactions
- Field names: CurrencyPrimary, DateTime, TradePrice, IBCommission, AssetClass
- Date format: `yyyy-MM-dd;HH:mm:ss`
- Type strings (CTRN): "Dividends", "Withholding Tax", "Broker Interest Received"
- Duplicate rows: same trade with CostBasis ±1.00 → deduped via raw_id
- FifoPnlRealized field present on TRNT SELL rows → used for FIFO cross-check

---

## Matthias's full symbol list (STK)
ALV, AIR, BAS, BAYN, BMW, FRE, GAZ, HEN3, HOT, IFX, KHC, LIN, LMT, IBKR, MC, MMM,
MUV2, NOV, OMV, P911, RIO1, RDSB, SAF, SHL, SIE, UNVB, VER, VOW3, AVGO, ABEC,
SOLV (3M spin-off, manual_cost_basis cost=0)
New 2025: HENSOLDT (DE000HAG0005), RENK (DE000RENK730), RHEINMETALL (DE0007030009),
TKMS (DE000TKMS001), 4SC (DE000A3E5C40), DRONESHIELD (AU000000DRO2), BLACKSKY (US09263B2079)

## Matthias's data files (not committed)
data/matthias_2021.csv through data/matthias_2026.csv — IBKR TT-AUT BOS/EOS exports
data/2024/2025/2026-AUT-TAX-Divi-Trades-Report.csv — Jessie IBKR HEADER/DATA exports
2020 intentionally excluded (IBKR UK/IE split year, nothing tax-relevant; FIFO starts 2021)

## Matthias's E1kv complexity (from consultant's Excel, screenshot 2026-05-02)
REITs/BDCs (Nichtmeldefonds), capital losses offsetting gains.
KZ fields not yet output: 864/865 (25% gains), 897 (fund distributions domestic),
982/993/893–896 (derivatives), 171/173/175 (crypto), 942 (Lichtenstein), 984/900/901.
