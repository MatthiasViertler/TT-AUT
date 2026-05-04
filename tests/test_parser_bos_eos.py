"""
Tests for the TT-AUT BOS/EOS format parser (Matthias's IBKR exports).
Each test targets one specific behaviour.
"""
from decimal import Decimal
from pathlib import Path

from brokers.ib_csv import parse
from core.models import TransactionType, AssetClass

from tests.conftest import FIXTURES


def _parse(filename: str, cfg: dict):
    txns, acct = parse(FIXTURES / filename, cfg)
    return txns, acct


# ── Basic dividend + WHT ─────────────────────────────────────────────────────

def test_account_id_extracted(cfg):
    _, acct = _parse("tt_aut_basic.csv", cfg)
    assert acct == "U99999999"


def test_dividend_parsed(cfg):
    txns, _ = _parse("tt_aut_basic.csv", cfg)
    divs = [t for t in txns if t.txn_type == TransactionType.DIVIDEND and t.symbol == "ALV"]
    assert len(divs) == 1
    assert divs[0].orig_amount == Decimal("1540.00")


def test_wht_netted_into_dividend(cfg):
    txns, _ = _parse("tt_aut_basic.csv", cfg)
    div = next(t for t in txns if t.symbol == "ALV" and t.txn_type == TransactionType.DIVIDEND)
    assert div.wht_amount_orig == Decimal("406.17")


def test_de_symbol_normalized(cfg):
    """ALVd must be normalized to ALV (DE ISIN + trailing 'd')."""
    txns, _ = _parse("tt_aut_basic.csv", cfg)
    symbols = [t.symbol for t in txns]
    assert "ALVd" not in symbols
    assert "ALV" in symbols


def test_country_code_from_isin(cfg):
    txns, _ = _parse("tt_aut_basic.csv", cfg)
    div = next(t for t in txns if t.symbol == "ALV")
    assert div.country_code == "DE"


def test_dk_dividend_parsed(cfg):
    txns, _ = _parse("tt_aut_basic.csv", cfg)
    # NOVd keeps the 'd' suffix (only stripped for DE ISINs)
    divs = [t for t in txns if t.symbol == "NOVd" and t.txn_type == TransactionType.DIVIDEND]
    assert len(divs) == 1
    assert divs[0].orig_amount == Decimal("395.00")
    assert divs[0].orig_currency == "DKK"
    assert divs[0].country_code == "DK"


def test_dk_symbol_normalized(cfg):
    """NOVd → NOV (DK ISIN, trailing 'd' stripped only for DE ISIN — NOV should stay NOV)."""
    txns, _ = _parse("tt_aut_basic.csv", cfg)
    # NOVd has DK ISIN so 'd' suffix should NOT be stripped (only DE ISINs)
    # The fixture has symbol NOVd with ISIN DK... → stays NOVd? Let's verify the actual rule.
    # Rule: strip 'd' only when isin.startswith("DE")
    # DK ISIN → NOVd stays as-is
    symbols = {t.symbol for t in txns if t.country_code == "DK"}
    assert "NOVd" in symbols  # DK ISIN → 'd' not stripped


def test_buy_trade_parsed(cfg):
    txns, _ = _parse("tt_aut_basic.csv", cfg)
    buys = [t for t in txns if t.txn_type == TransactionType.BUY]
    assert len(buys) == 1
    assert buys[0].symbol == "ALV"
    assert buys[0].quantity == Decimal("10")
    assert buys[0].asset_class == AssetClass.STOCK


# ── Return of Capital ─────────────────────────────────────────────────────────

def test_roc_group_skipped(cfg):
    """P911 Return of Capital group must be entirely skipped."""
    txns, _ = _parse("tt_aut_roc.csv", cfg)
    roc_divs = [t for t in txns if "return of capital" in t.description.lower()]
    assert len(roc_divs) == 0


def test_ordinary_dividend_after_roc_kept(cfg):
    """P911 ordinary dividend (different per-share key) must be kept."""
    txns, _ = _parse("tt_aut_roc.csv", cfg)
    divs = [t for t in txns if t.txn_type == TransactionType.DIVIDEND and t.symbol == "P911"]
    assert len(divs) == 1
    assert divs[0].orig_amount == Decimal("40.84")
    assert divs[0].wht_amount_orig == Decimal("10.77")


# ── Reversal netting (BAYN 2021) ──────────────────────────────────────────────

def test_reversal_nets_to_zero_cancelled(cfg):
    """The [70, -70] pair cancels; only the [70.01] re-booking survives."""
    txns, _ = _parse("tt_aut_reversal.csv", cfg)
    divs = [t for t in txns if t.txn_type == TransactionType.DIVIDEND and t.symbol == "BAYN"]
    assert len(divs) == 1


def test_reversal_correct_amount(cfg):
    txns, _ = _parse("tt_aut_reversal.csv", cfg)
    div = next(t for t in txns if t.symbol == "BAYN")
    assert div.orig_amount == Decimal("70.01")
    assert div.wht_amount_orig == Decimal("18.47")


# ── OPT filter ────────────────────────────────────────────────────────────────

def test_opt_trades_filtered(cfg):
    """OPT AssetClass rows in TRNT must be silently dropped."""
    txns, _ = _parse("tt_aut_opt_filter.csv", cfg)
    options = [t for t in txns if t.asset_class == AssetClass.OPTION]
    assert len(options) == 0


def test_stk_trades_kept_after_opt_filter(cfg):
    txns, _ = _parse("tt_aut_opt_filter.csv", cfg)
    buys = [t for t in txns if t.txn_type == TransactionType.BUY]
    assert len(buys) == 1
    assert buys[0].symbol == "SIE"
