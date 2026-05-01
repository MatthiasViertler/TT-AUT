"""
Configuration management.
Loads config.yaml (if present) and merges with sensible defaults.
"""

from pathlib import Path
from typing import Any
import yaml


DEFAULTS: dict[str, Any] = {
    # Austrian capital gains tax rate (Kapitalertragsteuer / KESt)
    "kest_rate": 0.275,

    # ECB FX rates API (free, no key needed)
    "fx_source": "ecb",           # "ecb" or "manual"
    "fx_cache_dir": "./data/fx_cache",

    # How to handle FX: "daily" uses trade-date rate, "annual_avg" uses yearly average
    # Austrian tax law: use daily ECB rate on transaction date
    "fx_method": "daily",

    # Withholding tax (Quellensteuer) treaty rates by country ISO code.
    # Key = country code, value = treaty-reduced WHT rate (0.0–1.0).
    # Default (no treaty / unknown): use actual rate from broker data.
    # Austrian DBA treaties — add/override as needed.
    "wht_treaty_rates": {
        "US": 0.15,   # Austria–US DBA, Art. 10: 15% on dividends
        "DE": 0.15,   # Austria–Germany DBA
        "CH": 0.15,   # Austria–Switzerland DBA
        "GB": 0.15,
        "FR": 0.15,
        "NL": 0.15,
        "IE": 0.15,
        "LU": 0.15,
        "SE": 0.15,
        "DK": 0.15,
        "FI": 0.15,
        "NO": 0.15,
        "CA": 0.15,
        "JP": 0.10,
        "AU": 0.15,
    },

    # Maximum creditable WHT against Austrian KESt (§ 1 Abs 4 KStG / § 27a EStG)
    # Austria allows crediting up to the treaty rate (not the full KESt rate)
    "max_creditable_wht": 0.15,

    # Transaction classification rules:
    # Any IB activity code mapped to internal type.
    # Extend here for new brokers without touching core code.
    "ib_action_map": {
        "DIV":    "dividend",
        "DIVNRA": "dividend_wht",   # Non-resident alien tax (= Quellensteuer)
        "BUY":    "buy",
        "SELL":   "sell",
        "REIN":   "dividend",       # Dividend reinvestment
        "PI":     "interest",       # Interest income
        "CINT":   "interest",       # Credit interest
        "FRTAX":  "dividend_wht",   # Foreign tax
        "FXCGL":  "fx_gain_loss",   # FX cash gain/loss (usually not taxable)
        "CORP":   "corporate_action",
        "JNLAFX": "fx_transfer",    # Journal FX (internal, skip)
        "JNLCSH": "cash_transfer",  # Journal cash (internal, skip)
        "DEP":    "deposit",
        "WITH":   "withdrawal",
    },

    # Internal types to include in tax calculations
    "taxable_types": ["dividend", "dividend_wht", "buy", "sell", "interest"],

    # Output options
    "output": {
        "excel": True,          # Rich Excel dashboard
        "csv": True,            # Raw transaction CSV
        "tax_summary": True,    # E1kv Kennziffern summary (TXT + CSV)
        "console": True,        # Print summary to stdout
    },
}


def load_config(config_path: str = "config.yaml") -> dict[str, Any]:
    """Load config file if it exists, merge with defaults."""
    config = dict(DEFAULTS)  # start with a copy of defaults

    path = Path(config_path)
    if path.exists():
        with open(path) as f:
            user_config = yaml.safe_load(f) or {}
        # Deep merge: user values override defaults, but nested dicts are merged
        _deep_merge(config, user_config)
        print(f"[config] Loaded: {path}")
    else:
        print(f"[config] No config file found at '{config_path}', using defaults.")

    return config


def _deep_merge(base: dict, override: dict) -> None:
    """Merge override into base in-place. Nested dicts are merged recursively."""
    for key, val in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(val, dict):
            _deep_merge(base[key], val)
        else:
            base[key] = val
