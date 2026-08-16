"""Read-only GitHub repository scanning through GitHub's official MCP server."""
from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import PurePosixPath

from mcp import ClientSession
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

from .config import REASONING_MODEL
from .llm import complete_json

GITHUB_MCP_URL = os.environ.get(
    "INCIDENT_AGENT_GITHUB_MCP_URL", "https://api.githubcopilot.com/mcp/"
)
MAX_SCAN_FILES = int(os.environ.get("INCIDENT_AGENT_GITHUB_MAX_SCAN_FILES", "40"))
CODE_SUFFIXES = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs", ".rb",
    ".php", ".cs", ".cpp", ".c", ".h", ".sql", ".yaml", ".yml", ".json",
}


class GitHubMCPError(RuntimeError):
    pass


def parse_repository(value: str) -> tuple[str, str]:
    cleaned = value.strip().rstrip("/")
    cleaned = re.sub(r"^https?://github\.com/", "", cleaned)
    cleaned = cleaned.removesuffix(".git")
    parts = [part for part in cleaned.split("/") if part]
    if len(parts) != 2 or any(part in {".", ".."} for part in parts):
        raise GitHubMCPError("Enter a GitHub repository as owner/name or a github.com URL.")
    return parts[0], parts[1]


def _http_headers() -> dict[str, str]:
    token = os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN", "")
    if not token:
        raise GitHubMCPError(
            "GITHUB_PERSONAL_ACCESS_TOKEN is not configured. Add a read-capable GitHub token to .env."
        )
    return {
        "Authorization": f"Bearer {token}",
        "X-MCP-Toolsets": "repos",
        "X-MCP-Readonly": "true",
    }


async def _call_async(tool_name: str, arguments: dict) -> str:
    try:
        async with create_mcp_http_client(headers=_http_headers()) as http_client:
            async with streamable_http_client(GITHUB_MCP_URL, http_client=http_client) as (
                read,
                write,
                *_
            ):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments)
    except GitHubMCPError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise GitHubMCPError(f"GitHub MCP call failed for {tool_name}: {exc}") from exc
    if getattr(result, "is_error", getattr(result, "isError", False)):
        raise GitHubMCPError(f"GitHub MCP tool {tool_name} returned an error: {result.content}")
    text = "\n".join(c.text for c in result.content if getattr(c, "type", None) == "text")
    if not text:
        raise GitHubMCPError(f"GitHub MCP tool {tool_name} returned no text content.")
    return text


def _call(tool_name: str, arguments: dict) -> str:
    return asyncio.run(_call_async(tool_name, arguments))


def _decode(raw: str):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def read_repository(owner: str, repo: str) -> list[dict[str, str]]:
    """Read a bounded set of source files through MCP, never writing GitHub."""
    queue = [""]
    files: list[dict[str, str]] = []
    while queue and len(files) < MAX_SCAN_FILES:
        path = queue.pop(0)
        payload = _decode(_call("get_file_contents", {"owner": owner, "repo": repo, "path": path}))
        entries = payload if isinstance(payload, list) else [payload]
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            entry_path = entry.get("path", "")
            entry_type = entry.get("type", "")
            if entry_type == "dir":
                if not any(part.startswith((".", "node_modules", "vendor", "dist", "build")) for part in PurePosixPath(entry_path).parts):
                    queue.append(entry_path)
            elif entry_type == "file" and PurePosixPath(entry_path).suffix.lower() in CODE_SUFFIXES:
                content_payload = _decode(_call("get_file_contents", {"owner": owner, "repo": repo, "path": entry_path}))
                content = content_payload.get("content", "") if isinstance(content_payload, dict) else str(content_payload)
                files.append({"path": entry_path, "content": content[:30000]})
                if len(files) >= MAX_SCAN_FILES:
                    break
    return files


def scan_repository(repository: str, request: str) -> dict:
    owner, repo = parse_repository(repository)
    files = read_repository(owner, repo)
    bundle = "\n\n".join(f"===== {item['path']} =====\n{item['content']}" for item in files)
    result = complete_json(
        system=(
            "You are a senior production software reliability engineer performing a repository-wide "
            "bug and incident-cause review. You must be evidence-driven and conservative. Analyze "
            "every supplied source file, trace data/control flow across files, and prioritize bugs "
            "that could cause runtime failures, incorrect data, security exposure, outages, crashes, "
            "resource leaks, race conditions, or silently wrong behavior. Ignore formatting, naming, "
            "refactoring preferences, and hypothetical issues without a reachable execution path. "
            "Do not infer code that is not supplied. A finding is valid only when you can cite the "
            "exact file and approximate line, explain the triggering input/path, and show why the "
            "current behavior is wrong. Return at most 10 findings, ordered by severity and confidence. "
            "For each finding return title, severity (critical/high/medium/low), confidence (0-1), "
            "file, line, evidence, trigger_scenario, root_cause, impact, and unified_diff. The diff "
            "must be minimal, syntactically plausible, and use the exact repository path and nearby "
            "context from the supplied file; never claim it was applied. If a safe patch cannot be "
            "derived from the supplied code, return an empty unified_diff and explain why. Return an "
            "empty findings array when no credible bug is supported. Output only valid JSON."
        ),
        user=(
            f"Repository: {owner}/{repo}\nUser request: {request}\n"
            f"Files read through GitHub MCP (read-only, max {MAX_SCAN_FILES}):\n{bundle}\n\n"
            "Before returning findings, cross-check each claim against the exact supplied code, "
            "reject duplicate symptoms of the same root cause, and ensure every proposed diff "
            "matches its cited file."
        ),
        model=REASONING_MODEL,
    )
    findings = result.get("findings", [])
    if not isinstance(findings, list):
        raise GitHubMCPError("The bug-scan response did not contain a findings list.")
    return {"repository": f"{owner}/{repo}", "files_read": [f["path"] for f in files], "findings": findings}
