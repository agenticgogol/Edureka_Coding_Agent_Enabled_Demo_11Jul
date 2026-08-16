"""Unit tests for backend/agent/tools.py.

Read-only tests (search_code/read_file/list_repos/search_similar_incidents)
run against the real data/repos/ fixtures — safe, nothing written.
Mutating tests (apply_patch, run_tests' sandbox behavior) use a throwaway
temp repo dir via monkeypatching `repos.REPOS_DIR` — they never touch the
real synthetic fixtures teaching_brief.md's verified demo run depends on.
All LLM calls (`complete_json`, `embed`) are monkeypatched; zero real API
calls anywhere in this file.
"""
from __future__ import annotations

import os
import sys
import textwrap

import pytest

from backend.agent import repos, tools
from backend.agent.config import RUN_TESTS_TIMEOUT_SECONDS


@pytest.fixture
def fake_repo(tmp_path, monkeypatch):
    """Points repos.REPOS_DIR at a throwaway temp dir and creates a
    checkout-service/ subdir inside it — reuses the real allowlisted repo
    NAME (repo_root() rejects unknown names) but never touches the real
    fixture files on disk."""
    monkeypatch.setattr(repos, "REPOS_DIR", tmp_path)
    repo_dir = tmp_path / "checkout-service"
    repo_dir.mkdir()
    return repo_dir


class TestSearchCodeReadFileListRepos:
    """Read-only against the REAL synthetic repos — safe."""

    def test_list_repos_returns_all_three(self):
        result = tools.list_repos()
        assert set(result.keys()) == {"checkout-service", "auth-service", "notifications-service"}
        assert "cart.py" in result["checkout-service"]

    def test_read_file_returns_real_content(self):
        content = tools.read_file("checkout-service", "cart.py")
        assert "calculate_cart_total" in content

    def test_search_code_finds_known_function(self):
        matches = tools.search_code("checkout-service", "calculate_cart_total")
        assert len(matches) > 0
        assert matches[0]["path"] == "cart.py"

    def test_search_code_no_match_returns_empty(self):
        matches = tools.search_code("checkout-service", "definitely_not_a_real_symbol_xyz123")
        assert matches == []


class TestSearchSimilarIncidents:
    def test_no_incidents_returns_none(self, monkeypatch):
        monkeypatch.setattr(tools, "embed", lambda text: [1.0, 0.0, 0.0])
        assert tools.search_similar_incidents("new incident") is None

    def test_match_above_threshold_returned(self, monkeypatch):
        from backend.agent import db

        db.insert_incident(
            incident_id="precedent-1",
            incident_text="checkout API 500 on large carts",
            embedding=[1.0, 0.0, 0.0],
            identified_repo="checkout-service",
            identified_file="cart.py",
            root_cause="overflow bug",
            classification="code-issue",
            outcome="closed_pass",
        )
        # Same direction vector -> cosine similarity 1.0, well above the
        # 0.80 threshold.
        monkeypatch.setattr(tools, "embed", lambda text: [1.0, 0.0, 0.0])
        match = tools.search_similar_incidents("checkout API 500 error")
        assert match is not None
        assert match["precedent_id"] == "precedent-1"
        assert match["similarity"] == 1.0

    def test_match_below_threshold_not_returned(self, monkeypatch):
        from backend.agent import db

        db.insert_incident(
            incident_id="precedent-2",
            incident_text="unrelated incident",
            embedding=[1.0, 0.0, 0.0],
            identified_repo="checkout-service",
            outcome="closed_pass",
        )
        # Orthogonal vector -> cosine similarity 0.0, below threshold.
        monkeypatch.setattr(tools, "embed", lambda text: [0.0, 1.0, 0.0])
        assert tools.search_similar_incidents("totally different incident") is None

    def test_incomplete_records_skipped_as_precedents(self, monkeypatch):
        from backend.agent import db

        # No identified_repo -> escalated/incomplete record, must be
        # skipped as a precedent candidate per tools.py's own comment.
        db.insert_incident(
            incident_id="precedent-3",
            incident_text="escalated incident",
            embedding=[1.0, 0.0, 0.0],
            identified_repo=None,
            outcome="escalated_ceiling",
        )
        monkeypatch.setattr(tools, "embed", lambda text: [1.0, 0.0, 0.0])
        assert tools.search_similar_incidents("anything") is None


