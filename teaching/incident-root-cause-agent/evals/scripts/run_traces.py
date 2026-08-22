"""Self-drive runner for eval-dataset-new: calls the real agent
(backend.agent.interface.stream_start_incident) for each generated query
and writes evallib.schema.Trace rows to evals/traces.jsonl.

Uses the streaming entrypoint (not the plain start_incident) purely to
recover intermediate tool-call signal for Trace.turns — interface.py's
blocking start_incident only returns the final public view, and
progress.py's emit_progress() messages are the only real (non-fabricated)
record of which tools ran, in what order, with what arguments, available
without editing agent code. The final `type: result` event's payload
becomes the trace's last turn and final_response either way.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(PROJECT_ROOT.parent.parent / ".env")

from backend.agent.interface import stream_start_incident  # noqa: E402

sys.path.insert(0, str(PROJECT_ROOT.parent.parent))
from evallib.schema import Role, Trace, Turn  # noqa: E402
from evallib.jsonl import write_jsonl, read_jsonl  # noqa: E402

QUERIES_PATH = PROJECT_ROOT / "evals" / "queries.jsonl"
TUPLES_PATH = PROJECT_ROOT / "evals" / "dimension_tuples.jsonl"
TRACES_PATH = PROJECT_ROOT / "evals" / "traces.jsonl"

_TOOL_PATTERNS = [
    (re.compile(r"^Checking for similar past incidents"), "search_similar_incidents"),
    (re.compile(r"^Listing available repositories"), "list_repos"),
    (re.compile(r"^Searching (\S+) for"), "search_code"),
    (re.compile(r"^Reading (\S+)/(\S+)"), "read_file"),
    (re.compile(r"^Classifying incident"), "classify"),
    (re.compile(r"^Drafting patch"), "draft_patch"),
    (re.compile(r"^Running tests"), "run_tests"),
]


def _infer_tool_name(message: str) -> str | None:
    for pattern, name in _TOOL_PATTERNS:
        if pattern.match(message):
            return name
    return None


def main() -> None:
    tuples_by_id = {}
    for line in TUPLES_PATH.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        tuples_by_id[row["tuple_id"]] = row["dimension_tuple"]

    queries = []
    for line in QUERIES_PATH.read_text().splitlines():
        if not line.strip():
            continue
        queries.append(json.loads(line))

    existing_traces = list(read_jsonl(Trace, TRACES_PATH)) if TRACES_PATH.exists() else []
    existing_ids = {t.query_id for t in existing_traces}

    new_traces: list[Trace] = []
    for i, q in enumerate(queries, start=1):
        tuple_id = q["tuple_id"]
        if tuple_id in existing_ids:
            print(f"[{i}/{len(queries)}] {tuple_id}: already in traces.jsonl, skipping")
            continue

        query_text = q["query"]
        print(f"[{i}/{len(queries)}] {tuple_id}: running...")

        turns: list[Turn] = [Turn(role=Role.user, content=query_text)]
        final_payload: dict | None = None

        for event in stream_start_incident(query_text):
            if event.get("type") == "progress":
                message = event.get("message", "")
                tool_name = _infer_tool_name(message)
                turns.append(
                    Turn(
                        role=Role.assistant if tool_name is None else Role.tool,
                        content=message,
                    )
                )
            elif event.get("type") == "result":
                final_payload = {k: v for k, v in event.items() if k != "type"}

        if final_payload is None:
            raise RuntimeError(f"{tuple_id}: no result event received")

        final_response = final_payload.get("message") or json.dumps(final_payload, default=str)
        turns.append(Turn(role=Role.assistant, content=json.dumps(final_payload, default=str)))

        trace = Trace(
            query_id=tuple_id,
            dimension_tuple=tuple(tuples_by_id.get(tuple_id, ())),
            turns=turns,
            final_response=final_response,
            metadata={"generated_query": True, "raw_result": final_payload},
        )
        new_traces.append(trace)
        print(f"    -> status={final_payload.get('status')} repo={final_payload.get('identified_repo')}")

    all_traces = existing_traces + new_traces
    write_jsonl(all_traces, TRACES_PATH)
    print(f"\nwrote {len(all_traces)} total traces ({len(new_traces)} new) to {TRACES_PATH}")


if __name__ == "__main__":
    main()
