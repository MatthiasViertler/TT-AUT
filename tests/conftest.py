"""Shared pytest fixtures."""
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

# Make project root importable without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import DEFAULTS
from core.models import (
    AssetClass, Domicile, NormalizedTransaction, TransactionType,
)


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def cfg():
    """Minimal config identical to production defaults."""
    return dict(DEFAULTS)


def make_dividend(
    symbol: str,
    isin: str,
    gross_eur: float,
    wht_eur: float,
    trade_date: date = date(2025, 5, 13),
    country_code: str = "DE",
) -> NormalizedTransaction:
    """Helper: create a fully FX-enriched DIVIDEND transaction (EUR, rate=1)."""
    g = Decimal(str(gross_eur))
    w = Decimal(str(wht_eur))
    return NormalizedTransaction(
        broker="ib",
        raw_id=f"test_{symbol}_{trade_date}",
        trade_date=trade_date,
        settle_date=None,
        txn_type=TransactionType.DIVIDEND,
        asset_class=AssetClass.STOCK,
        symbol=symbol,
        isin=isin,
        description=f"{symbol} CASH DIVIDEND",
        country_code=country_code,
        domicile=Domicile.FOREIGN,
        quantity=None,
        price=None,
        price_currency=None,
        orig_currency="EUR",
        orig_amount=g,
        wht_amount_orig=w,
        fx_rate_to_eur=Decimal("1"),
        eur_amount=g,
        eur_wht=w,
        source_file="test",
    )
