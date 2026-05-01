# Kapitalertrag

Austrian capital gains tax calculator. Parses broker exports, applies KeSt rules (FIFO, WHT crediting, domestic/foreign classification), and produces ready-to-file E1kv Kennziffern plus an Excel dashboard.

> **Personal tool** — built for Austrian tax residents with Interactive Brokers accounts. Contributions welcome, but no guarantees. Always verify output against your broker statements and consult a tax advisor for edge cases.

---

## What it produces

For each run (`--person`, `--year`):

| File | Contents |
|------|----------|
| `output/{person}_{year}_tax_summary.txt` | E1kv Kennziffern (KZ 898, 937, etc.) ready for FinanzOnline |
| `output/{person}_{year}_transactions.csv` | Full transaction log with FX rates, cost basis, gain/loss |
| `output/{person}_{year}_dashboard.xlsx` | 4-tab Excel workbook (summary, trades, dividends, WHT) |

FX rates are fetched from the ECB and cached locally — no API key needed.

---

## Supported brokers

| Broker | Status |
|--------|--------|
| Interactive Brokers (Flex Query CSV) | ✓ supported |
| SAXO | planned |
| E*Trade | planned |

---

## Setup

**Requirements:** Python 3.11+

```bash
git clone https://github.com/MatthiasViertler/TT-AUT.git
cd TT-AUT
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**Configure your account:**

Edit `config.yaml` and add your IBKR account ID to `account_map`:

```yaml
account_map:
  U11111111: Jessie      # find your account ID in the BOF row of any Flex Query export
  U99999999: YourName
```

---

## Getting an IB Flex Query export

In Client Portal / TWS:

1. **Reports → Flex Queries → Create**
2. Select **Activity Flex Query**
3. Include sections: **Trades**, **Cash Transactions**
4. Date range: full calendar year(s) you want to calculate
5. Format: **CSV**
6. Run query and save the file to `data/`

For multi-year FIFO accuracy, always pass **all years from your first trade** onward — cost basis is recalculated from scratch each run.

---

## Usage

```bash
# Single year
python main.py --input data/2025.csv --year 2025

# Multi-year (required for correct FIFO if you bought before the tax year)
python main.py --input data/2023.csv data/2024.csv data/2025.csv --year 2025

# Explicit person label (overrides account_map lookup)
python main.py --input data/2025.csv --year 2025 --person matthias

# Offline mode (use cached FX rates only)
python main.py --input data/2025.csv --year 2025 --no-fx-fetch
```

All options:

```
--input FILE [FILE ...]   broker export file(s); multiple files are merged
--year INT                tax year to calculate
--person NAME             output label; default: auto-detected from account_map
--broker auto|ib|...      force a specific parser (default: auto-detect)
--config FILE             config file path (default: config.yaml)
--output-dir DIR          output directory (default: ./output)
--no-fx-fetch             skip ECB rate fetch, use disk cache only
```

---

## Key tax rules implemented

- **FIFO** cost basis matching across all input files
- **KeSt rate:** 27.5% flat (§ 27a EStG)
- **WHT crediting:** up to 15% treaty rate offset against Austrian KeSt
- **Domestic classification:** ISIN prefix `AT` or exchange `WBAG`/`XWBO`
- **WHT excess warning** when foreign withholding exceeds the creditable amount (> €0.05 threshold to suppress rounding noise)
- **KZ 937** (Ausschüttungsgleiche Erträge for accumulating funds) is **not** auto-calculated — requires OeKB data; the tax summary flags this for manual entry

---

## Disclaimer

This tool is provided as-is for personal use. Output should be verified against your broker statements. Tax law changes frequently — KeSt rules, treaty rates, and OeKB reporting requirements may differ from what is implemented here. The authors are not liable for errors in tax filings made using this tool.
