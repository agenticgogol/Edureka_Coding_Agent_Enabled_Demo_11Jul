---
name: agent-langgraph
description: Use when design.md names LangGraph (or names no framework — this is the default) for agent/graph logic. Implements state/nodes/tools/checkpointing; the backend or notebook calls into this module.
---

# Agent (LangGraph)

Default agent framework for this repo. Well-covered by the model's own
knowledge, but still start from the bundled reference rather than free-hand
— it encodes the checkpointing pattern this repo's gap analysis flags as
commonly faked (a UI "approve" button with no real interrupt state).

## When to use

- `design.md` names LangGraph, or names no specific framework (default).
- Not for CrewAI, DSPy, real multi-process MCP, or GraphRAG — use
  `agent-crewai`, `agent-dspy`, `agent-mcp-real`, `agent-graphrag`
  respectively; do not substitute LangGraph for a framework the brief
  named explicitly.

## Procedure

1. Read `references/basic_graph_with_checkpointing.py` in this skill
   folder — a minimal, known-working StateGraph with a real
   interrupt/resume checkpoint, not a fake approval button. Adapt it; don't
   rewrite the pattern from memory.
2. Scaffold under `projects/<slug>/backend/agent/` (or
   `concepts/<slug>/agent/`). Define state shape, nodes, edges, and tools
   exactly as sketched in `design.md`.
3. Every external tool call (LLM, search, DB) goes through the copied
   `_shared/llm_client.py` / `config.py` (via `helper-utils`) — real
   provider calls only, no mock mode. `require-api-key` already verified
   the key before this skill ran.
4. Expose one clean entrypoint function (`run_agent(input) -> output`) —
   don't leak internal node names or state shape across the module
   boundary.
5. If `design.md` calls for human-in-the-loop, use the checkpointing +
   `interrupt`/resume pattern from the reference file, and prove it in
   `run-and-verify` by actually pausing and resuming a real run — not just
   asserting it in prose.
