"""Real Jira integration via MCP (Model Context Protocol).

Uses the open-source `mcp-atlassian` server (sooperset/mcp-atlassian,
https://github.com/sooperset/mcp-atlassian) launched as a stdio subprocess
via `uvx` — a REAL separate MCP server process communicating over stdio,
not an in-process function call standing in for MCP. Opt-in: only used
when a complete Cloud or Server/Data Center Jira credential set is present
(config.jira_enabled)
— tools.py falls back to the local mocked JSON ticket store otherwise. See
README's "Real Jira via MCP" section for individual setup (free Jira Cloud
tier, no cost).

Tool names/parameters below were verified directly against
mcp-atlassian's source (src/mcp_atlassian/servers/jira.py), not just its
docs — per this repo's research-first policy for fast-moving MCP tooling,
since the model's baseline knowledge of specific MCP server APIs is thin
and these interfaces change across releases.

Each call spawns a fresh `uvx mcp-atlassian` subprocess rather than
keeping one long-lived connection open across the backend process's
lifetime — simpler and more robust for this demo's call volume (at most a
few Jira calls per incident) than managing a persistent subprocess's
reconnection/liveness across the synchronous graph nodes that call into
this module. The cost is per-call subprocess startup latency (roughly
1-2s), acceptable here.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .config import (
    JIRA_DONE_TRANSITION_NAME,
    JIRA_ISSUE_TYPE,
    JIRA_PROJECT_KEY,
    MCP_ATLASSIAN_PACKAGE,
    MCP_UV_CACHE_DIR,
    MCP_UV_TOOL_DIR,
    config,
)

logger = logging.getLogger("incident_backend.mcp_jira")


class JiraMCPError(RuntimeError):
    """Raised when the mcp-atlassian subprocess, the MCP protocol call,
    or the underlying Jira API call fails. Never caught and silently
    ignored by callers — a failed real Jira write must surface as a real
    failure, not be treated as a successful mock-equivalent no-op."""


def _server_params() -> StdioServerParameters:
    # Keep the MCP child environment intentionally small: the Jira token is
    # needed by the server, but OpenAI/auth/backend secrets are not.
    child_env = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/tmp"),
        "UV_CACHE_DIR": MCP_UV_CACHE_DIR,
        "UV_TOOL_DIR": MCP_UV_TOOL_DIR,
        "JIRA_URL": config.jira_url,
    }
    if config.jira_personal_token:
        child_env["JIRA_PERSONAL_TOKEN"] = config.jira_personal_token
    else:
        child_env["JIRA_USERNAME"] = config.jira_username
        child_env["JIRA_API_TOKEN"] = config.jira_api_token
    return StdioServerParameters(
        command="uvx",
        args=["--from", MCP_ATLASSIAN_PACKAGE, "mcp-atlassian"],
        env=child_env,
    )


async def _call_tool_async(tool_name: str, arguments: dict) -> str:
    try:
        async with stdio_client(_server_params()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
    except Exception as exc:  # noqa: BLE001 - subprocess/transport failure
        raise JiraMCPError(
            f"Failed to reach mcp-atlassian for {tool_name}: {exc}. "
            "Confirm `uvx --from mcp-atlassian>=0.22.0 mcp-atlassian` runs "
            "standalone and the Jira credentials are correct."
        ) from exc

    # MCP Python SDKs have used both JSON-RPC-style `isError` and the current
    # Pydantic-style `is_error`; support either so a successful Jira write is
    # not reported as a failed incident merely while inspecting its result.
    result_is_error = getattr(result, "is_error", getattr(result, "isError", False))
    if result_is_error:
        raise JiraMCPError(f"{tool_name} returned an error: {result.content}")

    text_parts = [c.text for c in result.content if getattr(c, "type", None) == "text"]
    if not text_parts:
        raise JiraMCPError(f"{tool_name} returned no text content: {result.content}")
    return "\n".join(text_parts)


def _call_tool(tool_name: str, arguments: dict) -> str:
    # Safe to call asyncio.run() here: every caller of this module
    # (tools.py, invoked from synchronous graph.py nodes) runs on a plain
    # OS thread — FastAPI's sync route handlers execute in Starlette's
    # threadpool, not directly on the asyncio event loop — so there is
    # never an already-running loop in this thread to conflict with.
    return asyncio.run(_call_tool_async(tool_name, arguments))


def create_issue(summary: str, description: str) -> dict:
    """Creates a real Jira issue in JIRA_PROJECT_KEY. Returns a dict with
    at least `key` (e.g. 'SCRUM-42') on success. Raises JiraMCPError on
    any failure."""
    raw = _call_tool(
        "jira_create_issue",
        {
            "project_key": JIRA_PROJECT_KEY,
            "summary": summary,
            "issue_type": JIRA_ISSUE_TYPE,
            "description": description,
        },
    )
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise JiraMCPError(f"jira_create_issue returned non-JSON content: {raw}") from exc

    key = payload.get("key") or (payload.get("issue") or {}).get("key")
    if not key:
        raise JiraMCPError(f"jira_create_issue succeeded but no issue key in response: {raw}")
    return {"key": key, "raw": payload}


def _find_transition_id(issue_key: str, target_name: str) -> str | None:
    raw = _call_tool("jira_get_transitions", {"issue_key": issue_key})
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise JiraMCPError(f"jira_get_transitions returned non-JSON content: {raw}") from exc

    transitions = payload if isinstance(payload, list) else payload.get("transitions", [])
    for t in transitions:
        if (t.get("name") or "").strip().lower() == target_name.strip().lower():
            return str(t.get("id"))
    return None


def close_issue(issue_key: str, resolution_note: str) -> None:
    """Transitions `issue_key` to JIRA_DONE_TRANSITION_NAME (default
    'Done') and adds resolution_note as a comment. Raises JiraMCPError if
    no matching transition exists on this project's workflow — surfaced,
    not silently skipped, since a "closed" ticket that's actually still
    open is worse than an explicit failure the caller must handle."""
    transition_id = _find_transition_id(issue_key, JIRA_DONE_TRANSITION_NAME)
    if transition_id is None:
        raise JiraMCPError(
            f"No transition named '{JIRA_DONE_TRANSITION_NAME}' found for {issue_key} in this "
            "project's workflow. Set INCIDENT_AGENT_JIRA_DONE_TRANSITION_NAME in .env to match "
            "a real transition name (check your project's board/workflow settings)."
        )
    _call_tool(
        "jira_transition_issue",
        {"issue_key": issue_key, "transition_id": transition_id, "comment": resolution_note},
    )


def add_comment(issue_key: str, body: str) -> None:
    """Adds a comment without transitioning status — used for the reject
    path, where the ticket must stay open (see tools.py's reject_ticket)."""
    _call_tool("jira_add_comment", {"issue_key": issue_key, "body": body})
