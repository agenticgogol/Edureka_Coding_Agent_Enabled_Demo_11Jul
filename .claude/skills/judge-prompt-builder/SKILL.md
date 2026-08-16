---
name: judge-prompt-builder
description: MUST USE right after eval/graders.md exists — "write the judge prompts", "LLM-as-judge prompt", "eval/judge_prompts/", "score with a model". Always run last, after grader-selector, for every metric assigned a model-based grader. Trigger eagerly on any mention of writing an LLM judge/rubric/scoring prompt.
---

# Judge Prompt Builder

Produces one file per model-based metric under `eval/judge_prompts/`, plus an `index.md`.

## Steps

1. **Read `eval/graders.md`.** Collect every metric with `model-based` as primary or secondary grader. If none exist, tell the user there's nothing to build and stop.

2. **For each model-based metric, draft a judge prompt** with:
   - Metric name
   - Reference material block (task description, relevant context/policy the judge needs)
   - Slot for user input
   - Slot for agent response
   - **Default 3-point scale**, each level with a CONCRETE anchor description tied to the actual task — never vague anchors like "good/ok/bad". Anchors must describe specific observable behavior (e.g. "3 = cites the correct policy clause and applies it correctly to the user's situation; 2 = cites a relevant clause but misapplies it; 1 = cites no clause or an incorrect one"). Vague anchors are the top cause of low judge-human agreement — do not ship them.
   - Few-shot examples pulled from `eval/golden_set.jsonl` where available for that metric/task — prefer one example per scale level if the golden set has coverage.
   - Instruction: "return an integer score and one-sentence justification quoting the exact phrase from the response that drove the score."
   - If the metric is comparative (A vs. B), explicitly instruct the judge to ignore response order and length.

3. **Present each drafted prompt for editing — PAUSE HERE**, at minimum after the first one (as a template check) and before finalizing all of them. Let the user adjust anchors, scale, or few-shots. Do not write files until confirmed.

4. **Write** `eval/judge_prompts/<metric_slug>.md` per metric, plus `eval/judge_prompts/index.md` listing every judge prompt file with its metric and associated task(s).

## Rules

- One metric per prompt file — never combine multiple metrics into a single judge call.
- Anchors must be concrete and task-specific, never generic quality adjectives alone.
- Comparative prompts must always include the order/length-bias instruction.
- Pause for user review before writing, every time — especially to confirm anchor concreteness, since that's the main quality lever here.
