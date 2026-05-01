#!/usr/bin/env python3
"""
Kapitalertrag — Austrian Capital Gains Tax Calculator
Processes broker exports and produces E1/E1kv-ready tax summaries.

Usage:
    python main.py --input ./data/ib_activity.csv --year 2024
    python main.py --input ./data/ib_activity.xml --year 2024 --person wife
    python main.py --help
"""

import argparse
import sys
from pathlib import Path

from core.pipeline import run_pipeline
from core.config import load_config


def main():
    parser = argparse.ArgumentParser(
        description="Austrian capital gains tax calculator from broker exports.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--input", required=True, nargs="+",
                        help="Path(s) to broker export file(s). Multiple files merged.")
    parser.add_argument("--year", type=int, required=True,
                        help="Tax year to calculate for (e.g. 2024)")
    parser.add_argument("--person", default="self",
                        help="Label for this person's data (e.g. 'self', 'wife'). "
                             "Used in output filenames.")
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

    input_paths = [Path(p) for p in args.input]
    for p in input_paths:
        if not p.exists():
            print(f"ERROR: Input file not found: {p}", file=sys.stderr)
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
