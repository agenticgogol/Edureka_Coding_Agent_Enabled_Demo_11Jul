# Coding_Agent_Enabled_Demo — Instructions for Claude Code

This directory is a workshop for building end-to-end projects and atomic
concept demos entirely by conversing with a coding agent (Claude Code /
Codex), starting from a single human-written brief.

**Drive this with the slash commands in `.claude/commands/`** —
`/new-project`, `/new-concept`, `/run-pipeline`, `/test-project`,
`/status-project` — rather than expecting skills to sequence themselves;
skills are capabilities the agent draws on, they don't self-trigger in
order. See `WORKFLOW.md` for the full sequence table, the invocation
model, and the command reference.

## The workflow (always follow this order)

1. **Read the brief.** Every unit of work lives in `projects/<slug>/project_brief.md`
   or `concepts/<slug>/concept_brief.md`. That file is user input — never
   invent scope beyond it, and never silently narrow it either. Use
   `write-project-brief` / `write-concept-brief` if one doesn't exist yet.
2. **Clarify.** Use `clarify-requirements` and ask the user directly before
   writing any design or code. Do not guess.
2a. **Require API key — hard stop.** Use `require-api-key` immediately
    after clarification. **This repo has no mock mode.** Check for a
    provider key (`ANTHROPIC_API_KEY`/`OPENAI_API_KEY`/`GROQ_API_KEY`) and
    make one real verification call. If no key is set, or it fails, stop
    completely — do not draft `design.md`, do not write any code, do not
    create stub/placeholder implementations "for now." Nothing proceeds
    until a real, working key is confirmed.
3. **Design.** Use `technical-design` to produce `design.md` — architecture,
   data flow, API contracts, tech choices. No code yet.
4. **Write and validate tests.** Use `write-and-validate-tests` to draft
   test cases from the brief/design and **get explicit user confirmation
   that the test cases reflect their intent** before implementing anything.
5. **Plan.** Use `make-plan` to turn `design.md` into `plan.md`. It always
   includes: env/dependency setup, component build steps, test
   implementation, `security-check` (if applicable), `eval-and-observability`
   (if applicable), `lint-and-typecheck`, `validate-env`, and always ends
   with `integrate-and-assemble` + `run-and-verify`.
6. **Build.** Work through `plan.md` task by task using the component
   skills. For agent/graph logic, pick the skill matching the framework
   `design.md` names — `agent-langgraph` (default), `agent-crewai`,
   `agent-dspy`, `agent-mcp-real`, `agent-graphrag` — never substitute
   `agent-langgraph` for a framework named explicitly. For anything other
   than LangGraph, run `research-first` before coding and spike a
   standalone script before wiring into the project (see `agent-builder`).
7. **Run tests.** Run `run-tests` — the single owner of "did the tests
   pass." Full-suite run with real captured output, 100% green (or
   explicitly documented skips) before moving on.
8. **Security and eval.** Run `security-check` for any project with tool
   calling, DB access, or untrusted-content ingestion. Run
   `eval-and-observability` for any RAG or quality-claiming project.
9. **Static checks.** Run `lint-and-typecheck` — type errors and lint
   issues get caught here, not left for the runtime smoke test to find.
10. **Env check.** Run `validate-env` — confirms `.env.example` matches what
    the code actually reads, and that a missing required key fails loudly
    and immediately (no silent degraded behavior — there is no fallback).
11. **Integrate.** Run `integrate-and-assemble` to reconcile API contracts,
    env var names, dependency versions, and produce a single run path.
12. **Verify.** Run `run-and-verify` — install fresh, launch, and drive one
    real end-to-end request. A project is not done until this passes.
13. **Deploy config (optional).** If the brief calls for deployment, use
    `deploy-config`.

## Ground rules

- One project or concept at a time. Do not generate multiple folders under
  `projects/` or `concepts/` in a single pass unless explicitly told to.
- Never skip the clarify step, and never skip the user-confirmation step in
  `write-and-validate-tests` — both exist specifically to catch cases where
  the agent's reading of the brief diverges from the user's intent.
- Skills in `.claude/skills/` here are generic and apply to any project or
  concept. A project may define its own additional skills/agents in its own
  `.claude/skills/` or `.claude/agents/` — check there first, they take
  precedence for anything project-specific.
- For CrewAI, DSPy, real MCP, and GraphRAG specifically: the model's
  baseline knowledge is thinner and these APIs move faster than
  LangGraph/FastAPI/Next.js. Always use `research-first` and the
  spike-first discipline in `agent-builder` — do not trust a bundled
  `references/*.py` example without checking it against current docs.
- Reuse `_shared/config.py` and `_shared/llm_client.py` via `helper-utils`
  instead of reinventing config/required-key-checking/provider-switching
  per project.
- Don't add scope, abstractions, or files beyond what the brief and plan
  call for.
- **No mock mode, anywhere, in any track (projects/concepts/teaching).**
  Every LLM call goes to a real provider. A missing or broken key is a
  hard stop enforced by `require-api-key` before any build starts, and
  `config.py`/`llm_client.py` fail loudly rather than degrading — never
  add a mock/placeholder/canned-response fallback to route around a
  missing key, even temporarily.
- Preserve existing completed projects/concepts. Do not regenerate or
  silently rewrite them.

## Subagents available (`.claude/agents/`)

`requirements-clarifier`, `planner`, `frontend-builder`, `backend-builder`,
`agent-builder`, `integrator`, `reviewer`. See each agent file for its exact
scope boundary and, for `agent-builder`, the research-first/spike-first
rules. Use them to keep context isolated per slice on larger projects; for
small concepts, working directly in the main conversation is fine.

## Validation

After finishing a project or concept, run:

```bash
python scripts/validate_coding_agent_demo.py
```

Fix any failures before stopping.
