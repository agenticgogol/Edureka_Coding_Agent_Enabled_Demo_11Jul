"""Unit tests for backend/agent/graph.py — conditional routing functions
(pure, easy to test directly) and the analyze() bounded tool-loop's
control flow (step ceiling, malformed-output retry, transient-failure
retry, and — regression coverage for a real bug found this session — that
TokenBudgetExceededError is propagated immediately rather than retried).
All LLM calls are monkeypatched; zero real API calls anywhere here."""
from __future__ import annotations

import json

import pytest

from backend.agent import graph
from backend.agent.budget import TokenBudgetExceededError


# --- Routing functions: pure, no I/O ----------------------------------------


class TestRoutingFunctions:
    def test_route_after_analyze_escalated(self):
        assert graph.route_after_analyze({"escalated": True}) == "escalate"

    def test_route_after_analyze_not_escalated(self):
        assert graph.route_after_analyze({"escalated": False}) == "classify"

    def test_route_after_classify_infra(self):
        assert graph.route_after_classify({"classification": "infra-issue"}) == "infra_path"

    def test_route_after_classify_code_issue(self):
        assert graph.route_after_classify({"classification": "code-issue"}) == "code_issue_path"

    def test_route_after_code_issue_path_escalated(self):
        assert graph.route_after_code_issue_path({"escalated": True}) == "escalate"

    def test_route_after_code_issue_path_normal(self):
        assert graph.route_after_code_issue_path({"escalated": False}) == "human_approval"

    def test_route_after_approval_approved(self):
        assert graph.route_after_approval({"approval_status": "approved"}) == "apply_patch"

    def test_route_after_approval_rejected(self):
        assert graph.route_after_approval({"approval_status": "rejected"}) == "reject_end"

    def test_route_after_tests_passed(self):
        assert graph.route_after_tests({"test_result": {"passed": True}}) == "close_ticket"

    def test_route_after_tests_failed_first_attempt_retries(self):
        state = {"test_result": {"passed": False}, "draft_retry_used": False}
        assert graph.route_after_tests(state) == "retry_draft_patch"

    def test_route_after_tests_failed_after_retry_gives_up(self):
        state = {"test_result": {"passed": False}, "draft_retry_used": True}
        assert graph.route_after_tests(state) == "test_failed_end"


# --- analyze()'s bounded tool-loop -------------------------------------------


def _fake_tool_call(name: str, args: dict, call_id: str = "call_1"):
    return type(
        "FakeToolCall",
        (),
        {"id": call_id, "function": type("F", (), {"name": name, "arguments": json.dumps(args)})()},
    )()


def _fake_message(tool_calls):
    return type("FakeMessage", (), {"tool_calls": tool_calls})()


