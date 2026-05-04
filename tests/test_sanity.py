"""
Sanity / plausibility checks.
These run over both the fixture-parsed transactions and the ground-truth 2025 DE set.
They guard against systematic calculation errors (negative dividends, WHT > gross, etc.).
"""
from decimal import Decimal

import pytest

from brokers.ib_csv import parse
from core.models import TransactionType
from tests.conftest import FIXTURES, make_dividend
from tests.test_wht_reclaim import DE_2025_DIVIDENDS

from datetime import date


# ── helpers ───────────────────────────────────────────────────────────────────

def dividends_from_file(filename: str, cfg: dict):
    txns, _ = parse(FIXTURES / filename, cfg)
    return [t for t in txns if t.txn_type == TransactionType.DIVIDEND]


# ── fixtures sanity ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("filename", [
    "tt_aut_basic.csv",
    "tt_aut_roc.csv",
    "tt_aut_reversal.csv",
    "tt_aut_opt_filter.csv",
    "header_data_basic.csv",
])
def test_gross_always_positive(filename, cfg):
    divs = dividends_from_file(filename, cfg)
    for d in divs:
        assert d.orig_amount > Decimal("0"), \
            f"{d.symbol}: non-positive gross {d.orig_amount}"


@pytest.mark.parametrize("filename", [
    "tt_aut_basic.csv",
    "tt_aut_roc.csv",
    "tt_aut_reversal.csv",
    "tt_aut_opt_filter.csv",
    "header_data_basic.csv",
])
def test_wht_never_exceeds_gross(filename, cfg):
    divs = dividends_from_file(filename, cfg)
    for d in divs:
        assert d.wht_amount_orig <= d.orig_amount, \
            f"{d.symbol}: WHT {d.wht_amount_orig} > gross {d.orig_amount}"


@pytest.mark.parametrize("filename", [
    "tt_aut_basic.csv",
    "tt_aut_reversal.csv",
    "tt_aut_opt_filter.csv",
])
def test_wht_non_negative(filename, cfg):
    divs = dividends_from_file(filename, cfg)
    for d in divs:
        assert d.wht_amount_orig >= Decimal("0"), \
            f"{d.symbol}: negative WHT {d.wht_amount_orig}"


# ── 2025 DE ground truth sanity ───────────────────────────────────────────────

@pytest.fixture
def de_2025_txns():
    return [
        make_dividend(sym, isin, gross, wht, trade_date=date(2025, 5, 13))
        for sym, isin, gross, wht in DE_2025_DIVIDENDS
    ]


def test_de_2025_wht_never_exceeds_gross(de_2025_txns):
    for t in de_2025_txns:
        assert t.eur_wht <= t.eur_amount, \
            f"{t.symbol}: WHT {t.eur_wht} > gross {t.eur_amount}"


def test_de_2025_effective_rate_plausible(de_2025_txns):
    """Effective WHT rate should be ~26.375% (DE 25% + 5.5% Soli) for all stocks."""
    for t in de_2025_txns:
        rate = t.eur_wht / t.eur_amount
        # Allow ±2pp tolerance for per-stock rounding (e.g. SIE rounds to ~25.06%)
        assert Decimal("0.248") <= rate <= Decimal("0.280"), \
            f"{t.symbol}: unexpected WHT rate {float(rate):.3%}"


def test_de_2025_creditable_never_exceeds_wht(de_2025_txns):
    """Creditable amount (15% of gross) must never exceed actual WHT paid."""
    treaty = Decimal("0.15")
    for t in de_2025_txns:
        creditable = t.eur_amount * treaty
        assert creditable <= t.eur_wht, \
            f"{t.symbol}: creditable {creditable} > WHT {t.eur_wht}"


def test_de_2025_excess_positive_for_all(de_2025_txns):
    """Every DE stock should have positive excess (26.375% > 15% treaty)."""
    treaty = Decimal("0.15")
    for t in de_2025_txns:
        excess = t.eur_wht - t.eur_amount * treaty
        assert excess > Decimal("0.05"), \
            f"{t.symbol}: expected reclaimable excess, got {excess}"
