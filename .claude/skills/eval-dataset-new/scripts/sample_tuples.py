#!/usr/bin/env python3
"""Sample dimension tuples from evals/dimensions.yaml's cross-product.

Copied into evals/scripts/sample_tuples.py by the eval-dataset-new skill so
each project owns and can edit its own copy independent of skill updates.

Usage:
    python evals/scripts/sample_tuples.py --dimensions evals/dimensions.yaml \\
        --n 40 --out evals/dimension_tuples.jsonl [--seed 0]

Output: one JSON object per line: {"tuple_id": "...", "dimension_tuple": [...]}
dimension_tuple values are ordered to match the dimension order in
dimensions.yaml, matching evallib.schema.Trace.dimension_tuple.
"""

from __future__ import annotations

import argparse
import itertools
import json
import random
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("error: PyYAML is required (pip install pyyaml)", file=sys.stderr)
    raise SystemExit(2)


def load_dimensions(path: Path) -> list[tuple[str, list[str]]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    dims = data.get("dimensions")
    if not dims or not isinstance(dims, list):
        raise ValueError(f"{path}: expected a top-level 'dimensions' list")
    out: list[tuple[str, list[str]]] = []
    for d in dims:
        name = d.get("name")
        values = d.get("values")
        if not name or not values:
            raise ValueError(f"{path}: each dimension needs 'name' and non-empty 'values': {d!r}")
        out.append((name, values))
    if not (3 <= len(out) <= 4):
        raise ValueError(
            f"{path}: expected 3-4 dimensions (persona, intent, complexity, "
            f"+1 domain-specific), got {len(out)}"
        )
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dimensions", required=True, type=Path)
    parser.add_argument("--n", required=True, type=int, help="number of tuples to sample")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args(argv)

    dims = load_dimensions(args.dimensions)
    names = [name for name, _ in dims]
    value_lists = [values for _, values in dims]

    cross_product = list(itertools.product(*value_lists))
    n_total = len(cross_product)

    rng = random.Random(args.seed)

    if args.n >= n_total:
        sampled = cross_product
        if args.n > n_total:
            print(
                f"note: requested {args.n} but the full cross-product only has "
                f"{n_total} tuples; using all {n_total} once each (no repeats)."
            )
    else:
        sampled = rng.sample(cross_product, args.n)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        for i, combo in enumerate(sampled):
            record = {
                "tuple_id": f"t-{i:04d}",
                "dimension_tuple": list(combo),
                "dimension_names": names,
            }
            f.write(json.dumps(record))
            f.write("\n")

    print(f"wrote {len(sampled)} tuples ({n_total} possible) to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
