# Coding_Agent_Enabled_Demo

Build end-to-end projects and atomic concept demos by conversing with
Codex or Claude Code, starting from a plain-language brief instead of code.

## How it works

```text
+------------------+     +-------------+     +-----------+     +---------+     +-------------+
| project_brief.md |---->|  Clarify    |---->|  design.md|---->| plan.md |---->|  Build code |
| (you write this) |     | (agent asks |     |  (agent   |     | (agent  |     | (per-slice  |
|                   |     |  questions) |     |  writes)  |     | writes) |     |  skills)    |
+------------------+     +-------------+     +-----------+     +---------+     +------+------+
                                                                                       |
                                                                                       v
                                                                        +--------------------------+
                                                                        | integrate-and-assemble +  |
                                                                        | run-and-verify (must pass)|
                                                                        +--------------------------+
```

1. `/new-project <slug>` (or `/new-concept <slug>`) — drafts the brief via
   an interview, stops for your review.
2. `/run-pipeline projects <slug>` (or `concepts <slug>`) — runs clarify,
   **API key check**, design, test-drafting, planning, build, testing,
   security/eval checks, lint, env audit, integration, and verification,
   in order. It hard-stops if no working provider key is configured — this
   repo has no mock mode, so nothing is designed or built until a real key
   is verified with an actual call — and also stops and waits for you at
   two further points: clarifying open questions, and confirming the
   drafted test cases actually match what you meant.
3. `/status-project projects <slug>` any time to see what's actually done
   (re-checked against the filesystem, not just `plan.md`'s checkboxes).
4. `/test-project projects <slug>` to re-run the test gate standalone after
   a manual edit.
5. When done, the project/concept folder is self-contained: brief, design,
   plan, tests, and working code/notebook, runnable with one command.

Codex instructions live in `AGENTS.md`; reusable Codex skills live in
`skills/`; command-style prompt recipes live in `prompts/`. The legacy
Claude Code copies remain in `.claude/`. **Full sequence, the invocation
model, and the reasoning behind the ordering: see `WORKFLOW.md`.**

## Layout

- `skills/` — generic, reusable Codex skills: brief-writing, clarifying,
  `require-api-key` (hard gate, no mock mode), design, planning,
  test-writing (with a user-confirmation gate), env setup, frontend/backend
  scaffolding, one agent skill per framework
  (`agent-langgraph`/`agent-crewai`/`agent-dspy`/`agent-mcp-real`/
  `agent-graphrag`, each with a bundled `references/` example),
  `research-first` (for fast-moving frameworks), `security-check`,
  `eval-and-observability`, `lint-and-typecheck`, `validate-env`,
  integration, verification, deploy configs. Apply to any project/concept.
- `agents/` — role prompts with scoped responsibilities (clarifier,
  planner, frontend/backend/agent builders, integrator, reviewer). Use
  them as delegation prompts or scope boundaries in Codex.
- `prompts/` — command-style workflow recipes (`new-project`,
  `run-pipeline`, `test-project`, etc.) copied from the original slash
  commands for Codex use.
- `.codex-plugin/plugin.json` — local Codex plugin manifest exposing the
  `skills/` directory.
- `.claude/` — legacy Claude Code copies of the same skills, agents, and
  commands for backwards compatibility.
- `_shared/` — copy-from templates (`config.py`, `llm_client.py`) so
  required-key enforcement and provider-switching behavior stay consistent
  across projects instead of being reinvented each time. No mock mode —
  `config.py` raises immediately if no provider key is set.
- `projects/` — one folder per end-to-end application. Full pipeline.
- `concepts/` — one folder per atomic, certification-grade concept demo
  (7-part notebook contract). Full pipeline.
- `teaching/` — one folder per lightweight, progressive classroom demo
  (e.g. "API call → system prompt → tool calling → memory → basic RAG").
  Start with `/new-teaching-demo`, then `/run-teaching-pipeline` for the
  gated description/clarification/format/happy-path/API-key/
  observability/vector-store/code-generation flow.
- `scripts/validate_coding_agent_demo.py` — checks every project/concept/
  teaching unit has the required files before you consider it done.

## Setup

```bash
cp .env.example .env   # set at least one real LLM provider key — required, no mock mode
python -m venv .venv && source .venv/bin/activate   # or use the setup-venv skill
```

**No mock mode anywhere in this repo.** Every pipeline (`projects/`,
`concepts/`, `teaching/`) runs `require-api-key` before any design or code
is written — it checks for a provider key and makes one real verification
call. If that fails, nothing gets built until you fix it.

Each project/concept manages its own `requirements.txt` / `package.json` —
there is no single monorepo dependency file by design, since projects are
meant to be independently runnable and deployable.
