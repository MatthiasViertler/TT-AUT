"""
Auto-fetch year-end closing prices via yfinance (Yahoo Finance).

Used by Nichtmeldefonds calculation to avoid manual dec31_prices config.
Results cached in cache/price_cache/ as JSON to avoid repeated network calls.

Cache key: {symbol}_{year}.json
Value: {"price": float, "currency": str, "date": "YYYY-MM-DD", "source": "yfinance"}
"""

import json
import logging
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

log = logging.getLogger(__name__)


def get_year_end_price(
    symbol: str,
    currency: str,
    year: int,
    cache_dir: str = "./cache/price_cache",
) -> Decimal | None:
    """
    Return the last trading-day closing price on or before Dec 31 of `year`.

    Checks disk cache first. On miss, fetches from Yahoo Finance via yfinance.
    Returns None if the price cannot be determined.
    """
    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)
    cache_file = cache_path / f"{symbol}_{year}.json"

    if cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text())
            log.debug(f"Price cache hit: {symbol} {year} = {cached['price']} {cached['currency']}")
            return Decimal(str(cached["price"]))
        except Exception as e:
            log.warning(f"Price cache read error for {symbol} {year}: {e}")

    price = _fetch_from_yfinance(symbol, year)
    if price is None:
        return None

    cache_file.write_text(json.dumps({
        "symbol": symbol,
        "year": year,
        "price": float(price),
        "currency": currency,
        "source": "yfinance",
        "fetched": date.today().isoformat(),
    }))
    log.info(f"Fetched & cached price: {symbol} {year} = {price} {currency}")
    return price


def _fetch_from_yfinance(symbol: str, year: int) -> Decimal | None:
    try:
        import yfinance as yf
    except ImportError:
        log.error("yfinance not installed. Run: pip install yfinance")
        return None

    # Fetch Jan 1 – Jan 5 of following year to guarantee we capture Dec 31
    start = date(year, 12, 1)
    end   = date(year + 1, 1, 5)

    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(start=start.isoformat(), end=end.isoformat(), auto_adjust=True)
    except Exception as e:
        log.warning(f"yfinance fetch error for {symbol}: {e}")
        return None

    if hist is None or hist.empty:
        log.warning(f"yfinance returned no data for {symbol} in {year}")
        return None

    # Find the last row on or before Dec 31
    dec31 = date(year, 12, 31)
    hist.index = hist.index.date  # strip timezone
    candidates = hist[hist.index <= dec31]

    if candidates.empty:
        log.warning(f"No trading data on or before Dec 31 {year} for {symbol}")
        return None

    last_row = candidates.iloc[-1]
    price = Decimal(str(round(float(last_row["Close"]), 4)))
    log.debug(f"yfinance: {symbol} last trading day <= Dec 31 {year}: "
              f"{candidates.index[-1]} = {price}")
    return price
