"""Tests for brokers/ibkr_positions.py."""

import textwrap
from decimal import Decimal
from pathlib import Path

import pytest

from brokers.ibkr_positions import parse_ibkr_positions, _read_open_positions_section


# ── CSV helpers ────────────────────────────────────────────────────────────────

def _write(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "positions.csv"
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


# ── HEADER/DATA format fixtures ────────────────────────────────────────────────

HEADER_DATA_CSV = """\
BOF,U22222222,ACTIVITY,20251231,20251231,20251231
HEADER,Open Positions,ClientAccountID,AccountAlias,Model,CurrencyPrimary,AssetClass,SubCategory,Symbol,Description,Conid,SecurityID,SecurityIDType,CUSIP,ISIN,ListingExchange,UnderlyingConid,UnderlyingSymbol,Issuer,ReportDate,Position,MarkPrice,PositionValue,OpenPrice,CostBasisPrice,CostBasisMoney,PercentOfNAV,FifoPnlUnrealized,Side,LevelOfDetail,OpenDateTime,HoldingPeriodDateTime,Code,OriginatingOrderID,OriginatingTransactionID,AccruedInt
DATA,Open Positions,U22222222,,,"USD","STK","Common Stock","AAPL","APPLE INC",265598,"AAPL","TICKER","37833100","US0378331005","NASDAQ",,,,"20251231","100","245.50","24550","220.0","220.0","22000","5.00","2550","Long","SECURITY","","","","0","0","0"
DATA,Open Positions,U22222222,,,"EUR","STK","Common Stock","RHM","RHEINMETALL AG",123456,"RHM","TICKER","","DE0007030009","XETRA",,,,"20251231","50","720.00","36000","600.0","600.0","30000","3.00","6000","Long","SECURITY","","","","0","0","0"
DATA,Open Positions,U22222222,,,"USD","STK","Common Stock","TOTAL","CURRENCY TOTAL",0,"","","","","",,,,"20251231","","","60550","","","","","","","CURRENCY","","","","","",""
EOF,U22222222,ACTIVITY,20251231,20251231,20251231
"""

BOS_EOS_CSV = """\
BOS,Open Positions
ClientAccountID,CurrencyPrimary,AssetClass,Symbol,ISIN,Position,MarkPrice,LevelOfDetail
U22222222,USD,STK,O,US75513E1010,200,55.25,SECURITY
U22222222,USD,STK,ARCC,US02524D1081,100,21.10,SECURITY
EOS,Open Positions
"""

CLASSIC_CSV = """\
Statement,Header,Field Name,Field Value
Open Positions,Header,ClientAccountID,CurrencyPrimary,AssetClass,Symbol,ISIN,Position,MarkPrice,LevelOfDetail
Open Positions,Data,U22222222,USD,STK,EPR,US26884U1097,75,40.00,SECURITY
"""

# Options and CURRENCY rows should be filtered
MIXED_ASSETS_CSV = """\
BOF,U22222222,ACTIVITY,20251231,20251231,20251231
HEADER,Open Positions,CurrencyPrimary,AssetClass,Symbol,ISIN,Position,MarkPrice,LevelOfDetail
DATA,Open Positions,USD,OPT,AAPL_C250,US12345OPT001,10,3.50,SECURITY
DATA,Open Positions,USD,FUT,ES1,US99999FUT001,2,5000.00,SECURITY
DATA,Open Positions,USD,STK,AAPL,US0378331005,100,245.50,SECURITY
DATA,Open Positions,USD,STK,TOTAL,,,,CURRENCY
EOF,U22222222
"""

# Section not present at all
NO_SECTION_CSV = """\
BOF,U22222222
HEADER,Trades,Symbol,Date,Quantity
DATA,Trades,AAPL,20251201,10
EOF,U22222222
"""


# ── parse_ibkr_positions tests ─────────────────────────────────────────────────

class TestParseIbkrPositions:
    def test_header_data_format_parses_stocks(self, tmp_path):
        path = _write(tmp_path, HEADER_DATA_CSV)
        pos = parse_ibkr_positions(path)
        assert "AAPL" in pos
        assert "RHM" in pos
        assert pos["AAPL"]["qty"] == Decimal("100")
        assert pos["AAPL"]["price"] == Decimal("245.50")
        assert pos["AAPL"]["currency"] == "USD"
        assert pos["RHM"]["qty"] == Decimal("50")
        assert pos["RHM"]["price"] == Decimal("720.00")
        assert pos["RHM"]["currency"] == "EUR"

    def test_header_data_filters_currency_total_rows(self, tmp_path):
        path = _write(tmp_path, HEADER_DATA_CSV)
        pos = parse_ibkr_positions(path)
        assert "TOTAL" not in pos

    def test_bos_eos_format(self, tmp_path):
        path = _write(tmp_path, BOS_EOS_CSV)
        pos = parse_ibkr_positions(path)
        assert "O" in pos
        assert "ARCC" in pos
        assert pos["O"]["qty"] == Decimal("200")
        assert pos["O"]["price"] == Decimal("55.25")
        assert pos["ARCC"]["qty"] == Decimal("100")

    def test_classic_format(self, tmp_path):
        path = _write(tmp_path, CLASSIC_CSV)
        pos = parse_ibkr_positions(path)
        assert "EPR" in pos
        assert pos["EPR"]["qty"] == Decimal("75")
        assert pos["EPR"]["price"] == Decimal("40.00")

    def test_filters_options_and_futures(self, tmp_path):
        path = _write(tmp_path, MIXED_ASSETS_CSV)
        pos = parse_ibkr_positions(path)
        assert "AAPL" in pos
        # OPT and FUT tickers must not appear
        assert "AAPL_C250" not in pos
        assert "ES1" not in pos

    def test_filters_currency_aggregate_rows(self, tmp_path):
        path = _write(tmp_path, MIXED_ASSETS_CSV)
        pos = parse_ibkr_positions(path)
        assert "TOTAL" not in pos

    def test_empty_when_no_section(self, tmp_path):
        path = _write(tmp_path, NO_SECTION_CSV)
        pos = parse_ibkr_positions(path)
        assert pos == {}

    def test_isin_extracted_from_isin_column(self, tmp_path):
        path = _write(tmp_path, BOS_EOS_CSV)
        pos = parse_ibkr_positions(path)
        assert pos["O"]["isin"] == "US75513E1010"

    def test_isin_from_security_id_when_type_is_isin(self, tmp_path):
        csv_content = """\
BOF,U22222222
HEADER,Open Positions,CurrencyPrimary,AssetClass,Symbol,SecurityID,SecurityIDType,Position,MarkPrice,LevelOfDetail
DATA,Open Positions,USD,STK,VWRL,IE00B3RBWM25,ISIN,500,105.00,SECURITY
EOF,U22222222
"""
        path = _write(tmp_path, csv_content)
        pos = parse_ibkr_positions(path)
        assert pos["VWRL"]["isin"] == "IE00B3RBWM25"

    def test_zero_qty_skipped(self, tmp_path):
        csv_content = """\
BOF,U22222222
HEADER,Open Positions,CurrencyPrimary,AssetClass,Symbol,ISIN,Position,MarkPrice,LevelOfDetail
DATA,Open Positions,USD,STK,SOLD,,0,0.00,SECURITY
DATA,Open Positions,USD,STK,HELD,,10,50.00,SECURITY
EOF,U22222222
"""
        path = _write(tmp_path, csv_content)
        pos = parse_ibkr_positions(path)
        assert "SOLD" not in pos
        assert "HELD" in pos

    def test_negative_qty_skipped(self, tmp_path):
        csv_content = """\
BOF,U22222222
HEADER,Open Positions,CurrencyPrimary,AssetClass,Symbol,ISIN,Position,MarkPrice,LevelOfDetail
DATA,Open Positions,USD,STK,SHORT,,-100,50.00,SECURITY
EOF,U22222222
"""
        path = _write(tmp_path, csv_content)
        pos = parse_ibkr_positions(path)
        assert "SHORT" not in pos

    def test_bad_price_skipped(self, tmp_path):
        csv_content = """\
BOF,U22222222
HEADER,Open Positions,CurrencyPrimary,AssetClass,Symbol,ISIN,Position,MarkPrice,LevelOfDetail
DATA,Open Positions,USD,STK,BADPRICE,,10,N/A,SECURITY
DATA,Open Positions,USD,STK,GOODPRICE,,10,50.00,SECURITY
EOF,U22222222
"""
        path = _write(tmp_path, csv_content)
        pos = parse_ibkr_positions(path)
        assert "BADPRICE" not in pos
        assert "GOODPRICE" in pos

    def test_multi_lot_same_symbol_qty_summed(self, tmp_path):
        csv_content = """\
BOF,U22222222
HEADER,Open Positions,CurrencyPrimary,AssetClass,Symbol,ISIN,Position,MarkPrice,LevelOfDetail
DATA,Open Positions,USD,STK,AAPL,,60,245.00,SECURITY
DATA,Open Positions,USD,STK,AAPL,,40,245.00,SECURITY
EOF,U22222222
"""
        path = _write(tmp_path, csv_content)
        pos = parse_ibkr_positions(path)
        assert pos["AAPL"]["qty"] == Decimal("100")

    def test_default_currency_is_usd(self, tmp_path):
        csv_content = """\
BOF,U22222222
HEADER,Open Positions,AssetClass,Symbol,Position,MarkPrice,LevelOfDetail
DATA,Open Positions,STK,NOCCY,10,50.00,SECURITY
EOF,U22222222
"""
        path = _write(tmp_path, csv_content)
        pos = parse_ibkr_positions(path)
        assert pos["NOCCY"]["currency"] == "USD"


# ── _read_open_positions_section tests ────────────────────────────────────────

class TestReadSection:
    def test_returns_list_of_dicts(self, tmp_path):
        path = _write(tmp_path, BOS_EOS_CSV)
        rows = _read_open_positions_section(path)
        assert isinstance(rows, list)
        assert all(isinstance(r, dict) for r in rows)

    def test_header_data_row_count(self, tmp_path):
        path = _write(tmp_path, HEADER_DATA_CSV)
        rows = _read_open_positions_section(path)
        # 2 stock rows + 1 CURRENCY total = 3 raw rows (filtering is done by parse_ibkr_positions)
        assert len(rows) == 3

    def test_bos_eos_row_count(self, tmp_path):
        path = _write(tmp_path, BOS_EOS_CSV)
        rows = _read_open_positions_section(path)
        assert len(rows) == 2

    def test_empty_file_returns_empty(self, tmp_path):
        path = _write(tmp_path, "")
        rows = _read_open_positions_section(path)
        assert rows == []
