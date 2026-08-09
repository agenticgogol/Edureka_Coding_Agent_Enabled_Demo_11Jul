"""Repo allowlist + path-safety helpers.

`read_file`, `search_code`, `apply_patch`, and `run_tests` must never touch
anything outside the 3 synthetic repo directories under `data/repos/`.
Every path is validated with `resolve()` + a prefix check against the
repo's own resolved root, which blocks `..`-style traversal regardless of
how the untrusted path string is spelled.
"""
from __future__ import annotations

from pathlib import Path

from .config import ALLOWED_REPOS, REPOS_DIR


class InvalidRepoError(ValueError):
    pass


class PathEscapeError(ValueError):
    """Raised when a requested path would resolve outside its repo's
    allowlisted directory — the core defense against path traversal."""


def repo_root(repo_name: str) -> Path:
    if repo_name not in ALLOWED_REPOS:
        raise InvalidRepoError(
            f"unknown repo '{repo_name}' — must be one of {ALLOWED_REPOS}"
        )
    root = (REPOS_DIR / repo_name).resolve()
    if not root.is_dir():
        raise InvalidRepoError(f"repo directory does not exist: {root}")
    return root


def safe_repo_path(repo_name: str, relative_path: str) -> Path:
    """Resolve `relative_path` within `repo_name`'s directory and verify
    the result is actually still inside that directory (blocks `../../`
    traversal, absolute-path overrides, and symlink escapes)."""
    root = repo_root(repo_name)
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        raise PathEscapeError(
            f"path '{relative_path}' resolves outside repo '{repo_name}' "
            f"({candidate} is not inside {root})"
        )
    return candidate


def list_repo_files(repo_name: str) -> list[str]:
    root = repo_root(repo_name)
    return sorted(
        str(p.relative_to(root))
        for p in root.rglob("*")
        if p.is_file()
        and not p.name.endswith(".bak")
        and "__pycache__" not in p.parts
    )
