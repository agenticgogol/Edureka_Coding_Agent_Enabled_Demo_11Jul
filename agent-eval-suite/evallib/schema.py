"""Data contracts shared by every eval-suite skill.

Every model here round-trips losslessly to a single line of JSONL via
`model_dump_json()` / `model_validate_json()`. Skills must not invent ad hoc
dict shapes for traces, labels, judge output, or metrics — import the model
from here instead.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    """Base for all schema models: reject unknown fields so a typo or a
    silently-dropped upstream field fails loudly at ingestion, not three
    skills later."""

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Trace
# ---------------------------------------------------------------------------


class Role(str, Enum):
    system = "system"
    user = "user"
    assistant = "assistant"
    tool = "tool"


class ToolCall(StrictModel):
    tool_call_id: str
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolResult(StrictModel):
    tool_call_id: str
    output: Any
    is_error: bool = False


class RetrievedDoc(StrictModel):
    doc_id: str
    content: str
    score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Turn(StrictModel):
    role: Role
    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_results: list[ToolResult] = Field(default_factory=list)
    retrieved_docs: list[RetrievedDoc] = Field(default_factory=list)


class Trace(StrictModel):
    query_id: str
    dimension_tuple: tuple[str, ...] = Field(default_factory=tuple)
    turns: list[Turn]
    final_response: str
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Open coding (qualitative pass over traces)
# ---------------------------------------------------------------------------


class OpenCode(StrictModel):
    trace_id: str
    annotator: str
    first_failure_turn_index: int | None = None
    note: str = ""
    is_failure: bool


# ---------------------------------------------------------------------------
# Axial coding (taxonomy synthesized from open codes)
# ---------------------------------------------------------------------------


class Severity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class AxialCode(StrictModel):
    code_id: str
    label: str
    definition: str
    member_trace_ids: list[str] = Field(default_factory=list)
    count: int
    severity: Severity

    def model_post_init(self, __context: Any) -> None:
        if self.count != len(self.member_trace_ids):
            raise ValueError(
                f"count ({self.count}) must equal len(member_trace_ids) "
                f"({len(self.member_trace_ids)}) for code_id={self.code_id!r}"
            )


# ---------------------------------------------------------------------------
# Labels (human ground truth, split for judge calibration)
# ---------------------------------------------------------------------------


Split = Literal["train", "dev", "test"]

LabelSource = Literal["human", "ai_confirmed", "ai_edited"]


class LabelRecord(StrictModel):
    trace_id: str
    failure_mode_id: str
    human_label: bool
    split: Split
    annotator: str = Field(
        default="unspecified",
        description=(
            "Who produced human_label. Required in practice by every writer "
            "(the default exists only for schema-evolution safety, same as "
            "label_source) — a second annotator's rows for the same "
            "(trace_id, failure_mode_id) must carry a distinct name, or "
            "judge-align-new's kappa computation has no way to tell the two "
            "independent label sets apart within one file."
        ),
    )
    label_source: LabelSource = Field(
        default="human",
        description=(
            'Provenance of human_label: "human" = independently supplied '
            'with no AI hint shown; "ai_confirmed" = an optional AI-hint '
            "mode proposed a label and the human accepted it as-is; "
            '"ai_edited" = the human changed the AI\'s proposed label. The '
            "bool itself is always the human's final answer either way — "
            "this field exists purely so kappa/TPR/TNR consumers can "
            "detect when a nominally-human label set was AI-anchored."
        ),
    )


# ---------------------------------------------------------------------------
# Judge output
# ---------------------------------------------------------------------------


class JudgeResult(StrictModel):
    trace_id: str
    failure_mode_id: str
    judge_label: bool
    critique: str


# ---------------------------------------------------------------------------
# Metrics (judge calibration against the held-out test split)
# ---------------------------------------------------------------------------


class MetricsRecord(StrictModel):
    failure_mode_id: str
    n_test: int
    tpr: float = Field(ge=0.0, le=1.0)
    tnr: float = Field(ge=0.0, le=1.0)
    p_observed: float = Field(ge=0.0, le=1.0)
    theta_hat: float = Field(ge=0.0, le=1.0)
    ci_low: float = Field(ge=0.0, le=1.0)
    ci_high: float = Field(ge=0.0, le=1.0)

    def model_post_init(self, __context: Any) -> None:
        if self.ci_low > self.ci_high:
            raise ValueError(
                f"ci_low ({self.ci_low}) must be <= ci_high ({self.ci_high})"
            )


# ---------------------------------------------------------------------------
# Metrics history (append-only log behind eval-dashboard-new)
# ---------------------------------------------------------------------------

RunType = Literal["calibration", "ci"]
RegressionStatus = Literal["ok", "regressed", "no_baseline", "skipped_uncalibrated"]


class MetricsHistoryRecord(StrictModel):
    """One row per calibration run (judge-align-new step d/e) or CI gate run
    (eval-ci-new / run_judge_ci.py + check_regression.py). Appended, never
    overwritten — `evals/results/metrics.json` and `ci_run_latest.json`
    remain the "current value" files; this is the full history behind them,
    and what `eval-dashboard-new` renders `evals/results/dashboard.html`
    from. Written via `evallib.jsonl.append_jsonl`, one call per run."""

    run_id: str  # unique per row, e.g. f"{timestamp}-{failure_mode_id}-{run_type}"
    timestamp: str  # ISO-8601 UTC, e.g. datetime.now(timezone.utc).isoformat()
    run_type: RunType
    failure_mode_id: str
    method: Literal["code", "judge"]

    # calibration-run fields (judge-align-new step d/e) — required when run_type == "calibration"
    tpr: float | None = Field(default=None, ge=0.0, le=1.0)
    tnr: float | None = Field(default=None, ge=0.0, le=1.0)
    p_observed: float | None = Field(default=None, ge=0.0, le=1.0)
    theta_hat: float | None = Field(default=None, ge=0.0, le=1.0)
    ci_low: float | None = Field(default=None, ge=0.0, le=1.0)
    ci_high: float | None = Field(default=None, ge=0.0, le=1.0)
    n_test: int | None = None
    judge_model_id: str | None = None

    # CI-run fields (eval-ci-new) — required when run_type == "ci"
    ci_rate: float | None = Field(
        default=None, ge=0.0, le=1.0,
        description="The positive/failure rate this CI run measured on the golden set — "
        "1-pass_rate for a code eval, p_observed for a judge.",
    )
    baseline_rate: float | None = Field(
        default=None, ge=0.0, le=1.0,
        description="The metrics.json theta_hat this run was compared against, if any.",
    )
    regression_status: RegressionStatus | None = None
    n_golden: int | None = None

    notes: str = ""

    def model_post_init(self, __context: Any) -> None:
        if self.run_type == "calibration":
            if self.tpr is None or self.tnr is None or self.theta_hat is None:
                raise ValueError("run_type='calibration' requires tpr, tnr, and theta_hat")
            if self.ci_low is not None and self.ci_high is not None and self.ci_low > self.ci_high:
                raise ValueError(
                    f"ci_low ({self.ci_low}) must be <= ci_high ({self.ci_high})"
                )
        if self.run_type == "ci" and self.regression_status is None:
            raise ValueError("run_type='ci' requires regression_status")
