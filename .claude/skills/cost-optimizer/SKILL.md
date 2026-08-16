---
name: cost-optimizer
description: MUST USE when the user wants to reduce eval or agent runtime cost — "make this cheaper", "can we use a smaller model", "reduce token cost", "eval/cost_report.md", "route simple tasks". Refuses to run until eval/calibration_report.md shows an approved/trusted judge. Trigger eagerly on any mention of cost reduction, cheaper models, prompt compression, or routing for an already-evaluated agent.
---

# Cost Optimizer

Produces `eval/cost_report.md` via three gated experiments, each validated against the same eval used for baseline-runner.

## Gate check (do this first, every time)

Read `eval/calibration_report.md`. If it doesn't exist, or shows kappa <0.6 for the metrics this optimization would affect, **refuse to proceed** — tell the user to run judge-calibrator first. Cost experiments that trade on an uncalibrated judge's scores are not trustworthy; a "no regression" result from a bad judge is meaningless.

## Experiments

Run whichever of these the user wants (confirm scope before starting) — each compared against the existing `eval/results/baseline.json` using the same golden set and graders, never a different/looser bar:

1. **Model substitution.** Re-run the eval with a cheaper candidate model as the SUT. Report results **per task**, not just in aggregate — the goal is identifying which tasks tolerate the cheaper model so routing can be selective, not an all-or-nothing swap. Flag any task where the cheaper model regresses below the calibrated pass bar.

2. **Prompt compression.** Trim the agent's system/task prompt (redundant instructions, verbose examples, unused context). Re-run the eval and report **token savings and score delta together in the same table** — never token savings alone. Pay particular attention to metrics that depend on content being trimmed (e.g. if compressing retrieved-context handling, watch faithfulness/context-recall specifically) — call these out by name if they regress.

3. **Rule-based router.** For tasks the golden set already labels as unambiguously simple (reuse existing task/category labels from `eval/golden_set.jsonl` — do not invent a new simplicity heuristic), build a cheap rule-based router that shortcuts to a cheaper path. Use the golden set itself as the router's test set: does it route simple-labeled examples correctly and leave complex ones on the full path?

## Steps

1. Confirm gate check passes.
2. Confirm with user which experiment(s) to run and get cost approval for the real eval re-runs each requires (each is a full or partial eval pass against a live provider).
3. Run the chosen experiment(s), compare against baseline per the rules above.
4. Write `eval/cost_report.md`: per experiment — approach, cost/token delta, score delta (aggregate + per-task/per-metric where relevant), recommendation (adopt / adopt selectively / reject), and any metric-specific regressions flagged.

## Rules

- Never run any cost experiment if the judge isn't calibrated — this is a hard refusal, not a warning.
- Model substitution results must be reported per-task — never present a single blended "is the cheap model good enough" verdict.
- Prompt compression must always report score delta alongside token savings, never savings alone.
- The router's test set is the existing golden set's labels — don't build a separate simplicity classifier.
- Get explicit cost approval before each real eval re-run, per this repo's API-spend policy.
