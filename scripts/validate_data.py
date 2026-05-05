#!/usr/bin/env python3
"""Validate lark-docindex record data before writing Base or Wiki cards."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from docindex_lib import load_json, normalize_records, validate_grouped_data, validate_records
from normalize_data import extract_records


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", default="data/final_data.json")
    parser.add_argument("--raw", action="store_true", help="validate the file as-is without normalization rescue")
    parser.add_argument("--strip-anchor", action="store_true", help="remove URL fragments before validation")
    parser.add_argument("--dedupe-canonical", action="store_true", help="dedupe URLs after removing fragments")
    return parser.parse_args()


def validate_raw(data: Any) -> list[str]:
    if isinstance(data, dict) and "all" in data:
        return validate_grouped_data(data)
    if isinstance(data, list):
        return validate_records(data)
    return ["input must be a record list or grouped object with an 'all' list"]


def main() -> int:
    args = parse_args()
    data = load_json(args.input)
    if args.raw:
        errors = validate_raw(data)
        count = len(data.get("all", data)) if isinstance(data, dict) else len(data)
    else:
        raw_records = extract_records(data)
        records = normalize_records(
            raw_records,
            keep_anchor=not args.strip_anchor,
            dedupe=True,
            dedupe_canonical=args.dedupe_canonical,
        )
        errors = validate_records(records)
        count = len(records)

    if errors:
        print(f"INVALID: {args.input} ({len(errors)} errors)", file=sys.stderr)
        for error in errors[:50]:
            print(f"ERROR: {error}", file=sys.stderr)
        if len(errors) > 50:
            print(f"... and {len(errors) - 50} more errors", file=sys.stderr)
        return 1

    print(f"OK: {args.input} ({count} records)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
