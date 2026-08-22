"""Adapter for a Braintrust experiment/log export.

ASSUMPTIONS — verify against your actual export before trusting this
blindly (Braintrust's exact JSON shape depends on your account/SDK version
and how you logged the conversation; this was not cross-checked against
live Braintrust docs when written):

Expects a JSON array of "event" rows, each roughly:

    {
        "id": "...",                              # used as query_id if present
        "root_span_id": "...",                    # optional; falls back to "id"
        "input": [{"role": "user", "content": "..."}, ...]   # OR a bare string
                  | "a single user message string",
        "output": {"role": "assistant", "content": "..."}    # OR a bare string
                   | "final assistant text",
        "metadata": {
            "tool_calls": [...],                  # optional, best-effort
            "tool_results": [...],                # optional, best-effort
            "retrieved_docs": [...]                # optional, best-effort
        },
        "tags": [...]                              # optional
    }

Because Braintrust rows are usually already one-row-per-example (input/
output pair), this adapter treats each row as ONE trace with a two-turn
conversation (user, then assistant) by default. If your logging captured a
full multi-turn `input` message list, that list is used directly as the
turn sequence instead — this adapter picks whichever shape the row actually
has, it does not assume one over the other.

If your actual export nests events differently (e.g. under a top-level
"events" or "data" key instead of being the array itself), unwrap that
before passing the file to this adapter, or extend `iter_raw_records`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

from evallib.adapters.base import TraceAdapter
from evallib.schema import Trace


def _as_turn_dict(message: Any, default_role: str) -> dict[str, Any]:
    if isinstance(message, str):
        return {"role": default_role, "content": message}
    if isinstance(message, dict):
        return {
            "role": message.get("role", default_role),
            "content": message.get("content", "") or "",
        }
    raise ValueError(f"cannot interpret message as a turn: {message!r}")


class BraintrustAdapter(TraceAdapter):
    """Reads a JSON file containing a top-level array of Braintrust event
    rows (see module docstring for the assumed shape)."""

    def iter_raw_records(self, source: str | Path) -> Iterator[dict[str, Any]]:
        data = json.loads(Path(source).read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError(
                f"{source}: expected a top-level JSON array of Braintrust "
                f"event rows, got {type(data).__name__}. If your export "
                f"nests rows under a key like \"events\" or \"data\", "
                f"unwrap that first."
            )
        yield from data

    def to_trace(self, raw_record: dict[str, Any]) -> Trace:
        query_id = str(raw_record.get("root_span_id") or raw_record.get("id") or "")
        if not query_id:
            raise ValueError(f"Braintrust row has no 'id' or 'root_span_id': {raw_record!r}")

        raw_input = raw_record.get("input")
        turns: list[dict[str, Any]] = []
        if isinstance(raw_input, list):
            # Already a multi-turn message list — use it as-is.
            turns.extend(_as_turn_dict(m, "user") for m in raw_input)
        elif raw_input is not None:
            turns.append(_as_turn_dict(raw_input, "user"))

        raw_output = raw_record.get("output")
        final_response = ""
        if raw_output is not None:
            assistant_turn = _as_turn_dict(raw_output, "assistant")
            final_response = assistant_turn["content"]
            metadata = raw_record.get("metadata") or {}
            assistant_turn["tool_calls"] = metadata.get("tool_calls", [])
            assistant_turn["tool_results"] = metadata.get("tool_results", [])
            assistant_turn["retrieved_docs"] = metadata.get("retrieved_docs", [])
            turns.append(assistant_turn)

        if not turns:
            raise ValueError(f"Braintrust row has neither 'input' nor 'output': {raw_record!r}")

        return Trace.model_validate(
            {
                "query_id": query_id,
                "turns": turns,
                "final_response": final_response,
                "metadata": {
                    "source": "braintrust",
                    "tags": raw_record.get("tags", []),
                },
            }
        )
