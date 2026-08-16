---
description: Build (or extend) the golden dataset in reviewed batches — produces/appends eval/golden_set.jsonl.
argument-hint: [batch size to append, default 5-8]
allowed-tools: Skill
---

Prerequisite: `eval/metrics.md` must exist. If missing, run `/eval-define-metrics` first.

Invoke the `golden-dataset-builder` skill. If `$ARGUMENTS` specifies a batch size, use it as the target batch size for this run (still within the 5-8 per-batch review rule unless the user explicitly wants otherwise); if omitted, use the skill's default.

Next: run `/eval-select-graders`.
