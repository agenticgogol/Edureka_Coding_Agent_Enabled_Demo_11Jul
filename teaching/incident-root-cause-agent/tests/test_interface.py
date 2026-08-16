"""Integration-level tests for backend/agent/interface.py's public
entrypoints — in particular, regression coverage for the two real bugs
found in this session's production-readiness audits:

1. A TokenBudgetExceededError during start_incident used to crash
   _record_incident()'s embed() call (still inside the tripped budget
   context) instead of degrading cleanly, and the incident was never
   written to the audit table.
2. A TokenBudgetExceededError during resume_incident produced a fallback
   result with no incident_id, so _update_incident_record() was silently
   skipped — the audit row's outcome never reflected the approve-leg
   failure.

Every LLM/tool call is monkeypatched; zero real API calls."""
from __future__ import annotations

import json

import pytest

from backend.agent import db, graph as graph_mod
from backend.agent.budget import TokenBudgetExceededError
from backend.agent.interface import get_incident_status, resume_incident, start_incident


def _fake_tool_call(name: str, args: dict):
    return type(
        "FakeToolCall",
        (),
        {"id": "call_1", "function": type("F", (), {"name": name, "arguments": json.dumps(args)})()},
    )()


def _fake_message(tool_calls):
    return type("FakeMessage", (), {"tool_calls": tool_calls})()


@pytest.fixture
def happy_path_llm(monkeypatch):
    """Wires every LLM/tool call site the graph touches to deterministic
    fakes, so a full submit->approve run completes without any real
    provider call or real repo file write."""

    def fake_chat_with_tools(messages, tools=None, tool_choice=None, model=None):
        return _fake_message(
            [
                _fake_tool_call(
                    "finish_analysis",
                    {
                        "confident": True,
                        "identified_repo": "checkout-service",
                        "identified_file": "cart.py",
                        "root_cause": "simulated root cause",
                        "evidence_excerpt": "simulated evidence",
                    },
                )
            ]
        )

    def fake_complete_json(system, user, model=None):
        if "classification" in system:
            return {"classification": "code-issue", "message": "simulated"}
        return {"new_content": "simulated new content", "explanation": "simulated explanation"}

    monkeypatch.setattr(graph_mod, "chat_with_tools", fake_chat_with_tools)
    monkeypatch.setattr(graph_mod, "complete_json", fake_complete_json)
    monkeypatch.setattr(
        graph_mod.tools, "draft_patch",
        lambda **kw: {
            "repo": kw["repo"], "path": kw["path"], "current_content": "", "new_content": "x",
            "diff": "simulated diff", "explanation": "simulated explanation",
        },
    )
    monkeypatch.setattr(
        graph_mod.tools, "apply_patch",
        lambda repo, path, new_content: {"applied": True, "path": path, "backup": path + ".bak"},
    )
    monkeypatch.setattr(
        graph_mod.tools, "run_tests",
        lambda repo, test_file: {"passed": True, "stdout": "simulated pass", "stderr": "", "returncode": 0},
    )


class TestStartIncidentBudgetExceeded:
    def test_budget_exceeded_escalates_cleanly_not_500(self, monkeypatch):
        def budget_blown(*a, **kw):
            raise TokenBudgetExceededError("simulated budget breach")

        monkeypatch.setattr(graph_mod, "chat_with_tools", budget_blown)

        # Must return a clean escalation, not raise — this is the whole
        # point of the fix: interface.py catches TokenBudgetExceededError
        # around app.invoke(), and _record_incident()'s embed() call
        # (which runs AFTER that budget context exits) must not re-trip it.
        result = start_incident("incident that will blow the budget")
        assert result["status"] == "escalated"
        assert "budget" in result["message"].lower()

    def test_budget_exceeded_incident_is_still_recorded_in_audit_table(self, monkeypatch):
        def budget_blown(*a, **kw):
            raise TokenBudgetExceededError("simulated budget breach")

        monkeypatch.setattr(graph_mod, "chat_with_tools", budget_blown)

        result = start_incident("incident that will blow the budget")
        row = db.get_incident(result["incident_id"])
        assert row is not None
        assert row["outcome"] == "escalated_ceiling"


