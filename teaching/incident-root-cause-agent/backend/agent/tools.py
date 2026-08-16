"""The 9 tools, per `system_design/04_tools_and_authorization.md`.

Each tool is a plain Python function plus an OpenAI tool-calling JSON
schema (`TOOL_SCHEMAS`) so the bounded-search node in `graph.py` can let
the model choose among `search_code` / `list_repos` / `read_file` /
`finish_analysis` itself (real ReAct tool selection, not a hardcoded
sequence). `search_similar_incidents` is always called first and directly
by the graph (per stage 6: "always in context ... surfaced at the first
step of the loop"), not offered to the model as a choice.

`apply_patch` is the one tool that mutates a real repo file. It performs
no approval check itself — the approval boundary is structural: the graph
in `graph.py` makes it unreachable without first passing through the
`interrupt()` node and a resumed `Command(resume={"approved": True})`.
This function trusts its caller (the graph) to have already enforced that.
"""
from __future__ import annotations

import difflib
import json
import math
import os
import re
import resource
import subprocess
import sys
import uuid
from pathlib import Path

from . import db, mcp_jira
from .config import (
    ALLOWED_REPOS,
    PRECEDENT_SIMILARITY_THRESHOLD,
    REASONING_MODEL,
    RUN_TESTS_MAX_CPU_SECONDS,
    RUN_TESTS_MAX_MEMORY_BYTES,
    RUN_TESTS_TIMEOUT_SECONDS,
    config,
)
from .llm import complete_json, embed
from .repos import list_repo_files, repo_root, safe_repo_path


# --- 1. search_similar_incidents -------------------------------------------


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def search_similar_incidents(incident_text: str) -> dict | None:
    """Embed `incident_text` and compare (in-process cosine similarity)
    against every stored incident's embedding. Returns the single
    best-matching precedent (repo/file/root-cause/outcome summary) if its
    similarity clears `PRECEDENT_SIMILARITY_THRESHOLD`, else None. Never
    returns the full incidents table (per stage 6's context rules)."""
    query_vec = embed(incident_text)
    best_row = None
    best_score = 0.0
    for row in db.all_incidents():
        if not row["identified_repo"]:
            continue  # skip incomplete/escalated records as precedents
        stored_vec = json.loads(row["embedding_json"])
        score = _cosine_similarity(query_vec, stored_vec)
        if score > best_score:
            best_score = score
            best_row = row

    if best_row is None or best_score < PRECEDENT_SIMILARITY_THRESHOLD:
        return None

    return {
        "precedent_id": best_row["id"],
        "similarity": round(best_score, 4),
        "identified_repo": best_row["identified_repo"],
        "identified_file": best_row["identified_file"],
        "root_cause": best_row["root_cause"],
        "classification": best_row["classification"],
        "outcome": best_row["outcome"],
    }


# --- 2. list_repos -----------------------------------------------------------


def list_repos() -> dict:
    return {
        repo: list_repo_files(repo)
        for repo in ALLOWED_REPOS
    }


# --- 3. search_code -----------------------------------------------------------


def search_code(repo: str, pattern: str, context_lines: int = 2) -> list[dict]:
    """Grep-like search for `pattern` (plain substring or regex) across
    every file in `repo`. Returns matching line snippets with surrounding
    context, never full file contents (per stage 6's context rules)."""
    root = repo_root(repo)
    matches: list[dict] = []
    try:
        compiled = re.compile(pattern)
    except re.error:
        compiled = re.compile(re.escape(pattern))

    for rel_path in list_repo_files(repo):
        full_path = root / rel_path
        try:
            lines = full_path.read_text().splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        for i, line in enumerate(lines):
            if compiled.search(line):
                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines + 1)
                snippet = "\n".join(lines[start:end])
                matches.append({"path": rel_path, "line_number": i + 1, "snippet": snippet})
    return matches


# --- 4. read_file --------------------------------------------------------------


def read_file(repo: str, path: str) -> str:
    full_path = safe_repo_path(repo, path)
    return full_path.read_text()


# --- 5. run_tests ----------------------------------------------------------


