"""
FX rate module.
Fetches historical EUR exchange rates from the European Central Bank (ECB).
Caches results to disk to avoid repeated network calls.

ECB data source: https://data-api.ecb.europa.eu/service/data/EXR/
- Free, no API key required
- Daily rates, goes back to 1999
- ~170 currencies
"""

import json
import logging
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Optional
import urllib.request
import urllib.error

log = logging.getLogger(__name__)


class FXRateProvider:
    """
    Provides EUR-based exchange rates for any date.
    Usage:
        fx = FXRateProvider(cache_dir="./data/fx_cache")
        rate = fx.get_rate("USD", date(2024, 3, 15))  # returns EUR per 1 USD
    """

    ECB_BASE = "https://data-api.ecb.europa.eu/service/data/EXR/D.{currency}.EUR.SP00.A"
    ECB_PARAMS = "?startPeriod={start}&endPeriod={end}&format=csvdata"

    def __init__(self, cache_dir: str = "./data/fx_cache", fetch_live: bool = True):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.fetch_live = fetch_live
        self._memory: dict[tuple[str, date], Decimal] = {}  # in-process cache

    # ── Public API ────────────────────────────────────────────────────────────

    def get_rate(self, currency: str, on_date: date) -> Optional[Decimal]:
        """
        Return rate: 1 {currency} = ? EUR on {on_date}.
        Returns None if rate unavailable (caller should warn).
        EUR itself always returns 1.0.
        """
        if currency.upper() == "EUR":
            return Decimal("1.0")

        currency = currency.upper()
        key = (currency, on_date)

        if key in self._memory:
            return self._memory[key]

        # Try nearest trading day (ECB doesn't publish weekends/holidays)
        for delta in range(5):
            check_date = on_date - timedelta(days=delta)
            rate = self._lookup(currency, check_date)
            if rate is not None:
                self._memory[key] = rate
                return rate

        log.warning(f"FX: No rate found for {currency} around {on_date}")
        return None

    def get_annual_average(self, currency: str, year: int) -> Optional[Decimal]:
        """Annual average rate — sometimes used as a fallback."""
        rates = []
        start = date(year, 1, 1)
        end = date(year, 12, 31)
        self._ensure_fetched(currency, start, end)

        d = start
        while d <= end:
            r = self._lookup_exact(currency, d)
            if r is not None:
                rates.append(r)
            d += timedelta(days=1)

        if not rates:
            return None
        return (sum(rates) / len(rates)).quantize(Decimal("0.000001"))

    # ── Internal ──────────────────────────────────────────────────────────────

    def _lookup(self, currency: str, on_date: date) -> Optional[Decimal]:
        """Try exact date. If not in cache, fetch year block from ECB first."""
        self._ensure_fetched(currency, on_date, on_date)
        return self._lookup_exact(currency, on_date)

    def _lookup_exact(self, currency: str, on_date: date) -> Optional[Decimal]:
        cache = self._load_cache(currency, on_date.year)
        return cache.get(str(on_date))

    def _ensure_fetched(self, currency: str, start: date, end: date) -> None:
        """Fetch all years in [start.year, end.year] range if not cached."""
        if not self.fetch_live:
            return
        for year in range(start.year, end.year + 1):
            cache_file = self._cache_file(currency, year)
            if not cache_file.exists():
                self._fetch_year(currency, year)

    def _fetch_year(self, currency: str, year: int) -> None:
        """Download a full year of daily rates from ECB and cache to disk."""
        start = f"{year}-01-01"
        end = f"{year}-12-31"
        url = (self.ECB_BASE.format(currency=currency) +
               self.ECB_PARAMS.format(start=start, end=end))

        log.info(f"FX: Fetching {currency}/{year} from ECB…")
        try:
            req = urllib.request.Request(url, headers={"Accept": "text/csv"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.URLError as e:
            log.warning(f"FX: Could not fetch {currency}/{year}: {e}")
            # Write empty cache so we don't retry endlessly this session
            self._save_cache(currency, year, {})
            return

        rates: dict[str, str] = {}
        for line in raw.splitlines()[1:]:  # skip header
            parts = line.split(",")
            if len(parts) < 8:
                continue
            date_str = parts[6].strip().strip('"')
            rate_str = parts[7].strip().strip('"')
            if date_str and rate_str:
                try:
                    # ECB publishes units of currency per EUR; we want EUR per unit
                    ecb_rate = Decimal(rate_str)
                    eur_per_unit = (Decimal("1") / ecb_rate).quantize(Decimal("0.000001"))
                    rates[date_str] = str(eur_per_unit)
                except Exception:
                    pass

        self._save_cache(currency, year, rates)
        log.info(f"FX: Cached {len(rates)} daily rates for {currency}/{year}")

    def _cache_file(self, currency: str, year: int) -> Path:
        return self.cache_dir / f"{currency}_{year}.json"

    def _load_cache(self, currency: str, year: int) -> dict[str, Decimal]:
        f = self._cache_file(currency, year)
        if f.exists():
            with open(f) as fh:
                data = json.load(fh)
            return {k: Decimal(str(v)) for k, v in data.items()}
        return {}

    def _save_cache(self, currency: str, year: int, rates: dict) -> None:
        f = self._cache_file(currency, year)
        with open(f, "w") as fh:
            json.dump(rates, fh, indent=2)
