---
name: metric-definition
description: MUST USE right after eval/tasks.md exists and before any golden dataset or grader work — "what metrics should we track", "define success criteria", "how do we score this agent", "eval/metrics.md". Always run this immediately after task-definition and before golden-dataset-builder. Trigger eagerly on any mention of scoring, grading criteria, or "what makes a good response" for an agent eval.
---

# Metric Definition

Produces `eval/metrics.md`. Metrics are DERIVED from concrete good/bad examples per task — never picked off a generic list without grounding.

## Steps

1. **Read `eval/tasks.md`.** If it doesn't exist, stop and tell the user to run task-definition first.

2. **Elicit concrete examples per task.** For each task (or each priority-P0/P1 task if the list is long — confirm scope with the user), ask for 2-3 concrete example outputs: at least one good, at least one bad/mediocre. For each, ask "what specifically makes this good/bad?" Push for specifics — "it's wrong" is not enough; get "it cited a policy clause that doesn't exist" or "it called the refund tool without checking order status first."

3. **Derive metrics from the elicited specifics**, then cross-check against this shape→metric mapping to make sure nothing obvious was missed:
   - summarization → faithfulness, coverage, conciseness
   - classification → accuracy, precision, recall, F1
   - translation → adequacy, fluency, terminology
   - RAG → context precision, context recall, faithfulness, answer relevance
   - tool-using → tool selection correctness, argument validity, trajectory match, error recovery, efficiency
   - code-gen → test pass rate, style, security
   - conversational → resolution/completion, policy adherence, tone, turn efficiency, escalation correctness
   - content-gen → brief adherence, brand voice, factual safety

4. **Flag core-metric applicability.** For each task, note which of the 4 core metrics apply: relevance, faithfulness, correctness, coherence.

5. **Present the derived metric set for editing — PAUSE HERE.** Show task→metric mapping with the reasoning tied back to the elicited examples. Let the user overwrite, remove, or add metrics before locking. Do not write the file until confirmed.

6. **Write `eval/metrics.md`** with, per task: task ID, metrics list, one-line definition per metric grounded in the elicited example (not a generic textbook definition), and core-metric flags.

## Rules

- Never assign a metric to a task without at least one grounding example — if the user can't produce examples for a task, mark it "needs examples" and come back to it rather than guessing generic metrics.
- Don't dump the full generic mapping table on the user unfiltered — only surface metrics relevant to the task shapes actually present in `eval/tasks.md`.
- Pause for user edits before writing, every time — no exceptions.