def _sandbox_preexec() -> None:
    """Runs in the child process after fork(), before exec() — applies
    OS-level resource limits to whatever `run_tests` executes next.

    This is PROCESS-LEVEL HARDENING, not full sandboxing. What it does and
    does not protect against:

    - Caps CPU time (RLIMIT_CPU) and address space (RLIMIT_AS) so a test
      file with an infinite loop or a memory-bomb gets killed by the OS
      instead of degrading the whole backend host.
    - Caps subprocess count (RLIMIT_NPROC) to block fork-bomb-style code.
    - Disables core dumps (RLIMIT_CORE) so a crash doesn't write a
      potentially sensitive memory dump to disk.
    - Does NOT block filesystem access outside the repo directory — the
      test file still runs as the same OS user as the backend process, so
      it can read/write anything that user can (repo path safety in
      repos.py stops the AGENT from requesting an out-of-repo path, but
      code the test file itself executes is not confined to the repo).
    - Does NOT block network access — a malicious test file can still make
      outbound connections.
    - Does NOT provide a separate filesystem/PID/network namespace.

    Real isolation for arbitrary/untrusted repos (vs. this demo's fixed
    synthetic fixtures) requires running the test in a container or
    microVM with `--network=none`, a read-only root filesystem plus a
    throwaway writable scratch dir, and cgroup limits (Docker/gVisor/
    Firecracker/nsjail) — not achievable from within the same host process
    via `resource.setrlimit` alone. That's the production upgrade path;
    this function is the floor, not the ceiling.

    Each limit is applied best-effort: macOS in particular rejects
    RLIMIT_AS in some configurations ("current limit exceeds maximum
    limit") even though the request is well-formed — that's a platform
    quirk, not a reason to fail every test run outright. A limit that
    can't be set on this platform is simply skipped; CPU/NPROC/CORE are
    the load-bearing ones on Linux (where this runs in production).
    """
    for limit_id, values in (
        (resource.RLIMIT_CPU, (RUN_TESTS_MAX_CPU_SECONDS, RUN_TESTS_MAX_CPU_SECONDS)),
        (resource.RLIMIT_AS, (RUN_TESTS_MAX_MEMORY_BYTES, RUN_TESTS_MAX_MEMORY_BYTES)),
        (resource.RLIMIT_NPROC, (16, 16)),
        (resource.RLIMIT_CORE, (0, 0)),
    ):
        try:
            resource.setrlimit(limit_id, values)
        except (ValueError, OSError):
            pass  # platform doesn't support/allow this specific limit


def run_tests(repo: str, test_file: str) -> dict:
    """Execute the specific synthetic test file tied to an incident (a
    plain `python3 <test_file>` run, self-contained — see each repo's
    test_*.py `__main__` block). Returns pass/fail plus captured output.

    Hardened (see `_sandbox_preexec` for exactly what this does and does
    not cover): CPU/memory/process-count rlimits, a wall-clock timeout, and
    a scrubbed environment (no OPENAI_API_KEY / PHOENIX_API_KEY / auth
    secrets passed through to the child process) — a test file has no
    business reading this backend's credentials."""
    full_path = safe_repo_path(repo, test_file)
    root = repo_root(repo)

    scrubbed_env = {
        k: v
        for k, v in os.environ.items()
        if not any(
            secret in k.upper()
            for secret in ("API_KEY", "SECRET", "TOKEN", "PASSWORD", "PHOENIX")
        )
    }

    try:
        result = subprocess.run(
            [sys.executable, str(full_path)],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=RUN_TESTS_TIMEOUT_SECONDS,
            env=scrubbed_env,
            preexec_fn=_sandbox_preexec if sys.platform != "win32" else None,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "passed": False,
            "stdout": (exc.stdout or b"").decode() if isinstance(exc.stdout, bytes) else (exc.stdout or ""),
            "stderr": f"test run killed after exceeding {RUN_TESTS_TIMEOUT_SECONDS}s wall-clock timeout",
            "returncode": -1,
        }

    return {
        "passed": result.returncode == 0,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
    }


# --- 6. draft_patch ----------------------------------------------------------


