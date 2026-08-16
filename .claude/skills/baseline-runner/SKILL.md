---
name: baseline-runner
description: MUST USE right after eval/judge_prompts/ exists, or any time the user wants to actually run the eval — "run the eval", "baseline run", "generate promptfoo config", "score the agent against the golden set". Always run after judge-prompt-builder, and re-run any time golden_set.jsonl, graders.md, or judge_prompts/ change. Trigger eagerly on any mention of running/executing an eval, promptfoo, or Ragas config.
---

# Baseline Runner

Generates and runs the eval, producing `eval/promptfooconfig.yaml` and `eval/results/baseline.json`.

## Steps

1. **Read `eval/golden_set.jsonl`, `eval/graders.md`, and `eval/judge_prompts/`.** If any are missing, stop and point to the missing prerequisite skill.

2. **Generate the promptfoo config via script, not by hand.** Write/update `eval/scripts/generate_promptfoo_config.py` — a script that reads the three inputs above and emits `eval/promptfooconfig.yaml`. This keeps the config in sync automatically as the golden set grows or graders change, instead of drifting from a one-off hand-written file. Run the script to produce the config.

3. **Check if the agent is RAG-shaped** (per `eval/tasks.md`/`eval/metrics.md` — context precision/recall/faithfulness present). If so, also generate a Ragas config (`eval/ragas_config.py` or equivalent) covering the RAG-specific metrics.

4. **Order assertions: code-based first, then llm-rubric.** Code-based checks are cheap and deterministic — run them first so failing examples short-circuit before spending judge calls. Only run llm-rubric (model-based) assertions on examples that need them.

5. **Before executing any real run against a live provider, confirm cost/call count with the user** per this repo's standing rule — state the number of examples × judge calls and get explicit go-ahead.

6. **Run the eval and write `eval/results/baseline.json`** with: aggregate score, per-task scores, per-metric scores, model version used, and prompt version (git ref or content hash of the agent's system prompt).

7. **Do not stop at the aggregate number.** Once results are written, hand off to `failure-analyzer` on any failing examples — baseline-runner's job ends at producing scored results, not at diagnosing why they failed.

## Rules

- Never hand-edit `eval/promptfooconfig.yaml` directly as the source of truth — edits belong in the generator script so regeneration doesn't lose them.
- Code-based assertions always run before model-based ones, never interleaved arbitrarily.
- Always get cost approval before a real run, per this repo's API-spend policy.
- Always route to failure-analyzer after results are written — an aggregate score alone is not a deliverable.
