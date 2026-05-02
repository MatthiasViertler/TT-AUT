#!/usr/bin/env python3
"""
Kapitalertrag — Austrian Capital Gains Tax Calculator
Processes broker exports and produces E1/E1kv-ready tax summaries.

Usage:
    # Single file
    python main.py --input ./data/ib_activity.csv --year 2024

    # Multiple files (merged, all years needed for correct FIFO)
    python main.py --input ./data/2023.csv ./data/2024.csv --year 2024

    # Whole folder — scans for all broker files automatically
    python main.py --input ./data/Jessie/ --year 2024

    # Mix of files and folders
    python main.py --input ./data/Jessie/ ./data/extra_2024.csv --year 2024
"""

import argparse
import sys
from pathlib import Path

from core.pipeline import run_pipeline
from core.config import load_config

# File extensions recognised as potential broker exports
_BROKER_EXTENSIONS = {'.csv', '.xml', '.xlsx', '.xls', '.txt'}


def _resolve_inputs(paths: list[Path]) -> list[Path]:
    """Expand any directories in the list to their contained broker files."""
    result = []
    for p in paths:
        if p.is_dir():
            files = sorted(
                f for f in p.iterdir()
                if f.is_file()
                and f.suffix.lower() in _BROKER_EXTENSIONS
                and not f.name.startswith(('.', '~', '_'))
            )
            if files:
                print(f"  [input]  Scanned {p}/ → {len(files)} file(s): "
                      f"{', '.join(f.name for f in files)}")
            else:
                print(f"  [warn]   No broker files found in {p}/  "
                      f"(looking for: {', '.join(sorted(_BROKER_EXTENSIONS))})",
                      file=sys.stderr)
            result.extend(files)
        else:
            result.append(p)
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Austrian capital gains tax calculator from broker exports.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--input", required=True, nargs="+",
        help="Broker export file(s) or folder(s). Mix freely. "
             "Folders are scanned for .csv/.xml/.xlsx files. "
             "Pass all years for correct FIFO cost basis.",
    )
    parser.add_argument("--year", type=int, required=True,
                        help="Tax year to calculate for (e.g. 2024)")
    parser.add_argument("--person", default="auto",
                        help="Label for this person's data (e.g. 'Jessie'). "
                             "Default: auto-detected from account ID via account_map in config.yaml.")
    parser.add_argument("--broker", default="auto",
                        help="Force broker parser: 'ib', 'degiro', 'flatex', or 'auto' (default)")
    parser.add_argument("--config", default="config.yaml",
                        help="Path to config file (default: config.yaml)")
    parser.add_argument("--output-dir", default="./output",
                        help="Directory for output files (default: ./output)")
    parser.add_argument("--no-fx-fetch", action="store_true",
                        help="Skip fetching live FX rates (use cached only)")

    args = parser.parse_args()

    config = load_config(args.config)

    raw_paths = [Path(p) for p in args.input]
    for p in raw_paths:
        if not p.exists():
            print(f"ERROR: Input path not found: {p}", file=sys.stderr)
            sys.exit(1)

    input_paths = _resolve_inputs(raw_paths)

    if not input_paths:
        print("ERROR: No input files found. Check your --input path(s).", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    run_pipeline(
        input_paths=input_paths,
        tax_year=args.year,
        person_label=args.person,
        broker_hint=args.broker,
        config=config,
        output_dir=output_dir,
        fetch_fx=not args.no_fx_fetch,
    )


if __name__ == "__main__":
    main()