def draft_patch(
    repo: str,
    path: str,
    incident_text: str,
    root_cause: str,
    failing_test_output: str | None = None,
) -> dict:
    """LLM-authored fix. Produces a full replacement file body plus a
    unified diff for human review — nothing is written to disk here. The
    diff is what the approval UI shows; `apply_patch` later writes
    `new_content` verbatim once approved."""
    current_content = read_file(repo, path)

    retry_context = ""
    if failing_test_output:
        retry_context = (
            "\n\nA previous patch attempt was approved and applied, but the "
            "tied test still failed. This is a NEW patch attempt — produce a "
            "corrected fix, taking the failing test output below into account:\n"
            f"<test_output>\n{failing_test_output}\n</test_output>"
        )

    system = (
        "You are a senior software engineer fixing a real bug in a small "
        "synthetic codebase. You will be given the current contents of one "
        "file, an incident report, and a root-cause explanation. Return a "
        "JSON object with exactly two keys: `new_content` (the full, "
        "corrected contents of the file, as a single string) and "
        "`explanation` (a short human-readable explanation of the fix). "
        "Make the smallest correct change — do not rewrite unrelated code."
    )
    user = (
        f"<incident_report>\n{incident_text}\n</incident_report>\n\n"
        f"<root_cause>\n{root_cause}\n</root_cause>\n\n"
        f"<file_contents path=\"{path}\">\n{current_content}\n</file_contents>"
        f"{retry_context}"
    )

    result = complete_json(system, user, model=REASONING_MODEL)
    new_content = result["new_content"]
    explanation = result.get("explanation", "")

    diff_lines = list(
        difflib.unified_diff(
            current_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
    )
    diff_text = "".join(diff_lines)

    return {
        "repo": repo,
        "path": path,
        "current_content": current_content,
        "new_content": new_content,
        "diff": diff_text,
        "explanation": explanation,
    }


# --- 7. create_jira_ticket ----------------------------------------------------


def create_jira_ticket(incident_id: str, summary: str, description: str) -> dict:
    """Creates the incident's ticket — a REAL Jira issue via MCP
    (backend/agent/mcp_jira.py) when real Jira credentials are set
    (config.jira_enabled), otherwise the mocked local JSON
    store, exactly as before. Either way the result is ALSO mirrored into
    the local store keyed by the real (e.g. 'SCRUM-42') or synthetic
    ('TCKT-xxxxxxxx') ticket_id, so every downstream consumer (audit
    table, UI, close/reject) needs no branching of its own — they just
    look up ticket_id.

    Idempotency: real Jira's create call has no built-in idempotency the
    way the mock's incident-id-derived ticket_id gave it — but this
    function is only ever called once per incident, from code_issue_path
    (the analysis retry loop and the post-approval draft_patch retry
    never call it again), so that's a structural guarantee, not something
    engineered around here."""
    if config.jira_enabled:
        issue = mcp_jira.create_issue(summary=summary, description=description)
        ticket_id = issue["key"]
    else:
        ticket_id = f"TCKT-{incident_id[:8]}"
    return db.create_ticket(ticket_id, incident_id, summary, description)


# --- 8. apply_patch (human-approval gated, structurally, by the graph) ------


def apply_patch(repo: str, path: str, new_content: str) -> dict:
    """Writes `new_content` to the real synthetic repo file. This function
    itself has no approval check — the graph structurally cannot reach
    this call without a resumed, explicit human approval (see graph.py's
    `human_approval` interrupt node). A `.bak` copy of the pre-patch
    content is written alongside for the demo's own inspection/debugging,
    though this system offers no automated rollback beyond that."""
    full_path = safe_repo_path(repo, path)
    original = full_path.read_text()
    if original == new_content:
        return {"applied": False, "reason": "no-op: content already matches patch"}
    backup_path = full_path.with_suffix(full_path.suffix + ".bak")
    backup_path.write_text(original)
    full_path.write_text(new_content)
    return {"applied": True, "path": str(full_path), "backup": str(backup_path)}


# --- 9. close_jira_ticket ------------------------------------------------------


def close_jira_ticket(ticket_id: str, resolution_note: str) -> dict:
    """Closes the ticket — real Jira: transitions it to
    INCIDENT_AGENT_JIRA_DONE_TRANSITION_NAME (default 'Done') and adds
    resolution_note as a comment; mock: unchanged local behavior. Real
    Jira failures (e.g. no matching transition on this project's
    workflow) raise mcp_jira.JiraMCPError — NOT caught here, so the
    close_ticket_node in graph.py fails loudly rather than marking a
    ticket "closed" locally that's actually still open in real Jira."""
    if config.jira_enabled:
        mcp_jira.close_issue(ticket_id, resolution_note)
    return db.close_ticket(ticket_id, resolution_note)


def reject_jira_ticket(ticket_id: str, rejection_note: str) -> dict:
    """Records a rejection — real Jira: adds a comment WITHOUT
    transitioning status, so the ticket stays open exactly like the
    mock's reject_ticket (which leaves the local record open too, only
    storing the rejection note)."""
    if config.jira_enabled:
        mcp_jira.add_comment(ticket_id, f"Patch rejected: {rejection_note}")
    return db.reject_ticket(ticket_id, rejection_note)


# --- OpenAI tool-calling schemas for the bounded search/analysis loop ------
#
# Only the read-only search tools + a "finish_analysis" signal are exposed
# to the model in the ReAct loop. `draft_patch`, `create_jira_ticket`,
# `apply_patch`, `run_tests`, `close_jira_ticket` are called directly by
# graph nodes after classification, not chosen ad hoc by the model — this
# matches the design's fixed post-classification shape (stage 2/7) while
# still letting repo/file discovery be a genuine dynamic tool loop.

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "list_repos",
            "description": "List the 3 available repos and every file path in each.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_code",
            "description": (
                "Grep-like search for a substring or regex pattern across all "
                "files in one repo. Returns matching lines with surrounding context."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "enum": list(ALLOWED_REPOS)},
                    "pattern": {"type": "string"},
                },
                "required": ["repo", "pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the full contents of one file within one repo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "enum": list(ALLOWED_REPOS)},
                    "path": {"type": "string"},
                },
                "required": ["repo", "path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish_analysis",
            "description": (
                "Call this once you have enough evidence to state which repo/file "
                "is responsible and what the root cause is, OR to honestly report "
                "that you could not determine it. This ends the search loop."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "confident": {"type": "boolean"},
                    "identified_repo": {"type": "string", "enum": list(ALLOWED_REPOS)},
                    "identified_file": {"type": "string"},
                    "root_cause": {"type": "string"},
                    "evidence_excerpt": {"type": "string"},
                },
                "required": ["confident"],
            },
        },
    },
]

READ_ONLY_TOOL_IMPLS = {
    "list_repos": lambda **kwargs: list_repos(),
    "search_code": lambda **kwargs: search_code(**kwargs),
    "read_file": lambda **kwargs: read_file(**kwargs),
}


def new_incident_id() -> str:
    return str(uuid.uuid4())
