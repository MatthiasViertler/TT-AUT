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
