"""Graph state shape.

Per `06_context_engineering.md`'s "structured note-taking" pruning
strategy: this holds distilled findings only (identified repo/file, root
cause, evidence excerpts, classification, drafted patch) — never a raw
verbatim transcript of every tool call. This is exactly what gets
reconstructed for the model on resume after the approval interrupt.

This module is internal — the backend should not import `AgentState`
directly; use `interface.py`'s `start_incident` / `resume_incident`.
"""
from __future__ import annotations

from typing import Literal, TypedDict


class DraftedPatch(TypedDict, total=False):
    repo: str
    path: str
    new_content: str
    diff: str
    explanation: str


class AgentState(TypedDict, total=False):
    # Task input
    incident_id: str
    incident_text: str

    # Precedent check (stage 6: on-demand, single best match only)
    matched_precedent: dict | None

    # Analysis leg findings (structured notes, per stage 6's pruning strategy)
    identified_repo: str | None
    identified_file: str | None
    root_cause: str | None
    evidence_excerpt: str | None
    classification: Literal["code-issue", "infra-issue", "unresolved"] | None
    infra_message: str | None

    # Step-ceiling bookkeeping (stage 7)
    analysis_tool_calls: int
    execution_tool_calls: int
    escalated: bool
    escalation_reason: str | None

    # Code-issue path
    drafted_patch: DraftedPatch | None
    ticket_id: str | None
    draft_retry_used: bool

    # Human approval (interrupt payload / resume decision)
    approval_status: Literal["pending", "approved", "rejected"] | None
    rejection_note: str | None

    # Post-approval execution leg
    apply_result: dict | None
    test_result: dict | None

    # Terminal outcome
    outcome: Literal[
        "infra_resolved",
        "closed_pass",
        "rejected",
        "test_failed_after_retry",
        "escalated_ceiling",
        "error",
    ] | None
    final_message: str | None
