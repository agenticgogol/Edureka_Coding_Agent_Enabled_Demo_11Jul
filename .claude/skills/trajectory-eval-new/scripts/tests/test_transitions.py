from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from transitions import (
    build_transition_matrix,
    earliest_divergence,
    failure_divergence_report,
    most_common_divergence_state,
    state_sequence_from_trace_dict,
)


def test_state_sequence_plain_turns() -> None:
    trace = {
        "turns": [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
    }
    assert state_sequence_from_trace_dict(trace) == ["user_msg", "assistant_msg"]


def test_state_sequence_tool_call_and_result() -> None:
    trace = {
        "turns": [
            {"role": "user", "content": "refund?"},
            {
                "role": "assistant",
                "content": "checking",
                "tool_calls": [{"tool_call_id": "c1", "tool_name": "lookup_order"}],
                "tool_results": [{"tool_call_id": "c1", "output": {}, "is_error": False}],
            },
        ]
    }
    assert state_sequence_from_trace_dict(trace) == [
        "user_msg",
        "tool_call:lookup_order",
        "tool_result:ok",
    ]


def test_state_sequence_tool_error() -> None:
    trace = {
        "turns": [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"tool_call_id": "c1", "tool_name": "issue_refund"}],
                "tool_results": [{"tool_call_id": "c1", "output": "boom", "is_error": True}],
            }
        ]
    }
    assert state_sequence_from_trace_dict(trace) == [
        "tool_call:issue_refund",
        "tool_result:error",
    ]


def test_earliest_divergence_found() -> None:
    reference = ["user_msg", "tool_call:check", "tool_result:ok", "assistant_msg"]
    candidate = ["user_msg", "tool_call:issue_refund", "tool_result:ok", "assistant_msg"]
    assert earliest_divergence(candidate, reference) == 1


def test_earliest_divergence_none_when_prefix_matches() -> None:
    reference = ["user_msg", "tool_call:check", "tool_result:ok", "assistant_msg"]
    candidate = ["user_msg", "tool_call:check"]  # shorter, but matches within shared range
    assert earliest_divergence(candidate, reference) is None


def test_earliest_divergence_at_start() -> None:
    reference = ["user_msg", "assistant_msg"]
    candidate = ["system_msg", "assistant_msg"]
    assert earliest_divergence(candidate, reference) == 0


def test_build_transition_matrix_counts() -> None:
    sequences = [
        ["a", "b", "c"],
        ["a", "b", "d"],
    ]
    matrix = build_transition_matrix(sequences)
    assert matrix[("a", "b")] == 2
    assert matrix[("b", "c")] == 1
    assert matrix[("b", "d")] == 1


def test_failure_divergence_report_and_most_common_state() -> None:
    reference = ["user_msg", "tool_call:check", "tool_result:ok", "assistant_msg"]
    failed = {
        "t1": ["user_msg", "tool_call:issue_refund", "tool_result:ok", "assistant_msg"],
        "t2": ["user_msg", "tool_call:issue_refund", "tool_result:error"],
        "t3": ["user_msg", "tool_call:check", "tool_result:ok", "assistant_msg"],  # no divergence
    }
    report = failure_divergence_report(failed, reference)
    assert report == {"t1": 1, "t2": 1, "t3": None}

    ranked = most_common_divergence_state(report, failed)
    assert ranked[0] == ("tool_call:issue_refund", 2)
