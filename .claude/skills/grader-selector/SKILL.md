---
name: grader-selector
description: MUST USE right after eval/golden_set.jsonl exists — "how do we grade this", "pick graders", "eval/graders.md", "code-based vs model-based grading", "who scores these metrics". Always run after golden-dataset-builder and before judge-prompt-builder. Trigger eagerly on any mention of choosing scoring methods or graders for eval metrics.
---

# Grader Selector

Produces `eval/graders.md` — assigns each metric from `eval/metrics.md` to a grading method.

## Steps

1. **Read `eval/metrics.md`.** If missing, stop and point the user to metric-definition first.

2. **Assign graders per metric using this decision order:**
   - If a mechanical/deterministic check can verify it (regex, schema validation, exact match, tool-call trace diff, unit test, latency threshold) → **code-based**
   - Else if it requires open-ended judgment (tone, coherence, faithfulness nuance, brief adherence) → **model-based**
   - If the metric is high-stakes (safety, policy compliance, factual correctness with real-world consequence) → also assign a **human calibration sample** alongside the primary grader
   - If the metric is only observable with live user behavior (e.g. actual user satisfaction, real escalation outcomes) → **production-only**, and explicitly mark it excluded from the pre-launch gate

   A metric can have multiple graders (e.g. code-based primary + model-based secondary for partial credit).

3. **Present the draft assignment table for editing — PAUSE HERE.** Let the user override any assignment (e.g. they may want human grading on something that seems code-gradable, or vice versa) before finalizing.

4. **Write `eval/graders.md`** as a table:

   | Metric | Task(s) | Primary | Secondary | Notes |
   |--------|---------|---------|-----------|-------|
   | ... | ... | code-based/model-based/human/production-only | ... | ... |

   In Notes, flag production-only metrics as "excluded from pre-launch gate."

## Rules

- Never assign model-based grading to something that has a clean mechanical check available — that's wasted judge cost and adds noise.
- Every high-stakes metric must at least be flagged for a human calibration sample, even if the user later declines it — surface the recommendation, don't silently skip it.
- Pause for user edits before writing, every time.
