---
name: research-first
description: Use before writing any code against a framework outside the well-covered core (LangGraph, FastAPI, Next.js) — e.g. CrewAI, DSPy, MCP, GraphRAG libraries, N8N, Guardrails AI/NeMo, or anything else new/fast-moving. Cross-checks the bundled reference example against current official docs before trusting it.
---

# Research First

The model's training data is thinnest and stalest for narrower, faster-
moving frameworks. A bundled `references/*.py` example in a skill folder
is a snapshot from whenever it was written — it can drift from the
framework's current API. This skill is the check that catches that drift
before it's built into a project.

## When to use

- Any time `agent-crewai`, `agent-dspy`, `agent-mcp-real`, or
  `agent-graphrag` is invoked (their SKILL.md files call this out as
  mandatory).
- Any other named-but-narrow framework a brief specifies that isn't
  LangGraph/FastAPI/Next.js — Guardrails AI, NeMo Guardrails, N8N,
  fine-tuning/PEFT libraries, etc.
- Not needed for LangGraph, FastAPI, Next.js, or standard Python/JS
  stdlib — the model's knowledge there is deep and stable enough that this
  step would just add latency for no benefit.

## Procedure

1. Identify the exact library/framework and, if possible, the version
   pinned in `requirements.txt`/`package.json` (or the latest stable if not
   yet pinned).
2. Use `WebFetch`/`WebSearch` to pull the current official quickstart or
   API reference for the specific feature you're about to use (not just the
   framework's homepage — the specific class/function signature).
3. Diff what you find against the bundled `references/*.py` file in the
   relevant skill folder. If they match, proceed with the reference as-is.
   If they've diverged (renamed classes, changed constructor args, new
   required parameters), note the diff and adapt your code to the current
   docs — the fetched docs win, not the bundled file.
4. If the fetched docs themselves are ambiguous or you can't find an
   authoritative current source, say so explicitly rather than guessing,
   and consider using the `spike-first` step (see `agent-builder`) to
   verify empirically by running a tiny standalone script.
5. This is a quick check (one fetch + one diff), not a research essay —
   don't spend more effort here than the risk warrants.
