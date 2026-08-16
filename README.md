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

## Eval toolkit

A separate Claude Code toolkit for building and running an eval suite
against any agent (a scaffolded demo agent, or an existing one already in
this repo) — task definition through production monitoring. All artifacts
are plain files under `eval/`, keyed off `eval/state.md`, so any session
(or any collaborator) can resume the pipeline exactly where it left off
just by reading that file.

### Install

Nothing extra to install for the toolkit itself — it's `.claude/skills/`,
`.claude/agents/`, and `.claude/commands/` markdown, driven by whichever
skill/agent each command dispatches to. Individual steps may need Python
deps for calibration/scripts (e.g. `scikit-learn` for Cohen's kappa,
`promptfoo`/`ragas` for the baseline run) — install those as prompted when
you hit that step. Set a real provider key in `.env` per the no-mock-mode
policy above before running any step that calls a live model.

### Commands

| Command | Produces | Prerequisite |
|---|---|---|
| `/eval-suite-init` | `eval/` folder structure + empty `eval/state.md` | none |
| `/eval-demo-agent [archetype]` | `demo_agent/` (Mode A, seeded bugs) | `eval/state.md` |
| `/eval-integrate` | `eval/scan_report.md` (Mode B, read-only scan) | `eval/state.md` |
| `/eval-define-tasks` | `eval/tasks.md` | `eval/state.md` |
| `/eval-define-metrics` | `eval/metrics.md` | `eval/tasks.md` |
| `/eval-build-golden [batch size]` | `eval/golden_set.jsonl` | `eval/metrics.md` |
| `/eval-select-graders` | `eval/graders.md` | `eval/golden_set.jsonl` |
| `/eval-write-judge` | `eval/judge_prompts/` | `eval/graders.md` |
| `/eval-run-baseline` | `eval/results/baseline.json` | `eval/judge_prompts/` |
| `/eval-analyze` | `eval/failure_report.md` | `eval/results/baseline.json` |
| `/eval-calibrate [metric]` | `eval/calibration_report.md` | `eval/judge_prompts/` |
| `/eval-simulate` | `eval/simulation/` (multi-turn tasks only) | `eval/tasks.md` |
| `/eval-wire-cicd` | `.github/workflows/eval-gate.yml` | `eval/results/baseline.json` |
| `/eval-optimize-cost` | `eval/cost_report.md` | `eval/calibration_report.md` (approved judge) |
| `/eval-monitor-setup` | `eval/monitoring_config.md` | `eval/results/baseline.json` |
| `/eval-suite-run [demo\|integrate] [fast-forward]` | all of the above, end to end | none — inits if needed |

Run the individual commands one at a time for a guided walkthrough, or
`/eval-suite-run` to delegate the whole pipeline to the `eval-architect`
subagent, which drives all 12 steps in order, still pausing at every
skill's built-in user-review point unless you pass `fast-forward`.

Every artifact lives as a plain file under `eval/` — nothing is held only
in conversation state, so `eval/state.md`'s Pipeline Progress checklist and
Decisions Log are always the source of truth for what's done and why. Any
new session picks up the pipeline exactly where the last one stopped just
by reading it.
