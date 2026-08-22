#!/usr/bin/env python3
"""Export eval/golden_set.jsonl to a CSV for manual editing (Excel/Sheets/Numbers all open CSV directly).

Usage: python3 golden_to_csv.py <path/to/golden_set.jsonl> [path/to/golden_set.csv]
"""
import csv
import json
import sys
from pathlib import Path

FIELDS = ["id", "task_id", "category", "input", "good_output_notes", "bad_output_notes", "metrics_applicable", "source"]


def main():
    if len(sys.argv) < 2:
        print("Usage: golden_to_csv.py <golden_set.jsonl> [golden_set.csv]", file=sys.stderr)
        sys.exit(1)

    jsonl_path = Path(sys.argv[1])
    csv_path = Path(sys.argv[2]) if len(sys.argv) > 2 else jsonl_path.with_suffix(".csv")

    if not jsonl_path.exists():
        print(f"Error: {jsonl_path} does not exist", file=sys.stderr)
        sys.exit(1)

    rows = []
    with jsonl_path.open() as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"Error: {jsonl_path}:{lineno} is not valid JSON ({e})", file=sys.stderr)
                sys.exit(1)
            row = {}
            for field in FIELDS:
                val = obj.get(field, "")
                # Nested/list fields get JSON-encoded into a single cell so the
                # round trip is lossless; scalar fields stay plain text.
                if isinstance(val, (dict, list)):
                    val = json.dumps(val, ensure_ascii=False)
                row[field] = val
            rows.append(row)

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {csv_path}")
    print("Nested fields (input, metrics_applicable) are JSON-encoded in their cells — edit the JSON text in place, keep it valid JSON.")


if __name__ == "__main__":
    main()
