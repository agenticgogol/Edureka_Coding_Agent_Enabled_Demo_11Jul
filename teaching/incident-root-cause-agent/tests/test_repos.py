"""Unit tests for backend/agent/repos.py — the path-traversal defense
that keeps read_file/search_code/apply_patch/run_tests confined to the 3
allowlisted synthetic repos. Read-only against the real data/repos/
fixtures (safe — nothing here writes)."""
from __future__ import annotations

import pytest

from backend.agent import repos
from backend.agent.config import ALLOWED_REPOS


class TestRepoRoot:
    def test_known_repo_resolves(self):
        root = repos.repo_root("checkout-service")
        assert root.is_dir()
        assert root.name == "checkout-service"

    def test_unknown_repo_raises(self):
        with pytest.raises(repos.InvalidRepoError):
            repos.repo_root("not-a-real-repo")

    def test_all_allowed_repos_exist_on_disk(self):
        for repo in ALLOWED_REPOS:
            assert repos.repo_root(repo).is_dir()


class TestSafeRepoPath:
    def test_normal_relative_path_resolves_inside_repo(self):
        path = repos.safe_repo_path("checkout-service", "cart.py")
        assert path.is_file()
        assert path.parent == repos.repo_root("checkout-service")

    def test_dotdot_traversal_blocked(self):
        with pytest.raises(repos.PathEscapeError):
            repos.safe_repo_path("checkout-service", "../auth-service/secrets.py")

    def test_deep_dotdot_traversal_blocked(self):
        with pytest.raises(repos.PathEscapeError):
            repos.safe_repo_path("checkout-service", "../../../../../etc/passwd")

    def test_absolute_path_override_blocked(self):
        with pytest.raises(repos.PathEscapeError):
            repos.safe_repo_path("checkout-service", "/etc/passwd")

    def test_unknown_repo_raises_before_path_check(self):
        with pytest.raises(repos.InvalidRepoError):
            repos.safe_repo_path("not-a-real-repo", "anything.py")

    def test_nested_but_still_inside_path_is_fine(self):
        # Sanity check the guard isn't overly strict — a legitimately
        # nested (but still within-repo) path must resolve normally.
        # checkout-service is flat in this demo, so simulate via '.'.
        path = repos.safe_repo_path("checkout-service", "./cart.py")
        assert path.name == "cart.py"


class TestListRepoFiles:
    def test_lists_only_real_files(self):
        files = repos.list_repo_files("checkout-service")
        assert "cart.py" in files
        assert all(not f.endswith(".bak") for f in files)
        assert all("__pycache__" not in f for f in files)

    def test_every_allowed_repo_lists_at_least_one_file(self):
        for repo in ALLOWED_REPOS:
            assert len(repos.list_repo_files(repo)) > 0