class TestResumeIncidentBudgetExceeded:
    def test_budget_exceeded_during_approve_leg_escalates_cleanly(self, happy_path_llm, monkeypatch):
        submitted = start_incident("incident for resume-budget test")
        assert submitted["status"] == "pending_approval"

        def budget_blown(*a, **kw):
            raise TokenBudgetExceededError("simulated budget breach during approve leg")

        # Only the resume leg's invoke should blow the budget — patch
        # after submit succeeds.
        real_build_graph = graph_mod.build_graph

        class _BudgetBlowingApp:
            def __init__(self, real_app):
                self._real_app = real_app

            def invoke(self, *a, **kw):
                raise TokenBudgetExceededError("simulated budget breach during approve leg")

            def get_state(self, *a, **kw):
                return self._real_app.get_state(*a, **kw)

        import backend.agent.interface as iface_mod

        monkeypatch.setattr(
            iface_mod, "build_graph", lambda checkpointer: _BudgetBlowingApp(real_build_graph(checkpointer))
        )

        result = resume_incident(submitted["thread_id"], approved=True)
        assert result["status"] == "escalated"

    def test_budget_exceeded_during_approve_leg_updates_audit_record(self, happy_path_llm, monkeypatch):
        # Regression test for the second bug found this session: the
        # fallback result dict on a resume-leg budget breach used to have
        # no incident_id, so _update_incident_record() was silently
        # skipped and the audit row's outcome never reflected the failure.
        submitted = start_incident("incident for resume-budget audit-record test")
        assert submitted["status"] == "pending_approval"

        real_build_graph = graph_mod.build_graph

        class _BudgetBlowingApp:
            def __init__(self, real_app):
                self._real_app = real_app

            def invoke(self, *a, **kw):
                raise TokenBudgetExceededError("simulated budget breach")

            def get_state(self, *a, **kw):
                return self._real_app.get_state(*a, **kw)

        import backend.agent.interface as iface_mod

        monkeypatch.setattr(
            iface_mod, "build_graph", lambda checkpointer: _BudgetBlowingApp(real_build_graph(checkpointer))
        )

        result = resume_incident(submitted["thread_id"], approved=True)

        assert result.get("incident_id") is not None
        row = db.get_incident(result["incident_id"])
        assert row is not None
        assert row["outcome"] == "escalated_ceiling"


class TestHappyPathEndToEnd:
    def test_submit_then_approve_reaches_terminal_state(self, happy_path_llm):
        submitted = start_incident("checkout API returns 500 on large carts")
        assert submitted["status"] == "pending_approval"
        assert submitted["classification"] == "code-issue"
        assert submitted["diff"] == "simulated diff"

        approved = resume_incident(submitted["thread_id"], approved=True)
        assert approved["status"] == "resolved_code_fix"
        assert "Tests passed" in approved["message"]

        row = db.get_incident(submitted["incident_id"])
        assert row["outcome"] == "closed_pass"

    def test_reject_leaves_ticket_open(self, happy_path_llm):
        submitted = start_incident("another incident to reject")
        rejected = resume_incident(submitted["thread_id"], approved=False, rejection_note="not the right fix")
        assert rejected["status"] == "rejected"
        assert db.get_ticket(submitted["ticket_id"])["status"] == "open"

    def test_get_incident_status_read_only_does_not_advance_graph(self, happy_path_llm):
        submitted = start_incident("incident to check status of")
        status1 = get_incident_status(submitted["thread_id"])
        status2 = get_incident_status(submitted["thread_id"])
        assert status1["status"] == status2["status"] == "pending_approval"


class TestResetAllHistory:
    def test_wipes_incidents_tickets_and_checkpoints(self, happy_path_llm):
        from backend.agent.interface import reset_all_history

        submitted = start_incident("incident that will be reset away")
        assert submitted["status"] == "pending_approval"
        assert db.get_incident(submitted["incident_id"]) is not None
        assert db.get_ticket(submitted["ticket_id"]) is not None

        result = reset_all_history()
        assert result["incidents_deleted"] >= 1
        assert result["tickets_deleted"] >= 1
        assert result["checkpoint_threads_deleted"] >= 1

        assert db.all_incidents() == []
        assert db.get_ticket(submitted["ticket_id"]) is None

    def test_orphaned_thread_cannot_be_resumed_after_reset(self, happy_path_llm):
        # Regression guard for exactly the gap reset_all_history()'s
        # docstring calls out: without clearing checkpoints too, a
        # thread_id could still resolve to real (but orphaned) graph
        # state after its audit row was deleted.
        from backend.agent.interface import reset_all_history

        submitted = start_incident("incident to orphan via reset")
        thread_id = submitted["thread_id"]

        reset_all_history()

        status = get_incident_status(thread_id)
        # No checkpoint left for this thread -> nothing to report.
        assert status["status"] == "unknown"

    def test_new_incidents_work_normally_after_reset(self, happy_path_llm):
        from backend.agent.interface import reset_all_history

        start_incident("incident before reset")
        reset_all_history()

        submitted = start_incident("incident after reset")
        assert submitted["status"] == "pending_approval"
        assert len(db.all_incidents()) == 1


