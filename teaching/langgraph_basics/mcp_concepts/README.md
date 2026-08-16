# MCP Concepts

A five-notebook series on the **Model Context Protocol (MCP)** and how a
LangGraph agent uses it — building a real MCP server with FastMCP, exposing
all three MCP primitives (tools/resources/prompts), connecting a LangGraph
agent as an MCP client, understanding how routing actually works (or
doesn't) across multiple servers, connecting to a real public MCP server,
and the protocol lifecycle/security/production concerns a working demo
doesn't force you to learn.

This is scoped specifically to `teaching/langgraph_basics/`, matching this
course's style (problem-card markdown, mermaid diagrams, hand-built
`StateGraph`s like `single_agent_architectures/01_react_single_agent.ipynb`)
— a separate, more elaborate MCP project already exists at
`teaching/mcp_all/` (a full package + CLI + Qdrant-backed capstone); this
series is the concepts, that project is a worked end-to-end application
built on them.

## Why this matters

Most MCP tutorials either show a toy in-process function dressed up as
"MCP," or a single server/single tool happy path that never surfaces the
real failure modes. Every notebook in this series is **executed for real**
against actual separate server processes (and, in notebook 04, a genuine
third-party public server) — including two real bugs hit and fixed live:
a duplicate-tool-name collision (notebook 03) and a context-window overflow
from an oversized tool result (notebook 04). Nothing here is asserted
without a real run backing it.

## Servers (`servers/`)

Three standalone MCP server processes — not in-process functions — plus one
used only in notebook 05's sampling demo:

| File | Domain | Primitives | Notes |
|---|---|---|---|
| `calculator_server.py` | Arithmetic | tools only | Deliberately the simplest server, used first |
| `knowledge_ops_server.py` | Service ops (checkout/payments/search/inventory/auth — same theme as `multi_agent_architectures`' incident-investigation notebooks) | tools + resources (static + templated) + a prompt | Supports both stdio (default) and `--http <port>` |
| `orders_server.py` | Order lookups | tools only | A third, clearly-distinct domain for notebook 03's multi-server demo |
| `sampling_demo_server.py` | N/A (demo only) | one tool using `ctx.sample()` | Holds no API key of its own — asks the *client* to run the LLM call |

Run any of them standalone: `python servers/<name>.py`.

## Notebooks

| # | Notebook | Covers |
|---|---|---|
| 01 | `01_fastmcp_server_tools_resources_prompts.ipynb` | What MCP is; building `knowledge_ops_server.py`; tools vs. resources vs. prompts; a raw `mcp` SDK client doing real `initialize`/`list_tools`/`read_resource`/`get_prompt`/`call_tool` over stdio, then the same server over HTTP |
| 02 | `02_langgraph_agent_as_mcp_client.ipynb` | `MultiServerMCPClient` loads MCP tools into a hand-built LangGraph `StateGraph` (same shape as `single_agent_architectures/01_react_single_agent.ipynb`); one agent chaining tools from 2 servers in a single real run |
| 03 | `03_multi_mcp_server_tool_routing.ipynb` | Connects 3 servers at once; proves there's no server-level routing decision, only ordinary flat-list tool selection — then reproduces a **real, deterministic** duplicate-tool-name collision and fixes it |
| 04 | `04_connecting_public_mcp_server_http.ipynb` | Real connection to DeepWiki's public, no-auth MCP server over Streamable HTTP; hits and fixes a real context-overflow bug; stdio-vs-HTTP comparison and third-party trust/security notes |
| 05 | `05_mcp_lifecycle_security_and_production_notes.ipynb` | Full protocol lifecycle (capability negotiation, notifications); a real working **sampling** demo (server asks the client's LLM for a completion); roots (conceptual); a security checklist grounded in this course's own real bugs; production considerations |

## Setup

From this folder (`teaching/langgraph_basics/mcp_concepts/`):

```bash
pip install -r ../requirements.txt   # includes fastmcp, mcp, langchain-mcp-adapters
cp ../../../.env.example .env        # or use the repo-root .env; OPENAI_API_KEY required
```

Notebooks 02, 03, 04, and 05 make real OpenAI calls (gpt-4o-mini by
default, this repo's configured model) — total cost across all four is a
few cents at most. Notebook 01 makes zero LLM calls (pure protocol
mechanics). Notebook 04 also makes real network calls to a public,
no-authentication-required third-party server (`mcp.deepwiki.com`).

## A note on the ecosystem's pace

This series pins `fastmcp==3.4.6` deliberately — `ctx.sample()` (used for
real in notebook 05) was removed entirely in FastMCP 4. Every API used
across these notebooks was verified against current documentation before
being written, not assumed from prior knowledge — this is genuinely one of
the faster-moving parts of the LangGraph/agent ecosystem.
