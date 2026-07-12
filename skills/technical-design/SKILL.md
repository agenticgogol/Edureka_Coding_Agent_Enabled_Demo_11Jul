---
name: technical-design
description: Use after clarify-requirements has resolved all open questions on a brief. Produces design.md — architecture, data flow, API contracts, tech choices. No code written here.
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

0. **For `projects/`, ask the build-format question explicitly before
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