class TestAnalyzeLoop:
    def test_finish_analysis_confident_ends_loop_successfully(self, monkeypatch):
        def fake_chat(*a, **kw):
            return _fake_message(
                [
                    _fake_tool_call(
                        "finish_analysis",
                        {
                            "confident": True,
                            "identified_repo": "checkout-service",
                            "identified_file": "cart.py",
                            "root_cause": "overflow bug",
                            "evidence_excerpt": "line 42",
                        },
                    )
                ]
            )

        monkeypatch.setattr(graph, "chat_with_tools", fake_chat)
        result = graph.analyze({"incident_id": "i1", "incident_text": "bug report", "analysis_tool_calls": 0})
        assert result["escalated"] is False
        assert result["identified_repo"] == "checkout-service"
        assert result["root_cause"] == "overflow bug"

    def test_finish_analysis_low_confidence_escalates(self, monkeypatch):
        monkeypatch.setattr(
            graph, "chat_with_tools",
            lambda *a, **kw: _fake_message([_fake_tool_call("finish_analysis", {"confident": False})]),
        )
        result = graph.analyze({"incident_id": "i1", "incident_text": "x", "analysis_tool_calls": 0})
        assert result["escalated"] is True
        assert "low confidence" in result["escalation_reason"]

    def test_step_ceiling_reached_before_start_escalates(self):
        state = {
            "incident_id": "i1",
            "incident_text": "x",
            "analysis_tool_calls": graph.ANALYSIS_STEP_CEILING,
        }
        result = graph.analyze(state)
        assert result["escalated"] is True
        assert "step ceiling" in result["escalation_reason"]

    def test_step_ceiling_reached_mid_loop_escalates(self, monkeypatch):
        # Every turn calls a real (unknown-to-finish) tool, so the loop
        # must eventually hit the ceiling without ever calling
        # finish_analysis.
        monkeypatch.setattr(
            graph, "chat_with_tools",
            lambda *a, **kw: _fake_message([_fake_tool_call("list_repos", {})]),
        )
        result = graph.analyze({"incident_id": "i1", "incident_text": "x", "analysis_tool_calls": 0})
        assert result["escalated"] is True
        assert "step ceiling" in result["escalation_reason"]
        assert result["analysis_tool_calls"] == graph.ANALYSIS_STEP_CEILING

    def test_malformed_toolcall_output_retries_once_then_escalates(self, monkeypatch):
        # No tool_calls at all -> "malformed" path, allowed
        # MALFORMED_TOOLCALL_RETRY_LIMIT retries before escalating.
        monkeypatch.setattr(graph, "chat_with_tools", lambda *a, **kw: _fake_message([]))
        result = graph.analyze({"incident_id": "i1", "incident_text": "x", "analysis_tool_calls": 0})
        assert result["escalated"] is True
        assert "valid tool call" in result["escalation_reason"]

    def test_transient_failure_retries_then_escalates(self, monkeypatch):
        calls = {"n": 0}

        def flaky(*a, **kw):
            calls["n"] += 1
            raise ConnectionError("simulated transient network failure")

        monkeypatch.setattr(graph, "chat_with_tools", flaky)
        monkeypatch.setattr(graph.time, "sleep", lambda *_: None)  # skip real backoff sleeps
        result = graph.analyze({"incident_id": "i1", "incident_text": "x", "analysis_tool_calls": 0})
        assert result["escalated"] is True
        assert "transient provider failure" in result["escalation_reason"]
        # TRANSIENT_RETRY_LIMIT retries + the initial attempt
        assert calls["n"] == graph.TRANSIENT_RETRY_LIMIT + 1

    def test_token_budget_exceeded_propagates_immediately_not_retried(self, monkeypatch):
        # Regression test for a real bug found in the production-readiness
        # audit: this used to be caught by the same bare `except Exception`
        # as transient failures, causing 1-2 MORE paid LLM calls after the
        # budget was already exceeded, and mislabeling the escalation
        # reason as "transient provider failure" instead of the truth.
        calls = {"n": 0}

        def budget_blown(*a, **kw):
            calls["n"] += 1
            raise TokenBudgetExceededError("simulated budget breach")

        monkeypatch.setattr(graph, "chat_with_tools", budget_blown)
        monkeypatch.setattr(graph.time, "sleep", lambda *_: None)

        with pytest.raises(TokenBudgetExceededError):
            graph.analyze({"incident_id": "i1", "incident_text": "x", "analysis_tool_calls": 0})

        # Exactly ONE call — no retries burned on an already-exceeded budget.
        assert calls["n"] == 1

    def test_unknown_tool_name_returns_error_result_and_continues(self, monkeypatch):
        calls = {"n": 0}

        def fake_chat(*a, **kw):
            calls["n"] += 1
            if calls["n"] == 1:
                return _fake_message([_fake_tool_call("not_a_real_tool", {})])
            return _fake_message(
                [_fake_tool_call("finish_analysis", {"confident": True, "root_cause": "found it"})]
            )

        monkeypatch.setattr(graph, "chat_with_tools", fake_chat)
        result = graph.analyze({"incident_id": "i1", "incident_text": "x", "analysis_tool_calls": 0})
        assert result["escalated"] is False
        assert result["root_cause"] == "found it"

    def test_tool_impl_exception_is_caught_and_reported_as_tool_error(self, monkeypatch):
        from backend.agent import tools as tools_mod

        calls = {"n": 0}

        def fake_chat(*a, **kw):
            calls["n"] += 1
            if calls["n"] == 1:
                return _fake_message([_fake_tool_call("read_file", {"repo": "checkout-service", "path": "cart.py"})])
            return _fake_message(
                [_fake_tool_call("finish_analysis", {"confident": True, "root_cause": "recovered"})]
            )

        def raising_read_file(**kwargs):
            raise ValueError("simulated tool failure")

        monkeypatch.setattr(graph, "chat_with_tools", fake_chat)
        monkeypatch.setitem(tools_mod.READ_ONLY_TOOL_IMPLS, "read_file", raising_read_file)

        result = graph.analyze({"incident_id": "i1", "incident_text": "x", "analysis_tool_calls": 0})
        assert result["escalated"] is False
        assert result["root_cause"] == "recovered"


# --- classify() ---------------------------------------------------------


class TestClassify:
    def test_valid_classification_passed_through(self, monkeypatch):
        monkeypatch.setattr(
            graph, "complete_json",
            lambda system, user, model=None: {"classification": "infra-issue", "message": "check DNS"},
        )
        result = graph.classify({"incident_id": "i1", "incident_text": "x", "root_cause": "y", "evidence_excerpt": "z"})
        assert result["classification"] == "infra-issue"
        assert result["infra_message"] == "check DNS"

    def test_invalid_classification_defaults_to_code_issue(self, monkeypatch):
        # Conservative default per graph.py's comment — still human-gated
        # before anything is actually applied.
        monkeypatch.setattr(
            graph, "complete_json",
            lambda system, user, model=None: {"classification": "something-unexpected"},
        )
        result = graph.classify({"incident_id": "i1", "incident_text": "x", "root_cause": "y", "evidence_excerpt": "z"})
        assert result["classification"] == "code-issue"
