"""
Broker router — auto-detects which parser to use for a given file.

To add a new broker:
1. Create brokers/yourbroker.py with detect(path) and parse(path, config) functions
2. Add it to PARSERS list below
"""

import logging
from pathlib import Path

from core.models import NormalizedTransaction

log = logging.getLogger(__name__)

# Each entry: (module, display_name)
# Modules are imported lazily to keep startup fast
_PARSER_MODULES = [
    ("brokers.ib_csv",   "Interactive Brokers CSV"),
    # ("brokers.degiro",  "DEGIRO"),           # TODO: implement
    # ("brokers.flatex",  "Flatex Austria"),   # TODO: implement
]


def load_transactions(path: Path, config: dict,
                      broker_hint: str = "auto") -> list[NormalizedTransaction]:
    """
    Load and parse a broker export file.
    broker_hint: "auto" | "ib" | "degiro" | "flatex"
    """
    import importlib

    if broker_hint != "auto":
        hint_map = {"ib": "brokers.ib_csv"}
        mod_name = hint_map.get(broker_hint)
        if mod_name:
            mod = importlib.import_module(mod_name)
            return mod.parse(path, config)
        else:
            log.warning(f"Unknown broker hint '{broker_hint}', falling back to auto-detect")

    for mod_name, label in _PARSER_MODULES:
        mod = importlib.import_module(mod_name)
        if mod.detect(path):
            log.info(f"Auto-detected broker: {label} for {path.name}")
            return mod.parse(path, config)

    raise ValueError(
        f"Could not auto-detect broker format for: {path.name}\n"
        f"Supported brokers: {[l for _, l in _PARSER_MODULES]}\n"
        f"Use --broker flag to force a specific parser."
    )
