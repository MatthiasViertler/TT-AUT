#!/usr/bin/env python3
"""
Kapitalertrag — Austrian Capital Gains Tax Calculator
Processes broker exports and produces E1/E1kv-ready tax summaries.

Typical usage:
    # Auto-discovers input files and output dir from users/ structure
    python main.py --person matthias --year 2025

    # Explicit input files (power user / non-standard layout)
    python main.py --person matthias --input /path/to/file.csv --year 2025

    # Auto-detect person from account ID in input files
    python main.py --input users/matthias/data/IB/2025/file.csv --year 2025
"""

import argparse
import sys
from pathlib import Path

from core.pipeline import run_pipeline
from core.config import load_config, scan_account_ids

# File extensions recognised as potential broker exports
_BROKER_EXTENSIONS = {'.csv', '.xml', '.xlsx', '.xls', '.txt'}


def _resolve_inputs(paths: list[Path]) -> list[Path]:
    """Expand directories in the list to contained broker files (recursive)."""
    result = []
    for p in paths:
        if p.is_dir():
            files = sorted(
                f for f in p.rglob("*")
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


def _detect_person_from_paths(paths: list[Path], users_dir: Path) -> str | None:
    """If all paths sit under users/{person}/, return that person's name."""
    persons: set[str] = set()
    for p in paths:
        try:
            rel = p.resolve().relative_to(users_dir.resolve())
            persons.add(rel.parts[0])
        except ValueError:
            pass
    return persons.pop() if len(persons) == 1 else None


def main():
    parser = argparse.ArgumentParser(
        description="Austrian capital gains tax calculator from broker exports.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--input", nargs="+", default=None,
        help="Broker export file(s) or folder(s). Mix freely. "
             "If omitted, scans users/{person}/data/ automatically. "
             "Pass all years for correct FIFO cost basis.",
    )
    parser.add_argument("--year", type=int, required=True,
                        help="Tax year to calculate for (e.g. 2025)")
    parser.add_argument("--person", default="auto",
                        help="Person label (e.g. 'matthias'). "
                             "Default: auto-detected from account_id in users/*/config.local.yaml.")
    parser.add_argument("--broker", default="auto",
                        help="Force broker parser: 'ib', 'saxo', or 'auto' (default)")
    parser.add_argument("--config", default="config.yaml",
                        help="Path to universal config file (default: config.yaml)")
    parser.add_argument("--users-dir", default="./users",
                        help="Root directory for per-user data (default: ./users)")
    parser.add_argument("--output-dir", default=None,
                        help="Output directory override. "
                             "Default: users/{person}/output/")
    parser.add_argument("--no-fx-fetch", action="store_true",
                        help="Skip fetching live FX rates (use cached only)")

    args = parser.parse_args()
    users_dir = Path(args.users_dir)

    # ── Resolve person ────────────────────────────────────────────────────────
    person = args.person  # may be "auto"

    # If --person not given but --input paths are inside users/{person}/data/,
    # detect person from the path before loading config (avoids chicken-and-egg).
    if person == "auto" and args.input:
        raw_paths = [Path(p) for p in args.input]
        detected = _detect_person_from_paths(raw_paths, users_dir)
        if detected:
            person = detected
            print(f"  [person] Detected from input path: {person}")

    # ── Load config ───────────────────────────────────────────────────────────
    # If person still unknown, load base config only; pipeline will detect from
    # account_ids found in the parsed files and re-apply person overrides.
    known_person = person if person != "auto" else None
    config = load_config(args.config, person=known_person, users_dir=users_dir)

    # ── Resolve input files ───────────────────────────────────────────────────
    if args.input:
        raw_paths = [Path(p) for p in args.input]
    else:
        if person == "auto":
            print("ERROR: specify --person or --input (or both).", file=sys.stderr)
            sys.exit(1)
        data_dir = users_dir / person / "data"
        if not data_dir.is_dir():
            print(f"ERROR: data directory not found: {data_dir}", file=sys.stderr)
            sys.exit(1)
        raw_paths = [data_dir]

    for p in raw_paths:
        if not p.exists():
            print(f"ERROR: Input path not found: {p}", file=sys.stderr)
            sys.exit(1)

    input_paths = _resolve_inputs(raw_paths)

    if not input_paths:
        print("ERROR: No input files found. Check your --input path(s).", file=sys.stderr)
        sys.exit(1)

    # ── Resolve output directory ──────────────────────────────────────────────
    if args.output_dir:
        output_dir = Path(args.output_dir)
    elif person != "auto":
        output_dir = users_dir / person / "output"
    else:
        output_dir = Path("./output")  # fallback for full auto-detect mode

    output_dir.mkdir(parents=True, exist_ok=True)

    run_pipeline(
        input_paths=input_paths,
        tax_year=args.year,
        person_label=person,
        broker_hint=args.broker,
        config=config,
        output_dir=output_dir,
        fetch_fx=not args.no_fx_fetch,
        users_dir=users_dir,
    )


if __name__ == "__main__":
    main()
