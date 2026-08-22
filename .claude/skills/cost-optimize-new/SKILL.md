---
name: cost-optimize-new
description: Reduce agent inference cost via prompt refinement, few-shot calibration, task decomposition, KV-cache-friendly prompt ordering, and model cascades — gated on the failure backlog being closed and evaluated by CI overlap, not point estimates.
disable-model-invocation: true
---

# cost-optimize-new

Phase 8: cost optimization. **This is a quality-preserving pass, not a
quality-tradeoff pass** — every technique here must be verified not to move
the needle on the failure modes already discovered, which is why it's gated
on the backlog being closed first.

## Step 0 — Gate: refuse if the backlog has open items

Read `evals/backlog.md`. If any failure mode there doesn't have a
corresponding `MetricsRecord` in `evals/results/metrics.json` (for
judge-routed modes) or a passing code eval in CI (for code-routed modes),
**stop and refuse**. Tell the user plainly why: optimizing cost while a
failure mode is still open makes it impossible to tell whether a later
regression came from the cost change or was already there — fix and
validate first, optimize second. Name the specific open items so they know
what to close.

## Step 1 — Establish the baseline

Before changing anything, record current cost per query (from
`evals/config.yaml` / whatever token-usage logging the agent already has)
and current corrected pass rates from `evals/results/metrics.json`. Every
technique below is compared against this baseline, not against a fresh
run — an optimization is a diff from a known-good point, not a new
independent measurement.

## Step 2 — Techniques (apply in this order; each is optional per the user's goals)

1. **Prompt refinement.** Trim unused instructions, redundant examples, or
   verbose formatting from the agent's system/tool prompts. Check against
   `evals/spec.md` — never remove content a must-always/must-never rule
   actually depends on.
2. **Few-shot calibration.** If the agent's own prompts (not judge prompts —
   those are `judge-builder-new`'s territory) carry few-shot examples, check
   whether fewer, better-chosen examples hold accuracy — more examples isn't
   automatically better and costs more tokens per call.
3. **Task decomposition.** If a single large prompt does multiple things,
   check whether splitting it into a cheaper routing step plus a focused
   step (only invoked when needed) reduces average cost without harming the
   failure modes in the backlog.
4. **KV-cache-friendly prompt ordering.** Put static content (system prompt,
   tool definitions, few-shot examples — anything identical across calls)
   first, and dynamic content (the actual user query, retrieved context,
   conversation history) last. Any call whose prefix changes invalidates
   cache for everything after that point, so static-first ordering is what
   makes prefix caching actually save money across calls — check the
   agent's prompt construction code for content assembled in the wrong
   order (e.g. injecting the user query before the tool definitions) and
   flag it even if you don't reorder it yourself, since reordering may
   require touching agent logic beyond this skill's scope.
5. **Model cascades.** Use `scripts/cascade_threshold.py`
   (`tune_threshold`) — do not hand-pick a threshold. Feed it labeled
   `(confidence, cheap_correct, expensive_correct)` triples built by running
   both models against `evals/golden/golden_set.jsonl` (or a labeled subset
   of it), with `max_accuracy_loss` set from the user (ask; don't default
   silently for a production cascade — the tolerance is a business decision,
   not a technical default). If it raises (no threshold meets the
   tolerance), report that the cheap model isn't viable as a cascade stage
   at that tolerance — don't force a threshold that violates it.

## Step 3 — Verify: CI overlap with baseline, not a point estimate

**A point-estimate comparison is not acceptable here.** "new theta_hat
(0.91) >= old theta_hat (0.89)" looks like an improvement but can be pure
sampling noise if the confidence intervals overlap heavily. The accept
criterion is: **the new run's CI and the baseline's CI must overlap** (or
the new CI must sit entirely above the baseline's lower bound, for a claimed
improvement) for every failure mode touched by the optimization. Re-run
`judge-align-new`'s step (d)/(e) machinery (bias_correct + bootstrap_ci) on
a fresh sample after the change — don't reuse the old test split's raw
numbers as if they still describe the new prompt/routing.

If any touched failure mode's new CI falls below the baseline's CI with no
overlap, that's a real regression — revert that specific technique (not the
whole batch; apply techniques incrementally enough to isolate which one
caused it) and report why.

## Step 4 — Report

Report, per technique applied: cost delta (per-query, and at expected
volume), and per touched failure mode: baseline CI, new CI, and whether they
overlap. State the total cost reduction plainly, and state clearly if any
technique was reverted and why.
