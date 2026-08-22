#!/usr/bin/env python3
"""Import a manually-edited CSV back into eval/golden_set.jsonl.

Backs up the existing golden_set.jsonl to golden_set.jsonl.bak before
overwriting, and prints a summary of added/removed/modified example IDs
so the caller can report a real diff instead of a blind overwrite.

Usage: python3 csv_to_golden.py <path/to/golden_set.csv> <path/to/golden_set.jsonl>
"""
import csv
import json
import sys
from pathlib import Path

FIELDS = ["id", "task_id", "category", "input", "good_output_notes", "bad_output_notes", "metrics_applicable", "source"]
JSON_FIELDS = {"input", "metrics_applicable"}
VALID_CATEGORIES = {"common", "edge", "past_failure"}


def load_existing(jsonl_path: Path):
    existing = {}
    if jsonl_path.exists():
        with jsonl_path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                existing[obj["id"]] = obj
    return existing


def main():
    if len(sys.argv) < 3:
        print("Usage: csv_to_golden.py <golden_set.csv> <golden_set.jsonl>", file=sys.stderr)
        sys.exit(1)

    csv_path = Path(sys.argv[1])
    jsonl_path = Path(sys.argv[2])

    if not csv_path.exists():
        print(f"Error: {csv_path} does not exist", file=sys.stderr)
        sys.exit(1)

    existing = load_existing(jsonl_path)

    new_rows = []
    errors = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing_cols = [c for c in FIELDS if c not in (reader.fieldnames or [])]
        if missing_cols:
            print(f"Error: CSV is missing required columns: {missing_cols}", file=sys.stderr)
            sys.exit(1)

        for rownum, row in enumerate(reader, 2):  # header is row 1
            obj = {}
            for field in FIELDS:
                val = (row.get(field) or "").strip()
                if field in JSON_FIELDS:
                    if val == "":
                        errors.append(f"row {rownum} (id={row.get('id')}): '{field}' is empty, expected JSON")
                        continue
                    try:
                        obj[field] = json.loads(val)
                    except json.JSONDecodeError as e:
                        errors.append(f"row {rownum} (id={row.get('id')}): '{field}' is not valid JSON ({e})")
                        continue
                else:
                    obj[field] = val

            if not obj.get("id"):
                errors.append(f"row {rownum}: missing 'id'")
            if obj.get("category") and obj["category"] not in VALID_CATEGORIES:
                errors.append(f"row {rownum} (id={obj.get('id')}): category '{obj['category']}' not in {VALID_CATEGORIES}")

            new_rows.append(obj)

    if errors:
        print("Validation errors — fix these in the CSV and re-run before anything is written:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)

    new_ids = {obj["id"] for obj in new_rows}
    old_ids = set(existing.keys())
    added = sorted(new_ids - old_ids)
    removed = sorted(old_ids - new_ids)
    modified = sorted(
        obj["id"] for obj in new_rows
        if obj["id"] in existing and existing[obj["id"]] != obj
    )

    if jsonl_path.exists():
        backup_path = jsonl_path.with_suffix(jsonl_path.suffix + ".bak")
        backup_path.write_text(jsonl_path.read_text())
        print(f"Backed up previous file to {backup_path}")

    with jsonl_path.open("w", encoding="utf-8") as f:
        for obj in new_rows:
            ordered = {field: obj[field] for field in FIELDS}
            f.write(json.dumps(ordered, ensure_ascii=False) + "\n")

    print(f"Wrote {len(new_rows)} rows to {jsonl_path}")
    print(f"Added: {added or 'none'}")
    print(f"Removed: {removed or 'none'}")
    print(f"Modified: {modified or 'none'}")


if __name__ == "__main__":
    main()
