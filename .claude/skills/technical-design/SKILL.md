---
name: technical-design
description: Use after clarify-requirements has resolved all open questions on a brief. Produces design.md — architecture, data flow, API contracts, tech choices. If an approved architecture_design.md/system_design/ already exists (mandatory for projects/ via /run-pipeline's stage 1b), maps its pattern/tool-sourcing/MCP decisions directly in rather than re-deriving them; otherwise runs its own lightweight Agentic RAG / MCP detection. No code written here.
---

# Technical Design

Turns a fully-clarified brief into a concrete design a plan can be built
from. This is the step that prevents `integrate-and-assemble` from
discovering contract mismatches later — nail the interfaces here.

## When to use

- After `clarify-requirements` has closed all open questions, and after
  `require-api-key` has confirmed a real, working provider key exists —
  this repo has no mock mode, so there's no point designing around a key
  that isn't verified yet.
- Before `make-plan`.

## Procedure

0. **Check for an already-approved architecture design first.** For
   `projects/`, `/run-pipeline`'s stage 1b runs a mandatory
   `agent-system-design`/`agent-architecture-design` pass before this skill
   is invoked — check for `<slug>/architecture_design.md` or
   `<slug>/system_design/architecture_design.md` with `Status: APPROVED`.
   If found, **map its decisions directly into `design.md` instead of
   re-deriving them**:
   - Chosen architecture pattern → `design.md`'s Agent/graph component
     (e.g. Agentic RAG → `agent-agentic-rag` plus its recorded capability
     list; RAG assistant → `vector-store` + fixed pipeline; bounded ReAct/
     planner-executor/supervisor → the matching topology).
   - Tool inventory's sourcing decisions (per tool: MCP-server name, or
     custom/free/paid) → Components and Tech choices, naming
     `agent-mcp-real` Mode B for any MCP-sourced tool.
   - Knowledge & state design, runtime shape, and non-functional budgets →
     fold into Architecture/Tech choices as relevant.
   Skip steps 0a and 0a2 below entirely in this case — the architecture
   design already answered what they ask, and re-asking would contradict
   an already-approved decision. If no approved architecture design exists
   (this is the normal case for `concepts/`, which never runs stage 1b, or
   for a `projects/` design run standalone outside `/run-pipeline`), fall
   through to steps 0a/0a2 as the lightweight fallback.

0a. **Detect whether this is an Agentic RAG usecase before writing
    `design.md`.** If the brief involves answering questions from
    changing documents/policies/knowledge that need citation, check
    whether a single fixed retrieve-then-generate call is actually enough,
    or whether answering well needs the retrieval step itself to be
    dynamic — reformulating and retrying, grading what came back, routing
    between more than one source, decomposing a multi-part question before
    retrieving, or declining to answer on thin evidence. Ask one concrete,
    closed-ended question grounded in the brief's own scenario (not an
    abstract "do you want agentic RAG?") — e.g. "if someone asks something
    that needs two different documents combined, does one retrieval pass
    reliably find both, or would it need to search, check what it found,
    and search again?" If dynamic, name `agent-agentic-rag` as the Agent/
    graph framework in `design.md` below and record which of its
    capabilities (see that skill's list: agentic retrieval decisions and
    self-grading are always-on; multi-tool routing, multi-hop planning,
    reranking, groundedness verification, and abstention are opt-in) this
    brief actually needs — don't wire the optional ones silently. If the
    brief's "changing documents" are actually a relationship-heavy
    knowledge graph rather than a flat document/policy store, this is
    `agent-graphrag` instead (or combined, if agentic control flow over a
    graph retriever is genuinely needed) — ask rather than assuming. Skip
    this whole check entirely if the brief has no retrieval/knowledge
    component at all.
0a2. **Enumerate every tool the agent needs and check for a free public
    MCP server first, before writing `design.md`.** From the brief, list
    every distinct capability/action the agent needs — including ones that
    look like they'd normally be hand-coded (filesystem access, git
    operations, querying a local DB), not just obvious third-party
    SaaS calls (web search, email/SMS, Slack/GitHub, etc.). For **each**
    one, invoke `agent-decision-external-tool-sourcing`, whose first move
    is always an MCP-server lookup — the practical effect is: **when a
    project description names a capability like this, tell the user what
    free public MCP server(s) were found for it and recommend using one by
    default**, rather than silently defaulting to hand-written
    integration code. Prefer MCP whenever a covering server exists — treat
    it as the default choice, not a neutral A/B pick, and only fall back to
    a custom tool or raw API if the user gives a specific reason (data
    residency, credential scoping, a need narrower/different than what the
    server exposes) or no MCP server actually covers it. If an MCP server
    is chosen, name `agent-mcp-real` (Mode B — connect as a client) as the
    Agent/graph component (or one of its tools) in `design.md` below, and
    record the server name/transport in Tech choices. If the brief has no
    tool/capability component at all, skip this step entirely — don't
    invent a tool need to justify an MCP lookup.
0b. **For `projects/`, ask the build-format question explicitly before
   writing anything** — even if the brief reads like a full app, don't
   assume it. Ask: "Do you want this as (a) a Jupyter notebook prototype —
   fastest to build, good for proving the logic works, or (b) a full
   frontend + FastAPI backend production-style app?" Record the answer in
   `design.md`'s Tech choices section. This determines whether step 2
   below builds `notebook-concept` or the full frontend/backend stack —
   don't default silently either way for a project, since both are
   legitimate and the cost difference (one notebook vs. a full stack) is
   large enough that guessing wrong wastes a full build cycle. (`concepts/`
   skips this — it's always notebook-scale by definition.)
1. Write `design.md` next to the brief (`projects/<slug>/design.md` or
   `concepts/<slug>/design.md`) with:

```markdown
# Design: <Name>

## Architecture
<ASCII diagram of components and data flow>

## Components
- Frontend: <framework, key pages/views>
- Backend: <framework, key endpoints>
- Agent/graph: <framework, nodes, state shape>
- Data: <what's stored where, schema if relevant>

## API contract
<every endpoint the frontend calls: method, path, request shape,
response shape — this is load-bearing, integrate-and-assemble diffs
against it later>

## Environment variables
<every env var needed, which component reads it, which are required
(at minimum one LLM provider key — no mock mode exists in this repo)>

## Tech choices and why
<framework/library choices tied back to brief constraints>

## Out of scope
<explicitly carried over from brief's non-goals>
```

2. For projects that chose the full-app format in step 0: default to
   Next.js frontend + FastAPI backend unless the brief specifies otherwise
   (see `frontend-nextjs`, `frontend-streamlit`, `backend-fastapi`). For
   projects that chose notebook format, or for concepts: a single notebook
   via `notebook-concept`, unless the brief calls for a small script/app.
3. Show `design.md` to the user before calling `make-plan` — this is the
   cheapest point to change direction, before any code exists.