class TestDraftPatch:
    def test_produces_diff_and_explanation(self, monkeypatch):
        monkeypatch.setattr(
            tools,
            "complete_json",
            lambda system, user, model=None: {
                "new_content": "print('fixed')\n",
                "explanation": "simulated fix",
            },
        )
        patch = tools.draft_patch(
            repo="checkout-service",
            path="cart.py",
            incident_text="incident",
            root_cause="root cause",
        )
        assert patch["new_content"] == "print('fixed')\n"
        assert patch["explanation"] == "simulated fix"
        assert "cart.py" in patch["diff"]
        assert patch["current_content"]  # real file was actually read

    def test_retry_context_included_when_failing_test_output_given(self, monkeypatch):
        captured_user = {}

        def fake_complete_json(system, user, model=None):
            captured_user["value"] = user
            return {"new_content": "x", "explanation": "y"}

        monkeypatch.setattr(tools, "complete_json", fake_complete_json)
        tools.draft_patch(
            repo="checkout-service",
            path="cart.py",
            incident_text="incident",
            root_cause="root cause",
            failing_test_output="AssertionError: boom",
        )
        assert "AssertionError: boom" in captured_user["value"]
        assert "NEW patch attempt" in captured_user["value"]


class TestJiraTicketHelpers:
    def test_ticket_id_derived_from_incident_id(self):
        ticket = tools.create_jira_ticket("abcdefgh-1234-5678", "summary", "description")
        assert ticket["ticket_id"] == "TCKT-abcdefgh"

    def test_close_ticket_delegates_to_db(self):
        tools.create_jira_ticket("11112222-3333", "s", "d")
        closed = tools.close_jira_ticket("TCKT-11112222", "resolved")
        assert closed["status"] == "closed"


class TestApplyPatch:
    def test_writes_new_content_and_backs_up_old(self, fake_repo):
        target = fake_repo / "cart.py"
        target.write_text("old content\n")

        result = tools.apply_patch("checkout-service", "cart.py", "new content\n")

        assert result["applied"] is True
        assert target.read_text() == "new content\n"
        backup = fake_repo / "cart.py.bak"
        assert backup.read_text() == "old content\n"

    def test_noop_when_content_unchanged(self, fake_repo):
        target = fake_repo / "cart.py"
        target.write_text("same content\n")

        result = tools.apply_patch("checkout-service", "cart.py", "same content\n")

        assert result["applied"] is False
        assert not (fake_repo / "cart.py.bak").exists()

    def test_cannot_escape_repo_via_path_traversal(self, fake_repo):
        with pytest.raises(repos.PathEscapeError):
            tools.apply_patch("checkout-service", "../outside.py", "malicious content")


class TestRunTestsSandbox:
    def _write_test_script(self, repo_dir, name: str, body: str) -> str:
        (repo_dir / name).write_text(textwrap.dedent(body))
        return name

    def test_passing_script_reports_passed(self, fake_repo):
        test_file = self._write_test_script(
            fake_repo, "test_ok.py", """
            print("PASS")
            """
        )
        result = tools.run_tests("checkout-service", test_file)
        assert result["passed"] is True
        assert result["returncode"] == 0

    def test_failing_script_reports_not_passed(self, fake_repo):
        test_file = self._write_test_script(
            fake_repo, "test_fail.py", """
            import sys
            print("FAIL: something broke")
            sys.exit(1)
            """
        )
        result = tools.run_tests("checkout-service", test_file)
        assert result["passed"] is False
        assert result["returncode"] == 1
        assert "FAIL" in result["stdout"]

    def test_timeout_is_enforced(self, fake_repo, monkeypatch):
        monkeypatch.setattr(tools, "RUN_TESTS_TIMEOUT_SECONDS", 1)
        test_file = self._write_test_script(
            fake_repo, "test_slow.py", """
            import time
            time.sleep(10)
            """
        )
        result = tools.run_tests("checkout-service", test_file)
        assert result["passed"] is False
        assert result["returncode"] == -1
        assert "timeout" in result["stderr"].lower()

    def test_secrets_scrubbed_from_child_environment(self, fake_repo, monkeypatch):
        # OPENAI_API_KEY is set (to a dummy value) by conftest.py for the
        # whole test session — confirm run_tests' child process genuinely
        # cannot see it, regardless of what's in the parent's environment.
        monkeypatch.setenv("OPENAI_API_KEY", "sk-should-never-reach-child")
        monkeypatch.setenv("SOME_OTHER_SECRET_TOKEN", "also-should-not-leak")
        test_file = self._write_test_script(
            fake_repo, "test_env.py", f"""
            import os
            leaked = [k for k in os.environ if 'API_KEY' in k.upper() or 'SECRET' in k.upper() or 'TOKEN' in k.upper()]
            print("LEAKED:" + ",".join(leaked))
            """
        )
        result = tools.run_tests("checkout-service", test_file)
        assert "LEAKED:" in result["stdout"]
        assert result["stdout"].strip() == "LEAKED:"  # nothing after the colon

    def test_cannot_run_test_file_outside_repo(self, fake_repo):
        with pytest.raises(repos.PathEscapeError):
            tools.run_tests("checkout-service", "../../etc/passwd")
