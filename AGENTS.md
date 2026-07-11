# Coding_Agent_Enabled_Demo — Codex Instructions

This directory is a workshop for building end-to-end projects, atomic
concept demos, and lightweight teaching demos by conversing with Codex,
starting from a single human-written brief.

Use `WORKFLOW.md` as the canonical process reference. The Codex-facing
assets are:

- `skills/` — reusable Codex skills for each workflow capability.
- `agents/` — role prompts copied from the original subagent definitions;
  use them as scope boundaries when delegating work or keeping slices
  isolated.
- `prompts/` — slash-command style prompt recipes from the original Claude
  setup. Codex does not need these to auto-run; read the matching prompt
  when the user asks for that workflow.
- `.codex-plugin/plugin.json` — local plugin manifest exposing `skills/`.

The legacy Claude Code assets remain under `.claude/` for backwards
compatibility. Prefer the Codex-facing paths above when working in Codex.

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
`teaching-brief`, `require-api-key`, `teaching-build`, and
`teaching-verify`, with `teaching-debug` on failures. Use
`teaching-add-step` when extending an existing demo.

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
