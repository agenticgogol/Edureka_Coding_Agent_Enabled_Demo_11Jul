# Calibration protocol — formulas and file layout

All statistics come from `evallib.stats` — this file explains how the
skill's steps map onto those functions, it does not reimplement or restate
their math. If a formula here and `evallib/stats.py` ever disagree, the code
is correct and this file is stale.

## Files this skill reads and writes

```
evals/labels/<failure_mode_id>_splits.json   # INPUT — written by judge-split-new, read-only here
evals/judges/<failure_mode_id>.md            # INPUT — the judge prompt under iteration, from judge-builder-new;
                                              # its `judge_model_id` frontmatter field is the model every
                                              # step below must use
evals/labels/<failure_mode_id>.jsonl         # LabelRecord rows, dev + test only (never train)
evals/.cache/judge_results/                  # (trace_id, sha256(prompt), model_id) -> JudgeResult
evals/results/runs/<run_id>/                 # raw per-round judge output for this calibration session
evals/results/metrics.json                   # JSON array of MetricsRecord, one per failure_mode_id
```

Note what changed from this pipeline's earlier design: split assignment
used to be this skill's own step (a). It's now owned entirely by
`judge-split-new`, which runs before both this skill and `judge-builder-new`
— splitting has no dependency on a judge prompt existing, so pulling it out
breaks what used to be a circular dependency between builder and align.

## Step-by-step mapping

**(a) Human labeling + kappa.** Label dev+test traces (from the
`judge-split-new`-written split file) for this failure_mode_id as
`evallib.schema.LabelRecord(trace_id, failure_mode_id, human_label, split,
annotator, label_source)`. `annotator` has no meaningful default
(`"unspecified"` exists only for schema-evolution safety) — every writer,
chat or `label_tool`, must always supply the real name, since it's the only
thing that lets two independent annotators' rows for the same
`(trace_id, failure_mode_id)` coexist in one file and still be told apart.
`label_source` defaults to `"human"`; set it to `"ai_confirmed"`/`"ai_edited"`
only when the skill's optional AI-hint mode was used for that specific
record — see SKILL.md (a) for the opt-in prompt and the caveats around
trusting kappa/TPR-TNR computed from `ai_confirmed`-heavy label sets. If a
second annotator labels the same traces independently, filter rows by
`annotator` to build the two paired label lists (same trace order for both)
and call `evallib.stats.cohens_kappa(labels_a, labels_b)`. The **primary
annotator** (the first to label, confirmed with the user) is whose rows
feed `human_dev`/`human_test` in (b)/(c) — a second annotator's rows are for
kappa only, never merged into the primary set even where they agree.
**kappa < 0.6 blocks progress** — do not proceed to (b). Tell the user the
definition in `taxonomy.yaml` / the judge prompt's "what you are checking"
section is ambiguous enough that two humans disagree, and that sharpening
it (not re-labeling with a third tiebreaker) is the fix.

**(b) Iterate on dev only.** Run the current judge prompt, under the model
id pinned in its frontmatter, against dev-split traces (never test).
Compute `evallib.stats.tpr_tnr(human_dev, judge_dev)` each round. Report
TPR/TNR after every round so drift or improvement is visible round-over-
round, not just at the end. If the pinned model genuinely can't clear a
reasonable TPR/TNR after a few prompt-sharpening rounds, that's a signal to
reconsider the pinned model itself (update the frontmatter, with the user's
confirmation) rather than an endless prompt-tuning loop against a model
that isn't engaging with the instructions.

**(c) Read test exactly once.** After the user explicitly confirms
iteration is over, run the judge (same pinned model, same prompt) against
test-split traces with `EVAL_FINAL_VALIDATION=1` set for that read (this
satisfies hook H1, which otherwise denies any tool call touching
`evals/labels/**test**` paths). Compute `evallib.stats.tpr_tnr(human_test,
judge_test)` — this is the TPR/TNR that goes into the final metrics, not
the dev numbers from (b).

**(d) Bias-corrected estimate + CI.**
1. Decide the target population whose true positive rate you want to know
   (typically all of `evals/traces.jsonl`, or a subset the user names — ask
   if unclear). Run the judge (same pinned model) over that population to
   get the observed positive rate: `p_observed = (# judge_label=True) / (#
   traces)`.
2. `theta_hat = evallib.stats.bias_correct(p_observed, tpr, tnr)` using the
   **test-derived** tpr/tnr from (c).
3. `ci_low, ci_high = evallib.stats.bootstrap_ci(human_test, judge_test, p_observed, n_resamples=5000, alpha=0.05, random_state=<seed>)`
   — this resamples the **test** human/judge pairs to get a TPR/TNR
   distribution and re-derives theta_hat per draw, holding `p_observed`
   fixed (per the function's own docstring: p_observed comes from the
   population being measured, not the calibration set).
4. Write one `evallib.schema.MetricsRecord(failure_mode_id, n_test,
   tpr, tnr, p_observed, theta_hat, ci_low, ci_high)` — `n_test = len(test
   split)`. Merge into `evals/results/metrics.json` (read existing array,
   replace any prior record for this failure_mode_id, write the array back)
   — don't append duplicates.

**(e) Report.** State `p_observed` (raw judge positive rate on the target
population) and `theta_hat` (bias-corrected) side by side, and state
`ci_high - ci_low` as the CI width in plain language ("the true rate is
likely between X% and Y%, a Z-point-wide interval") — don't just print the
tuple and move on; a wide interval with an impressive-looking theta_hat is
still a weak result and the user needs to see that plainly. Also note: with
a small test split and a perfect (1.0/1.0) TPR/TNR, `bootstrap_ci` can
degenerate to a zero-width interval — that reflects the sample size, not
genuine certainty, and must be said out loud rather than presented as an
unqualified strong result.

## Why the dev/test boundary is absolute

`bias_correct` and `bootstrap_ci` assume the TPR/TNR they're given describe
the judge's *true* error rate against genuinely unseen data. Once the judge
prompt (or its few-shot examples, or the human iterating it) has seen a
test-split trace's label, the TPR/TNR measured on that trace is no longer an
honest estimate of out-of-sample performance — it's partly measuring
memorization/overfitting to that trace. There is no statistical correction
for this; the only fix is drawing a new test split via `/judge-split-new`
(a fresh `random_state`) and re-running (a)-(d) against it.

## Why the model id is pinned in the judge prompt's frontmatter, not chosen here

Calibration (this skill) and production (`eval-ci-new`'s CI gate) must run
the judge under the *identical* model id, or the TPR/TNR/theta_hat this
skill computes describes a different judge than the one CI actually gates
on. Reading the model id from `evals/judges/<failure_mode_id>.md`'s
frontmatter — written once by `judge-builder-new` and never re-chosen ad
hoc mid-calibration — is what keeps calibration and production from
drifting apart. If a model swap mid-calibration (e.g. an early choice
turns out not to follow the judge prompt's instructions reliably) is
genuinely necessary, update the frontmatter explicitly, with the user's
confirmation, rather than passing a different model id to the judge-calling
script without updating the file it's meant to be read from.
