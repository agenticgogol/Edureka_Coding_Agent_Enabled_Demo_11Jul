"""Round-trip tests and one malformed-input test per schema model."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from evallib.jsonl import read_jsonl, write_jsonl
from evallib.schema import (
    AxialCode,
    JudgeResult,
    LabelRecord,
    MetricsRecord,
    OpenCode,
    RetrievedDoc,
    Role,
    Severity,
    ToolCall,
    ToolResult,
    Trace,
    Turn,
)

# ---------------------------------------------------------------------------
# Fixtures: one valid instance per model
# ---------------------------------------------------------------------------


@pytest.fixture
def trace() -> Trace:
    return Trace(
        query_id="q-1",
        dimension_tuple=("billing", "refund"),
        turns=[
            Turn(role=Role.user, content="Can I get a refund?"),
            Turn(
                role=Role.assistant,
                content="Let me check.",
                tool_calls=[
                    ToolCall(
                        tool_call_id="call-1",
                        tool_name="lookup_order",
                        arguments={"order_id": "o-1"},
                    )
                ],
                tool_results=[
                    ToolResult(tool_call_id="call-1", output={"status": "eligible"})
                ],
                retrieved_docs=[
                    RetrievedDoc(doc_id="d-1", content="refund policy...", score=0.9)
                ],
            ),
        ],
        final_response="Yes, you're eligible for a refund.",
        metadata={"channel": "chat"},
    )


@pytest.fixture
def open_code() -> OpenCode:
    return OpenCode(
        trace_id="q-1",
        annotator="alice",
        first_failure_turn_index=1,
        note="Assistant skipped verifying the order date.",
        is_failure=True,
    )


@pytest.fixture
def axial_code() -> AxialCode:
    return AxialCode(
        code_id="ax-1",
        label="skipped-verification",
        definition="Assistant grants a refund without checking eligibility.",
        member_trace_ids=["q-1", "q-2"],
        count=2,
        severity=Severity.high,
    )


@pytest.fixture
def label_record() -> LabelRecord:
    return LabelRecord(
        trace_id="q-1", failure_mode_id="ax-1", human_label=True, split="test"
    )


@pytest.fixture
def judge_result() -> JudgeResult:
    return JudgeResult(
        trace_id="q-1",
        failure_mode_id="ax-1",
        judge_label=True,
        critique="No eligibility check performed before promising a refund.",
    )


@pytest.fixture
def metrics_record() -> MetricsRecord:
    return MetricsRecord(
        failure_mode_id="ax-1",
        n_test=50,
        tpr=0.82,
        tnr=0.91,
        p_observed=0.2,
        theta_hat=0.18,
        ci_low=0.10,
        ci_high=0.28,
    )


ALL_MODEL_FIXTURES = [
    "trace",
    "open_code",
    "axial_code",
    "label_record",
    "judge_result",
    "metrics_record",
]


# ---------------------------------------------------------------------------
# Round-trip: model -> JSON string -> model, and model -> JSONL file -> model
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fixture_name", ALL_MODEL_FIXTURES)
def test_json_string_round_trip(fixture_name: str, request: pytest.FixtureRequest) -> None:
    instance = request.getfixturevalue(fixture_name)
    model_cls = type(instance)
    round_tripped = model_cls.model_validate_json(instance.model_dump_json())
    assert round_tripped == instance


@pytest.mark.parametrize("fixture_name", ALL_MODEL_FIXTURES)
def test_jsonl_file_round_trip(
    fixture_name: str, request: pytest.FixtureRequest, tmp_path: Path
) -> None:
    instance = request.getfixturevalue(fixture_name)
    model_cls = type(instance)
    path = tmp_path / f"{fixture_name}.jsonl"

    write_jsonl([instance, instance], path)
    loaded = read_jsonl(model_cls, path)

    assert loaded == [instance, instance]
    # File is exactly two lines, each valid standalone JSON.
    lines = path.read_text(encoding="utf-8").strip("\n").split("\n")
    assert len(lines) == 2


# ---------------------------------------------------------------------------
# Malformed input: one case per model
# ---------------------------------------------------------------------------


def test_trace_malformed_missing_final_response() -> None:
    with pytest.raises(ValidationError):
        Trace.model_validate(
            {
                "query_id": "q-1",
                "turns": [{"role": "user", "content": "hi"}],
                # final_response missing
            }
        )


def test_open_code_malformed_bad_is_failure_type() -> None:
    with pytest.raises(ValidationError):
        OpenCode.model_validate(
            {
                "trace_id": "q-1",
                "annotator": "alice",
                "is_failure": "definitely",  # not a bool-coercible value
            }
        )


def test_axial_code_malformed_count_mismatch() -> None:
    with pytest.raises(ValidationError):
        AxialCode.model_validate(
            {
                "code_id": "ax-1",
                "label": "skipped-verification",
                "definition": "...",
                "member_trace_ids": ["q-1", "q-2"],
                "count": 5,  # doesn't match len(member_trace_ids)
                "severity": "high",
            }
        )


def test_label_record_malformed_bad_split() -> None:
    with pytest.raises(ValidationError):
        LabelRecord.model_validate(
            {
                "trace_id": "q-1",
                "failure_mode_id": "ax-1",
                "human_label": True,
                "split": "validation",  # not one of train|dev|test
            }
        )


def test_label_record_label_source_defaults_to_human_for_old_shaped_json() -> None:
    # Records written before label_source existed must still validate.
    record = LabelRecord.model_validate(
        {"trace_id": "q-1", "failure_mode_id": "ax-1", "human_label": True, "split": "dev"}
    )
    assert record.label_source == "human"


def test_label_record_label_source_ai_confirmed_and_ai_edited_round_trip() -> None:
    for source in ("ai_confirmed", "ai_edited"):
        record = LabelRecord(
            trace_id="q-1", failure_mode_id="ax-1", human_label=True, split="dev",
            label_source=source,
        )
        round_tripped = LabelRecord.model_validate_json(record.model_dump_json())
        assert round_tripped.label_source == source


def test_label_record_malformed_bad_label_source() -> None:
    with pytest.raises(ValidationError):
        LabelRecord.model_validate(
            {
                "trace_id": "q-1",
                "failure_mode_id": "ax-1",
                "human_label": True,
                "split": "dev",
                "label_source": "ai_only",  # not one of human|ai_confirmed|ai_edited
            }
        )


def test_label_record_annotator_defaults_for_old_shaped_json() -> None:
    record = LabelRecord.model_validate(
        {"trace_id": "q-1", "failure_mode_id": "ax-1", "human_label": True, "split": "dev"}
    )
    assert record.annotator == "unspecified"


def test_label_record_two_annotators_same_trace_distinguishable() -> None:
    # Two independent annotators labeling the same (trace_id, failure_mode_id)
    # for a kappa computation must remain distinct rows in one file.
    a = LabelRecord(
        trace_id="q-1", failure_mode_id="ax-1", human_label=True, split="dev", annotator="alice",
    )
    b = LabelRecord(
        trace_id="q-1", failure_mode_id="ax-1", human_label=False, split="dev", annotator="bob",
    )
    assert a.annotator != b.annotator
    assert a.human_label != b.human_label
    # Both round-trip independently.
    assert LabelRecord.model_validate_json(a.model_dump_json()) == a
    assert LabelRecord.model_validate_json(b.model_dump_json()) == b


def test_judge_result_malformed_missing_critique() -> None:
    with pytest.raises(ValidationError):
        JudgeResult.model_validate(
            {
                "trace_id": "q-1",
                "failure_mode_id": "ax-1",
                "judge_label": True,
                # critique missing
            }
        )


def test_metrics_record_malformed_ci_out_of_order() -> None:
    with pytest.raises(ValidationError):
        MetricsRecord.model_validate(
            {
                "failure_mode_id": "ax-1",
                "n_test": 50,
                "tpr": 0.8,
                "tnr": 0.9,
                "p_observed": 0.2,
                "theta_hat": 0.18,
                "ci_low": 0.5,
                "ci_high": 0.1,  # ci_high < ci_low
            }
        )


def test_metrics_record_malformed_rate_out_of_range() -> None:
    with pytest.raises(ValidationError):
        MetricsRecord.model_validate(
            {
                "failure_mode_id": "ax-1",
                "n_test": 50,
                "tpr": 1.5,  # out of [0, 1]
                "tnr": 0.9,
                "p_observed": 0.2,
                "theta_hat": 0.18,
                "ci_low": 0.1,
                "ci_high": 0.3,
            }
        )


def test_extra_field_rejected(trace: Trace) -> None:
    payload = trace.model_dump()
    payload["unexpected_field"] = "should not be allowed"
    with pytest.raises(ValidationError):
        Trace.model_validate(payload)
