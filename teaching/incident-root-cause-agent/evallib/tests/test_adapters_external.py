"""Tests for the Braintrust and Phoenix adapters, against hand-built
fixtures matching each adapter's documented assumed shape (not live API
responses — see each adapter's module docstring for the caveat)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from evallib.adapters import BraintrustAdapter, PhoenixAdapter, TraceAdapter
from evallib.schema import Trace

# ---------------------------------------------------------------------------
# BraintrustAdapter
# ---------------------------------------------------------------------------

BRAINTRUST_ROWS = [
    {
        "id": "bt-1",
        "input": "What's my order status?",
        "output": "Your order ships tomorrow.",
        "metadata": {"tool_calls": [], "tool_results": []},
        "tags": ["support"],
    },
    {
        "id": "bt-2",
        "root_span_id": "root-2",
        "input": [
            {"role": "user", "content": "Can I get a refund?"},
            {"role": "assistant", "content": "Let me check your order."},
            {"role": "user", "content": "It's order 555."},
        ],
        "output": {"role": "assistant", "content": "Refund issued for order 555."},
        "metadata": {},
    },
]


@pytest.fixture
def braintrust_file(tmp_path: Path) -> Path:
    path = tmp_path / "braintrust_export.json"
    path.write_text(json.dumps(BRAINTRUST_ROWS), encoding="utf-8")
    return path


def test_braintrust_adapter_is_a_trace_adapter() -> None:
    assert issubclass(BraintrustAdapter, TraceAdapter)


def test_braintrust_adapter_two_turn_row(braintrust_file: Path) -> None:
    traces = BraintrustAdapter().normalize(braintrust_file)
    assert len(traces) == 2
    first = traces[0]
    assert isinstance(first, Trace)
    assert first.query_id == "bt-1"
    assert [t.role.value for t in first.turns] == ["user", "assistant"]
    assert first.final_response == "Your order ships tomorrow."


def test_braintrust_adapter_multi_turn_input_list(braintrust_file: Path) -> None:
    traces = BraintrustAdapter().normalize(braintrust_file)
    second = traces[1]
    assert second.query_id == "root-2"  # root_span_id preferred over id
    assert len(second.turns) == 4  # 3 from input list + 1 assistant output
    assert second.final_response == "Refund issued for order 555."


def test_braintrust_adapter_missing_id_raises(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps([{"input": "hi", "output": "hello"}]), encoding="utf-8")
    with pytest.raises(ValueError):
        BraintrustAdapter().normalize(path)


def test_braintrust_adapter_non_array_raises(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"events": []}), encoding="utf-8")
    with pytest.raises(ValueError):
        list(BraintrustAdapter().iter_raw_records(path))


# ---------------------------------------------------------------------------
# PhoenixAdapter
# ---------------------------------------------------------------------------

PHOENIX_SPANS = [
    {
        "context.trace_id": "trace-1",
        "context.span_id": "span-root",
        "parent_id": None,
        "name": "agent",
        "span_kind": "AGENT",
        "start_time": "2026-01-01T00:00:00Z",
        "attributes.input.value": "Refund my order please",
    },
    {
        "context.trace_id": "trace-1",
        "context.span_id": "span-llm-1",
        "parent_id": "span-root",
        "name": "llm_call",
        "span_kind": "LLM",
        "start_time": "2026-01-01T00:00:01Z",
        "attributes.llm.output_messages": [{"role": "assistant", "content": "Checking your order..."}],
    },
    {
        "context.trace_id": "trace-1",
        "context.span_id": "span-tool-1",
        "parent_id": "span-llm-1",
        "name": "lookup_order",
        "span_kind": "TOOL",
        "start_time": "2026-01-01T00:00:02Z",
        "attributes.tool.name": "lookup_order",
        "attributes.tool.parameters": {"order_id": "ORD-1"},
        "attributes.output.value": {"status": "eligible"},
        "status_code": "OK",
    },
    {
        "context.trace_id": "trace-1",
        "context.span_id": "span-llm-2",
        "parent_id": "span-root",
        "name": "llm_call",
        "span_kind": "LLM",
        "start_time": "2026-01-01T00:00:03Z",
        "attributes.llm.output_messages": [{"role": "assistant", "content": "Refund issued."}],
    },
]


@pytest.fixture
def phoenix_file(tmp_path: Path) -> Path:
    path = tmp_path / "phoenix_export.json"
    path.write_text(json.dumps(PHOENIX_SPANS), encoding="utf-8")
    return path


def test_phoenix_adapter_is_a_trace_adapter() -> None:
    assert issubclass(PhoenixAdapter, TraceAdapter)


def test_phoenix_adapter_groups_spans_into_one_trace(phoenix_file: Path) -> None:
    traces = PhoenixAdapter().normalize(phoenix_file)
    assert len(traces) == 1
    trace = traces[0]
    assert isinstance(trace, Trace)
    assert trace.query_id == "trace-1"


def test_phoenix_adapter_reconstructs_turns_and_tool_attachment(phoenix_file: Path) -> None:
    trace = PhoenixAdapter().normalize(phoenix_file)[0]
    roles = [t.role.value for t in trace.turns]
    assert roles == ["user", "assistant", "assistant"]
    assert trace.turns[0].content == "Refund my order please"
    # tool call/result attached to the first LLM turn (its parent)
    assert len(trace.turns[1].tool_calls) == 1
    assert trace.turns[1].tool_calls[0].tool_name == "lookup_order"
    assert trace.turns[1].tool_results[0].output == {"status": "eligible"}
    assert trace.final_response == "Refund issued."


def test_phoenix_adapter_missing_trace_id_raises(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps([{"name": "x", "span_kind": "LLM"}]), encoding="utf-8")
    with pytest.raises(ValueError):
        list(PhoenixAdapter().iter_raw_records(path))


def test_phoenix_adapter_non_array_raises(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"spans": []}), encoding="utf-8")
    with pytest.raises(ValueError):
        list(PhoenixAdapter().iter_raw_records(path))
