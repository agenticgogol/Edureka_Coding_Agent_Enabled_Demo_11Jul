"""Adapter for an Arize Phoenix span export.

ASSUMPTIONS — read before trusting this, more so than any other adapter
here. Phoenix exports *spans* (OpenInference semantic conventions), not
conversations — there is no native "one row = one Trace" concept the way
Braintrust or a raw JSON log has, so reconstructing a Trace means grouping
spans by trace_id and making judgment calls about what counts as a turn.
This was written against the *commonly documented* OpenInference shape, not
cross-checked against live Phoenix docs — verify field names against your
actual export (`phoenix.Client().get_spans_dataframe(...)`, then
`.to_json(orient="records", path_or_buf=...)` or `.to_dict(orient="records")`
dumped to a file) before relying on it, and expect to adjust the attribute
lookups below if your Phoenix/OpenInference version differs.

Expected raw record shape: a JSON array of span dicts, each with (some
combination of, checked defensively — nested `attributes` dict OR flat
dotted keys, both handled):

    {
        "context.trace_id": "...",   # or nested under "context": {"trace_id": ...}
        "context.span_id": "...",
        "parent_id": "..." | null,
        "name": "...",
        "span_kind": "LLM" | "TOOL" | "CHAIN" | "AGENT" | ...,
        "start_time": "...",          # used to order spans within a trace
        "attributes.input.value": "...",
        "attributes.output.value": "...",
        "attributes.llm.output_messages": [{"role": "assistant", "content": "..."}],
        "attributes.tool.name": "...",
        "attributes.tool.parameters": {...}
    }

One raw_record here = the full list of spans sharing one trace_id (grouping
happens in iter_raw_records, not to_trace).

Turn reconstruction (best-effort, documented so you can judge if it fits
your traces): every LLM-kind span becomes one assistant turn, its output
message content as the turn's content; every TOOL-kind span is attached as
a tool_result on the nearest preceding LLM-kind span (matched by parent_id
where available, else by chronological adjacency); the root span's input
value becomes the leading user turn. If your agent's span structure doesn't
match this (e.g. multiple LLM spans per logical turn, or a different
span_kind vocabulary), this mapping will be wrong for your traces — treat it
as a starting point to adjust, not a finished integration.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterator

from evallib.adapters.base import TraceAdapter
from evallib.schema import Trace


def _get(span: dict[str, Any], dotted_key: str) -> Any:
    """Looks up `dotted_key` first as a literal flat key (Phoenix dataframe
    columns are often literally named with dots), then by walking a nested
    dict along the same path (in case the export preserved nesting)."""
    if dotted_key in span:
        return span[dotted_key]
    node: Any = span
    for part in dotted_key.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def _trace_id(span: dict[str, Any]) -> str | None:
    return _get(span, "context.trace_id") or span.get("trace_id")


def _span_id(span: dict[str, Any]) -> str | None:
    return _get(span, "context.span_id") or span.get("span_id")


class PhoenixAdapter(TraceAdapter):
    """Reads a JSON file of Phoenix span records and groups them into
    Trace objects by trace_id. See module docstring for assumptions."""

    def iter_raw_records(self, source: str | Path) -> Iterator[list[dict[str, Any]]]:
        data = json.loads(Path(source).read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError(
                f"{source}: expected a top-level JSON array of Phoenix span "
                f"records, got {type(data).__name__}."
            )

        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for span in data:
            tid = _trace_id(span)
            if not tid:
                raise ValueError(f"Phoenix span has no trace_id: {span!r}")
            grouped[tid].append(span)

        for spans in grouped.values():
            spans.sort(key=lambda s: s.get("start_time") or "")
            yield spans

    def to_trace(self, raw_record: list[dict[str, Any]]) -> Trace:
        spans = raw_record
        if not spans:
            raise ValueError("empty span group cannot become a Trace")

        trace_id = _trace_id(spans[0])
        root_input = _get(spans[0], "attributes.input.value") or ""

        turns: list[dict[str, Any]] = []
        if root_input:
            turns.append({"role": "user", "content": str(root_input)})

        span_id_to_turn_index: dict[str, int] = {}
        for span in spans:
            kind = (span.get("span_kind") or "").upper()

            if kind == "LLM":
                output_messages = _get(span, "attributes.llm.output_messages")
                if output_messages:
                    content = output_messages[-1].get("content", "")
                else:
                    content = str(_get(span, "attributes.output.value") or "")
                turns.append(
                    {"role": "assistant", "content": content, "tool_calls": [],
                     "tool_results": [], "retrieved_docs": []}
                )
                sid = _span_id(span)
                if sid:
                    span_id_to_turn_index[sid] = len(turns) - 1

            elif kind == "TOOL":
                parent_id = span.get("parent_id")
                target_idx = span_id_to_turn_index.get(parent_id) if parent_id else None
                if target_idx is None and turns and turns[-1]["role"] == "assistant":
                    target_idx = len(turns) - 1
                if target_idx is not None:
                    tool_name = _get(span, "attributes.tool.name") or span.get("name", "unknown")
                    call_id = _span_id(span) or f"tool-{len(turns[target_idx]['tool_calls'])}"
                    turns[target_idx]["tool_calls"].append(
                        {
                            "tool_call_id": call_id,
                            "tool_name": tool_name,
                            "arguments": _get(span, "attributes.tool.parameters") or {},
                        }
                    )
                    turns[target_idx]["tool_results"].append(
                        {
                            "tool_call_id": call_id,
                            "output": _get(span, "attributes.output.value"),
                            "is_error": (span.get("status_code") or "OK") != "OK",
                        }
                    )
                # A TOOL span with no attachable parent is dropped rather
                # than guessed at — better a gap you notice than a wrong
                # attribution you don't.

        assistant_turns = [t for t in turns if t["role"] == "assistant"]
        final_response = assistant_turns[-1]["content"] if assistant_turns else ""

        return Trace.model_validate(
            {
                "query_id": str(trace_id),
                "turns": turns,
                "final_response": final_response,
                "metadata": {"source": "arize_phoenix"},
            }
        )
