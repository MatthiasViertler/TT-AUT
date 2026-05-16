# Session Handoff — 2026-05-16

## What was done

- **OPT rows warning** (`brokers/ib_csv.py`)
  - `log.info` → visible `print` with `[warn]` prefix when IBKR options trades are skipped.
  - Message: `IB: N OPT row(s) skipped in {file} — derivatives KZ (982/993) not yet implemented`

- **Multi-year dividend trend chart** (`generators/writer.py`)
  - Added openpyxl `BarChart` to the Overview tab (`_fill_overview_sheet`).
  - Shows "Dividend Income by Year" as a vertical column chart below the existing table.
  - Only rendered when 2+ years of history exist (guard: `if len(history) >= 2`).

- **Household combined report** (`generators/household.py` + `main.py`)
  - New `--household matthias,jessie --year 2025` CLI mode (short-circuits normal pipeline).
  - Freshness check: warns if any person's `summary.json` is >7 days old; errors if missing.
  - Handles both new `output/{year}/` and legacy `output/` path layouts (Jessie pre-v0.3.0).
  - Writes `users/household/output/{year}/household_{year}_{persons}.xlsx` with side-by-side
    KeSt, dividends, gains/losses, net taxable, portfolio, dividend yield + combined totals column.
  - Combined 2025 figures: KeSt remaining **€4,296.31** | portfolio **€402,878** | yield **3.13%**

## Current state

- Tests: **378 passed**, 0 failed
- Key figures (Matthias 2025): KZ 863 €11,340.73 | KZ 891 €1,107 | KZ 994 €9,292 | KZ 892 €4,735 | NMF KeSt €985 | KeSt remaining **€4,251.72** — unchanged
- Household 2025: Matthias €4,251.72 + Jessie €44.59 = **€4,296.31** combined KeSt remaining
- Known issues / open warnings:
  - OeKB AE/WA PLACEHOLDER values in `data/oekb_ae.yaml` for some funds — verify on my.oekb.at before filing Meldefonds KZ 937.

## Next session priorities

1. **WHT reclaim paper filings** (user action, not coding):
   - France deadline **2026-12-31** — Cerfa n°12816 (Formulaire 5000+5001), MC + SAF, €12.06 excess.
   - Germany — BZSt portal, €775.00 excess.
   - Denmark — SKAT, €37.91 excess.
2. **SAXO Holdings parser** — blocked on Holdings xlsx export sample from user.
3. **E*Trade CSV parser** (`brokers/etrade_csv.py`) — `tradesdownload.csv` format.
4. **OeKB data license inquiry** — email taxdata@oekb.at.

## Blockers

- SAXO Holdings parser needs a Holdings xlsx export sample from Matthias.
- No coding blockers.
