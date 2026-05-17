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
    ("brokers.ib_csv",             "Interactive Brokers CSV"),
    ("brokers.saxo_closedpos_xlsx","SAXO Bank ClosedPositions xlsx"),
    ("brokers.saxo_xlsx",          "SAXO Bank xlsx"),
    ("brokers.etrade_pdf",         "E*TRADE PDF"),
    # ("brokers.degiro",  "DEGIRO"),           # TODO: implement
    # ("brokers.flatex",  "Flatex Austria"),   # TODO: implement
]

_IB_MOD = "brokers.ib_csv"


def load_transactions(
    path: Path,
    config: dict,
    broker_hint: str = "auto",
    suppress_cash: bool = False,
) -> tuple[list[NormalizedTransaction], str | None]:
    """
    Load and parse a broker export file.
    Returns (transactions, account_id).
    broker_hint: "auto" | "ib" | "degiro" | "flatex"
    suppress_cash: skip dividend/cash parsing for IB files. Used to prevent
        double-counting when a TT-AUT annual export overlaps with a Flex CSV.
    """
    import importlib

    if broker_hint != "auto":
        hint_map = {
            "ib":        _IB_MOD,
            "saxo":      "brokers.saxo_xlsx",
            "closedpos": "brokers.saxo_closedpos_xlsx",
        }
        mod_name = hint_map.get(broker_hint)
        if mod_name:
            mod = importlib.import_module(mod_name)
            kwargs = {"suppress_cash": suppress_cash} if mod_name == _IB_MOD else {}
            return mod.parse(path, config, **kwargs)
        else:
            log.warning(f"Unknown broker hint '{broker_hint}', falling back to auto-detect")

    for mod_name, label in _PARSER_MODULES:
        mod = importlib.import_module(mod_name)
        if mod.detect(path):
            log.info(f"Auto-detected broker: {label} for {path.name}")
            kwargs = {"suppress_cash": suppress_cash} if mod_name == _IB_MOD else {}
            return mod.parse(path, config, **kwargs)

    log.warning("Skipping unrecognised file (no parser matched): %s", path.name)
    return None, None
