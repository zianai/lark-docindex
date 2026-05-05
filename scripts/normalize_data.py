#!/usr/bin/env python3
"""Normalize, dedupe, and regroup Feishu document metadata."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from docindex_lib import group_records, load_json, normalize_records, validate_records, write_json


def extract_records(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("all"), list):
        return data["all"]
    if isinstance(data, dict):
        for key in ("by_type", "by_tag"):
            grouped = data.get(key)
            if isinstance(grouped, dict):
                records = []
                for items in grouped.values():
                    if isinstance(items, list):
                        records.extend(item for item in items if isinstance(item, dict))
                if records:
                    return records
    raise ValueError("input must be a record list or grouped object with an 'all' list")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", default="data/final_data.json")
    parser.add_argument("-o", "--output", default="data/final_data.normalized.json")
    parser.add_argument("--strip-anchor", action="store_true", help="remove URL fragments before grouping")
    parser.add_argument("--dedupe-canonical", action="store_true", help="dedupe URLs after removing fragments")
    parser.add_argument("--no-dedupe", action="store_true", help="keep duplicate URLs")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data = load_json(args.input)
    raw_records = extract_records(data)
    records = normalize_records(
        raw_records,
        keep_anchor=not args.strip_anchor,
        dedupe=not args.no_dedupe,
        dedupe_canonical=args.dedupe_canonical,
    )
    errors = validate_records(records)
    if errors:
        for error in errors[:30]:
            print(f"ERROR: {error}", file=sys.stderr)
        if len(errors) > 30:
            print(f"... and {len(errors) - 30} more errors", file=sys.stderr)
        return 1
    grouped = group_records(records)
    write_json(args.output, grouped)
    print(f"normalized {len(raw_records)} -> {len(records)} records: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
