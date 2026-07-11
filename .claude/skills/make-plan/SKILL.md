---
name: make-plan
description: Use after design.md is approved. Produces plan.md, an ordered task list for building the project/concept, following this repo's full canonical sequence (see WORKFLOW.md). Always ends with integrate-and-assemble and run-and-verify.
---

# Make Plan

Converts `design.md` into an ordered, checkable task list. This is what
`TaskCreate`/`TaskUpdate` get seeded from when building. See
`../../WORKFLOW.md` for the full skill/subagent sequence table this
template is derived from.

## When to use

- After `technical-design` produces an approved `design.md`.
- Before any component-building skill runs.

## Procedure

1. Write `plan.md` next to `design.md`, using this template and pruning
   steps that don't apply (note explicitly in `plan.md` why a step was
   skipped, e.g. "security-check skipped — no tool/DB access in scope"):

```markdown
# Plan: <Name>

0. [x] require-api-key — already completed before design.md was written;
       verified provider: <anthropic|openai|groq>
1. [ ] write-and-validate-tests — draft test cases from brief/design,
       CONFIRM WITH USER before implementing
2. [ ] setup-venv / package manager init
3. [ ] pick-requirements — lock requirements.txt / package.json
4. [ ] helper-utils — copy config.py/llm_client.py from _shared/
5. [ ] backend-fastapi — implement API contract from design.md
6. [ ] agent-<framework> — implement agent/graph logic (pick the skill
       matching design.md's named framework: agent-langgraph / agent-crewai
       / agent-dspy / agent-mcp-real / agent-graphrag). Apply research-first
       and spike-first for anything other than agent-langgraph.
7. [ ] frontend-nextjs (or frontend-streamlit / notebook-concept) — implement UI
8. [ ] implement tests from step 1 alongside each slice above; each builder
       runs their own new tests before moving on
9. [ ] run-tests — INTEGRATOR-OWNED full-suite gate; real pass/fail output,
       100% green or explicitly documented skips, before proceeding
10. [ ] security-check — if tool-calling/DB/untrusted-content in scope
11. [ ] eval-and-observability — if RAG/quality claims in scope
12. [ ] lint-and-typecheck — static checks clean before integration
13. [ ] validate-env — .env.example matches what code actually reads,
        confirmed a missing required key fails loudly (no mock fallback)
14. [ ] integrate-and-assemble — reconcile contracts, env vars, single run path
15. [ ] run-and-verify — install fresh, launch, drive one real end-to-end request
16. [ ] deploy-config — only if brief requires deployment
```

2. Steps 14 and 15 (`integrate-and-assemble`, `run-and-verify`) are
   mandatory and always last, regardless of what else is in the plan — a
   project/concept is not done until both pass. Never let a plan end on a
   component-building step. Step 9 (`run-tests`) is the explicit,
   unambiguous owner of "did the tests pass" — don't leave that implicit.
3. If using subagents (`frontend-builder`, `backend-builder`,
   `agent-builder`), assign each their own numbered steps so their scope
   stays isolated; `integrator` always owns steps 9, 12-15, `reviewer` runs
   after everything passes.
4. Use `TaskCreate` to mirror `plan.md` into trackable tasks before
   building, so progress is visible.
