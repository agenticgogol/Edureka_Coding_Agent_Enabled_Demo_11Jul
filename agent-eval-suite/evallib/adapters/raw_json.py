"""Adapter for a raw JSON trace log: a JSON array of dicts already shaped
close to Trace, e.g. exported manually or by a bespoke agent harness.

Expected raw record shape:

    {
        "query_id": "...",
        "dimension_tuple": ["...", "..."],       # optional
        "turns": [
            {"role": "user", "content": "..."},
            {"role": "assistant", "content": "...", "tool_calls": [...]}
        ],
        "final_response": "...",
        "metadata": {...}                         # optional
    }
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

from evallib.adapters.base import TraceAdapter
from evallib.schema import Trace


class RawJSONAdapter(TraceAdapter):
    """Reads a JSON file containing a top-level array of raw trace dicts."""

    def iter_raw_records(self, source: str | Path) -> Iterator[dict[str, Any]]:
        data = json.loads(Path(source).read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError(
                f"{source}: expected a top-level JSON array of trace records, "
                f"got {type(data).__name__}"
            )
        yield from data

    def to_trace(self, raw_record: dict[str, Any]) -> Trace:
        return Trace.model_validate(raw_record)
