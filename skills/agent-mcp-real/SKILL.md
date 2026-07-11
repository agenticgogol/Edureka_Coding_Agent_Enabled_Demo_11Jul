---
name: agent-mcp-real
description: Use when design.md/project_brief.md calls for a real MCP (Model Context Protocol) client/server integration — actual separate processes with stdio or SSE transport, not an in-process function call standing in for MCP.
---

# Agent (Real MCP Client/Server)

This repo's own gap analysis flags prior MCP demos as "toy" — a function
call dressed up as MCP, with filenames literally containing `_toy`. This
skill exists specifically to prevent that: a real MCP integration means two
separate processes talking over an actual transport with capability
negotiation, not one Python function calling another.

## When to use

- Brief/design calls for MCP client/server, an MCP tool-serving demo, or an
  "MCP integration lab" style project.

## Procedure

1. **Research-first, mandatory**: fetch the current official MCP spec/SDK
   docs (Python SDK: `mcp` package) before writing anything — confirm
   transport setup (stdio vs SSE) and current server/client class names,
   since this is a newer, actively-evolving spec.
2. Read and adapt the two reference files in this folder:
   - `references/mcp_server.py` — a real MCP server process exposing at
     least one tool, run as its own process (stdio transport).
   - `references/mcp_client.py` — a real MCP client process that spawns/
     connects to the server, performs capability negotiation, and calls the
     tool.
3. Scaffold as two genuinely separate runnable entrypoints under
   `projects/<slug>/backend/agent/mcp_server.py` and `mcp_client.py` — not
   one module importing functions from the other in-process. The backend's
   agent calls the *client*, which talks to the server over the transport.
4. **Spike-first**: run server and client as two separate processes and
   confirm a tool call actually round-trips over the transport before
   wiring into the rest of the project.
5. `run-and-verify` for this project must demonstrate the two-process
   round trip explicitly (e.g. print statements showing client -> server
   -> client) — a single-process demo does not satisfy this skill.
