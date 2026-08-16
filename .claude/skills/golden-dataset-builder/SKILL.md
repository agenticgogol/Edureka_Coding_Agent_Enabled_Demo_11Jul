---
name: golden-dataset-builder
description: MUST USE right after eval/metrics.md exists — "build the golden set", "eval/golden_set.jsonl", "generate test examples", "I need eval data". Always run after metric-definition and before grader-selector. Trigger eagerly on any mention of building/expanding an eval dataset, golden examples, or test cases for an agent.
---

# Golden Dataset Builder

Produces `eval/golden_set.jsonl` — roughly 50 examples, generated and reviewed in small batches, never all at once.

## Steps

1. **Read `eval/tasks.md` and `eval/metrics.md`.** If either is missing, stop and point the user to the missing prerequisite skill.

2. **Compute quota.** Target ~50 examples total, split:
   - ~60% common/happy-path
   - ~25% edge cases
   - ~15% past-failure cases (ask the user if there's a known failure log; if none exists yet, redistribute this slice toward edge cases and note that the set is expected to grow from production monitoring and failure analysis over time)

   Distribute the quota across tasks weighted by priority (P0 tasks get proportionally more examples than P2).

3. **Generate in batches of 5-8.** For each batch:
   - Pick the next task(s)/category due per quota.
   - Draft 5-8 examples using this line schema (JSONL, one object per line):
     ```json
     {"id": "G001", "task_id": "T1", "category": "common|edge|past_failure", "input": {"user_message": "...", "context": "..."}, "good_output_notes": "...", "bad_output_notes": "...", "metrics_applicable": ["..."], "source": "generated|user_provided|production"}
     ```
   - Show the batch to the user for review — ask them to confirm, edit, drop, or request replacements before moving to the next batch.
   - Only append the batch to `eval/golden_set.jsonl` after review.

4. **Print a running coverage table after each batch**: task ID vs. category counts vs. quota remaining, so the user can see progress at a glance.

5. **Stop at ~50** (or when the user says the set is sufficient), and note explicitly in the final summary that the golden set is a living artifact — it should grow over time from failure-analyzer output and production monitoring, not stay frozen at this initial pass.

## Rules

- Never generate all ~50 examples in one shot — batches of 5-8 with review in between, every time.
- Don't fabricate `past_failure` examples out of thin air if no real failure data exists — relabel that quota slice as edge cases instead and say so.
- Keep IDs stable and sequential (`G001`, `G002`, ...) across batches — don't renumber.