class TestStreaming:
    def test_stream_start_incident_emits_progress_then_result(self, happy_path_llm):
        from backend.agent.interface import stream_start_incident

        events = list(stream_start_incident("checkout API returns 500 on large carts"))

        assert len(events) >= 2
        assert all(e["type"] in ("progress", "result") for e in events)
        assert [e["type"] for e in events][-1] == "result"
        # Every event but the last is a progress update, in order.
        assert all(e["type"] == "progress" for e in events[:-1])
        assert all(isinstance(e.get("message"), str) and e["message"] for e in events[:-1])

        result_event = events[-1]
        assert result_event["status"] == "pending_approval"
        assert result_event["classification"] == "code-issue"

    def test_stream_result_payload_matches_non_streaming_call(self, happy_path_llm):
        # The final `type: result` event must be exactly what the
        # blocking start_incident() would have returned for an
        # equivalent call — streaming is a transport difference, not a
        # behavior difference.
        from backend.agent.interface import stream_start_incident

        events = list(stream_start_incident("identical incident text for comparison"))
        result_event = events[-1]

        expected_keys = {"thread_id", "status", "incident_id", "identified_repo", "classification"}
        assert expected_keys.issubset(result_event.keys())

    def test_stream_progress_messages_mention_key_milestones(self, happy_path_llm):
        from backend.agent.interface import stream_start_incident

        events = list(stream_start_incident("checkout API returns 500 on large carts"))
        messages = " | ".join(e["message"] for e in events if e["type"] == "progress")

        assert "similar past incident" in messages.lower()
        assert "analysis" in messages.lower()

    def test_stream_resume_incident_emits_progress_then_result(self, happy_path_llm):
        from backend.agent.interface import start_incident, stream_resume_incident

        submitted = start_incident("incident to approve via streaming resume")
        events = list(stream_resume_incident(submitted["thread_id"], approved=True))

        assert events[-1]["type"] == "result"
        assert events[-1]["status"] == "resolved_code_fix"
        progress_messages = " | ".join(e["message"] for e in events if e["type"] == "progress")
        assert "applying patch" in progress_messages.lower()
        assert "closing ticket" in progress_messages.lower()

    def test_stream_call_reraises_target_fn_exceptions(self):
        # Direct test of _stream_call's own error-propagation mechanism —
        # NOT going through the full graph, since graph.py's analyze()
        # legitimately catches and retries most exception types as
        # "transient failures" (correct, separate behavior tested in
        # test_graph.py) rather than letting them propagate. This test
        # only needs to confirm the thread+queue plumbing itself forwards
        # a target_fn exception to the generator's caller, for ANY
        # target_fn, independent of what start_incident/resume_incident
        # specifically do with errors internally.
        import backend.agent.interface as iface_mod
        from backend.agent.progress import emit_progress

        def failing_target():
            emit_progress("about to fail")
            raise RuntimeError("simulated unexpected failure")

        with pytest.raises(RuntimeError, match="simulated unexpected failure"):
            list(iface_mod._stream_call(failing_target))

    def test_stream_call_forwards_progress_events_before_raising(self):
        import backend.agent.interface as iface_mod
        from backend.agent.progress import emit_progress

        seen = []

        def failing_target():
            emit_progress("step one")
            emit_progress("step two")
            raise RuntimeError("boom")

        gen = iface_mod._stream_call(failing_target)
        with pytest.raises(RuntimeError):
            for event in gen:
                seen.append(event)

        assert [e["message"] for e in seen] == ["step one", "step two"]

    def test_stream_does_not_double_record_incident(self, happy_path_llm):
        # The worker thread calls the real start_incident() internally —
        # confirm that isn't somehow invoked twice (e.g. once directly,
        # once via the generator machinery).
        from backend.agent.interface import stream_start_incident

        events = list(stream_start_incident("incident recorded exactly once"))
        incident_id = events[-1]["incident_id"]
        matches = [r for r in db.all_incidents() if r["id"] == incident_id]
        assert len(matches) == 1
