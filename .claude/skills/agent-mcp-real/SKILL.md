---
name: agent-mcp-real
description: Use when design.md/project_brief.md calls for a real MCP (Model Context Protocol) integration — either building an MCP server/client pair from scratch, or connecting as a client to an existing public/third-party MCP server sourced via agent-decision-external-tool-sourcing. Always actual separate processes with stdio or SSE transport, not an in-process function call standing in for MCP.
---

# Agent (Real MCP)

This repo's own gap analysis flags prior MCP demos as "toy" — a function
call dressed up as MCP, with filenames literally containing `_toy`. This
skill exists specifically to prevent that: a real MCP integration means an
MCP client talking to an MCP server over an actual transport with
capability negotiation, not one Python function calling another.

There are two distinct modes. Check `design.md`'s tool sourcing record (or
`project_brief.md`) to see which one applies — they are not
interchangeable, and defaulting to Mode A when a public server was already
sourced means redundantly rebuilding something that already exists.

- **Mode A — build both server and client.** The brief calls for an MCP
  client/server demo, an "MCP integration lab," or a tool that genuinely
  has no existing public MCP server (nothing was found during
  `agent-decision-external-tool-sourcing`'s step 2a lookup, or the brief
  explicitly wants a from-scratch server).
- **Mode B — connect to an existing public MCP server.** A tool's sourcing
  record says `Decision: MCP-server (name, ...)` — a public/third-party
  server was found and chosen over a raw API or custom logic. Here you
  build **only the client**; the server is a separate process/package you
  connect to, not code you own or need to write.

## When to use

- Brief/design calls for MCP client/server, an MCP tool-serving demo, or an
  "MCP integration lab" style project → **Mode A**.
- `design.md`'s tool inventory names an MCP server as a tool's sourcing
  decision (from `agent-decision-external-tool-sourcing`) → **Mode B**.

## Procedure — Mode A (build server and client)

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

## Procedure — Mode B (connect to an existing public MCP server)

1. **Research-first, mandatory**: confirm the specific server's current
   install/run instructions and available tools directly from its own repo
   or listing (the one found during `agent-decision-external-tool-sourcing`
   step 2a) — server packages and their tool names change; don't trust a
   remembered API surface. Also fetch the current MCP Python SDK client
   docs for the transport this server uses.
2. Identify the server's transport and how it's launched:
   - **stdio, via a package** (e.g. `npx <server-package>` or
     `uvx <server-package>`): the client spawns this as a subprocess — no
     server code to write, only the launch command and its required
     env vars/args.
   - **Hosted SSE/HTTP endpoint**: the client connects to a URL, possibly
     with an API key/token the server's own docs specify.
3. Confirm any credentials the *underlying* service needs (e.g. a GitHub
   MCP server still needs a GitHub token, a Slack MCP server still needs a
   Slack token) — these are real secrets, go through this repo's normal
   `.env`/`require-api-key`-style handling, and are a hard stop if missing,
   same as any other provider key.
4. Write only `references/mcp_client.py`-style client code under
   `projects/<slug>/backend/agent/mcp_client.py`, adapted to spawn/connect
   to this specific server rather than a locally-written one. Do not write
   an `mcp_server.py` for a server that already exists — that would defeat
   the entire point of choosing an existing MCP server over custom-built
   logic in the first place.
5. **Spike-first**: run the client against the real server process/endpoint
   standalone and confirm capability negotiation and at least one real tool
   call succeed before wiring into the rest of the project.
6. `run-and-verify` for this project must demonstrate a real call to the
   external server's tool succeeding end to end (not a mocked response) —
   no mock mode, same as every other external integration in this repo.
