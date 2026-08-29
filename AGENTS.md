# Coding_Agent_Enabled_Demo — Agent Instructions

This directory is a workshop for building end-to-end projects, atomic
concept demos, and lightweight teaching demos by conversing with agent-based
tools (Claude Code, OpenCode, Codex), starting from a single human-written brief.

Use `WORKFLOW.md` as the canonical process reference. The toolchain-facing
assets are:

- `skills/` — reusable skills for each workflow capability (Codex plugin, opencode auto-loaded).
- `agents/` — role prompts for scope boundaries when delegating work or keeping slices isolated.
- `prompts/` — slash-command style prompt recipes (`/new-teaching-demo`, `/run-teaching-pipeline`, etc).
- `.opencode/` — opencode config with skills, agents, commands, and plugin registration.
- `.codex-plugin/plugin.json` — Codex plugin manifest exposing `skills/`.
- `.claude/` — legacy Claude Code assets for backwards compatibility.

## Opencode Setup

Skills are auto-discovered from `.opencode/skills/`, `.claude/skills/`, and `skills/`.
Commands are auto-discovered from `.opencode/commands/` and `.claude/commands/`.
Agents are defined in `.opencode/agents/` with symlinks to `agents/`.

Restart opencode after config changes for them to take effect.

## Tools Supported

| Tool | Support |
|------|---------|
| Claude Code | `.claude/skills/`, `.claude/agents/`, `.claude/commands/` |
| OpenCode | `.opencode/skills/`, `.opencode/agents/`, `.opencode/commands/`, `opencode.json` |
| Codex | `skills/`, `agents/`, `prompts/`, `.codex-plugin/plugin.json` |

## Mandatory Workflow

For `projects/<slug>` and `concepts/<slug>`, always follow this order:

1. Read the existing brief, or create one with `write-project-brief` /
   `write-concept-brief`.
2. Clarify requirements with `clarify-requirements`; ask the user directly
   before design or code when open questions remain.
3. Run `require-api-key`. This repository has no mock mode. A real
   provider key (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or `GROQ_API_KEY`)
   must be present and verified with an actual call before design or code.
4. Produce `design.md` with `technical-design`.
5. Draft test cases with `write-and-validate-tests` and wait for explicit
   user confirmation that they match intent.
6. Produce `plan.md` with `make-plan`.
7. Build task by task from `plan.md`, using the matching component skills.
8. Run `run-tests`; do not proceed while the full suite is failing.
9. Run `security-check` for tool calling, database access, or untrusted
   content ingestion.
10. Run `eval-and-observability` for RAG or quality/reliability claims.
11. Run `lint-and-typecheck`, then `validate-env`.
12. Run `integrate-and-assemble`, then `run-and-verify`.
13. Review brief fidelity and scope after verification passes.
14. Add `deploy-config` only when the brief requires deployment.

For `teaching/<slug>`, use the lightweight track in `WORKFLOW.md`:
`/new-teaching-demo` creates the folder only, then
`/run-teaching-pipeline` drives `teaching-brief` through description,
clarification, format, happy-path testcase, `.env`/real API-key
verification, Phoenix/no-Phoenix, vector-store choice, and
ready-to-generate approval before `teaching-build` and `teaching-verify`.
Resume from the first incomplete checkpoint if Claude Code or Codex has
already done part of the work. Use `teaching-debug`/`project-debug` on
failures and `teaching-add-step` when extending an existing demo. For
extensions, accept `/add-teaching-step <slug> <feature description>` or
ask for the description when only `<slug>` is supplied; support both
notebook/script and `full_app` demos.

## Ground Rules

- Work on one project, concept, or teaching demo at a time.
- Preserve existing completed units; do not regenerate them silently.
- Never add mock, placeholder, canned-response, or degraded fallback paths
  around a missing provider key.
- Reuse `_shared/config.py` and `_shared/llm_client.py` through
  `helper-utils` rather than reinventing provider loading.
- If a design names CrewAI, DSPy, MCP, GraphRAG, or another fast-moving
  framework, run `research-first` and a standalone spike before wiring it
  into the app.
- Keep generated code scoped to the brief, decisions, design, and plan.

## Validation

After finishing a project, concept, or teaching demo, run:

```bash
python scripts/validate_coding_agent_demo.py
```

Fix reported failures before considering the unit complete.
