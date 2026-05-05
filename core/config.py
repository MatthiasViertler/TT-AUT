"""
Configuration management.

Load sequence:
  1. Built-in DEFAULTS (hardcoded here)
  2. config.yaml  — universal settings, committed to git
  3. users/{person}/config.local.yaml  — person-specific overrides, gitignored

scan_account_ids() scans all users/*/config.local.yaml for account_id entries and
returns a {account_id: person_name} mapping used for auto-detecting --person.
"""

from pathlib import Path
from typing import Any
import yaml


DEFAULTS: dict[str, Any] = {
    # Austrian capital gains tax rate (Kapitalertragsteuer / KESt)
    "kest_rate": 0.275,

    # ECB FX rates API (free, no key needed)
    "fx_source": "ecb",           # "ecb" or "manual"
    "fx_cache_dir": "./cache/fx_cache",

    # Year-end price cache for Nichtmeldefonds (auto-fetched via yfinance)
    "price_cache_dir": "./cache/price_cache",

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


def load_config(
    config_path: str = "config.yaml",
    person: str | None = None,
    users_dir: Path | str = Path("users"),
) -> dict[str, Any]:
    """Load universal config then merge person-specific overrides.

    Layer order (each overrides the previous):
      1. DEFAULTS
      2. config.yaml  (committed, universal)
      3. users/{person}/config.local.yaml  (gitignored, person-specific)

    If person is None, only layers 1–2 are applied. The pipeline then
    calls this again (or uses scan_account_ids) after detecting the person
    from account IDs found in the input files.
    """
    users_dir = Path(users_dir)
    config = dict(DEFAULTS)

    path = Path(config_path)
    if path.exists():
        with open(path) as f:
            user_config = yaml.safe_load(f) or {}
        _deep_merge(config, user_config)
        print(f"[config] Loaded: {path}")
    else:
        print(f"[config] No config file found at '{config_path}', using defaults.")

    if person:
        local_path = users_dir / person / "config.local.yaml"
        if local_path.exists():
            with open(local_path) as f:
                local_config = yaml.safe_load(f) or {}
            _deep_merge(config, local_config)
            print(f"[config] Loaded person overrides: {local_path}")
        else:
            print(f"[config] No person config found at '{local_path}'")

    return config


def scan_account_ids(users_dir: Path | str = Path("users")) -> dict[str, str]:
    """Scan users/*/config.local.yaml and return {account_id: person_name}.

    account_id in each person's config may be a scalar string or a list of
    strings (to support multiple broker accounts per person, e.g. IB + SAXO,
    or old/new account IDs after a broker migration).
    """
    users_dir = Path(users_dir)
    mapping: dict[str, str] = {}

    if not users_dir.is_dir():
        return mapping

    for person_dir in sorted(users_dir.iterdir()):
        if not person_dir.is_dir():
            continue
        person_name = person_dir.name
        local_path = person_dir / "config.local.yaml"
        if not local_path.exists():
            continue
        try:
            with open(local_path) as f:
                data = yaml.safe_load(f) or {}
        except Exception:
            continue

        raw = data.get("account_id")
        if raw is None:
            continue

        ids = raw if isinstance(raw, list) else [raw]
        for aid in ids:
            mapping[str(aid)] = person_name

    return mapping


def _deep_merge(base: dict, override: dict) -> None:
    """Merge override into base in-place. Nested dicts are merged recursively."""
    for key, val in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(val, dict):
            _deep_merge(base[key], val)
        else:
            base[key] = val
