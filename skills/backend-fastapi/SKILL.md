---
name: backend-fastapi
description: Use when plan.md calls for a FastAPI backend. Implements the API contract defined in design.md exactly — no frontend or standalone agent scaffolding here.
---

# Backend (FastAPI)

## When to use

- Default backend choice for `projects/` needing an HTTP API.

## Procedure

1. Scaffold under `projects/<slug>/backend/` — `main.py` (app + routers),
   `requirements.txt` (or contribute to the shared one from
   `pick-requirements`).
2. Implement every endpoint listed in `design.md`'s "API contract" exactly
   as specified: same paths, methods, request/response shapes. If an
   endpoint the frontend needs isn't in `design.md`, stop and flag it back —
   don't invent an undocumented endpoint the frontend then has to guess at.
3. Wire agent/graph logic (if any) via a clean import from wherever
   the relevant `agent-*` skill (`agent-langgraph`/`agent-crewai`/
   `agent-dspy`/`agent-mcp-real`/`agent-graphrag`) places it — the backend calls the agent, it does not
   embed graph-building logic inline.
4. Config/secrets: read via `helper-utils`' config loader; every external
   call (LLM, vector DB, etc.) requires a real, working key — no mock-mode
   fallback exists in this repo. `require-api-key` already verified the
   key before this skill ran; `run-and-verify` will run against the real
   provider.
5. Add basic error handling at the API boundary (validation errors ->
   4xx with a clear message) — but don't add defensive handling for
   scenarios `design.md` doesn't call for.
6. Include a `README` run snippet: `uvicorn main:app --reload`.
