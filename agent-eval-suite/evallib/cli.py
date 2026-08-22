"""CLI entrypoint: validate a JSONL file against one of the evallib schema
models, one line at a time, and report every failing line rather than
stopping at the first.

Usage:
    python -m evallib.cli validate --model trace --file evals/traces.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from evallib.schema import (
    AxialCode,
    JudgeResult,
    LabelRecord,
    MetricsRecord,
    OpenCode,
    Trace,
)

MODELS = {
    "trace": Trace,
    "open-code": OpenCode,
    "axial-code": AxialCode,
    "label-record": LabelRecord,
    "judge-result": JudgeResult,
    "metrics-record": MetricsRecord,
}


def validate_file(model_name: str, path: Path) -> int:
    """Returns the number of invalid lines (0 = all valid)."""
    model = MODELS[model_name]
    n_errors = 0
    n_records = 0
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            n_records += 1
            try:
                model.model_validate_json(line)
            except (ValidationError, json.JSONDecodeError) as exc:
                n_errors += 1
                print(f"{path}:{line_no}: {exc}", file=sys.stderr)
    if n_errors:
        print(f"FAIL: {n_errors}/{n_records} invalid {model_name} record(s) in {path}")
    else:
        print(f"OK: {n_records} valid {model_name} record(s) in {path}")
    return n_errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m evallib.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser(
        "validate", help="Validate a JSONL file against a schema model"
    )
    validate_parser.add_argument(
        "--model", required=True, choices=sorted(MODELS), help="Schema model name"
    )
    validate_parser.add_argument(
        "--file", required=True, type=Path, help="Path to a JSONL file"
    )

    args = parser.parse_args(argv)

    if args.command == "validate":
        if not args.file.exists():
            print(f"error: {args.file} does not exist", file=sys.stderr)
            return 2
        n_errors = validate_file(args.model, args.file)
        return 1 if n_errors else 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
