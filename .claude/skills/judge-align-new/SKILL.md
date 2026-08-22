---
name: judge-align-new
description: Calibrate one judge — human-label (with an opt-in, always-caveated AI-hint mode), iterate on dev, validate on test exactly once, compute the bias-corrected estimate and its CI. The rigorous core of the eval suite.
disable-model-invocation: true
argument-hint: "[failure-mode-id]"
---

# judge-align-new

Phase 6: judge calibration. Requires **both** `evals/judges/<failure_mode_id>.md`
from `/judge-builder-new` **and** `evals/labels/<failure_mode_id>_splits.json`
from `/judge-split-new` — if either is missing, say so and tell the user
which skill to run first (in that order: `judge-split-new` before
`judge-builder-new`, since the latter needs the split to pick few-shot
examples). `$ARGUMENTS` is the `failure_mode_id`; ask if not given.

Read [references/calibration_protocol.md](references/calibration_protocol.md)
before starting — it maps every step below onto the exact `evallib.stats`
call and file layout. **Do not compute kappa, TPR/TNR, bias correction, or a
CI yourself, inline, in any form — call `evallib.stats`.** That module is
the only place in this repo those formulas exist; reimplementing them here,
even "just to double check," creates a second source of truth that will
drift.

**Read the pinned model id from the judge prompt's frontmatter before
calling anything.** `evals/judges/<failure_mode_id>.md` has a
`judge_model_id` field (written by `judge-builder-new`) — every judge call
in steps (b)-(d) below MUST use exactly that model id, sourced from that one
place, every time. Never pick a model ad hoc mid-calibration (e.g. because a
cheaper or newer model seems tempting) without going back to update the
frontmatter first — a model swap that isn't reflected in the frontmatter is
exactly what makes `eval-ci-new` pin a different model than what was
actually calibrated, forcing a full, avoidable redo of dev+test+population
calibration. If dev/test performance is weak under the pinned model and you
genuinely need to try a different one, update the frontmatter's
`judge_model_id` explicitly (with the user's confirmation) before
continuing — don't let it drift silently.

**The dev/test boundary is absolute. Read this before step (b):** iterating
the judge prompt against, or even glancing at, a test-split trace's human
label during step (b) invalidates the TPR/TNR you'll measure in step (c) —
there is no statistical fix for it afterward. The only remedy is drawing a
fresh test split (`/judge-split-new` with a new seed) and starting (a)
through (d) over. Treat every test-split trace as off-limits until step (c)
explicitly says otherwise.

## (a) Human labeling on dev + test, kappa gate

Run a labeling loop over dev+test trace_ids only (never train — train is
reserved for `judge-builder-new`'s few-shot curation). Write
`evallib.schema.LabelRecord` rows to `evals/labels/<failure_mode_id>.jsonl`.

**This is the highest-stakes labeling in the whole pipeline — read this
before offering hints.** These labels are what `cohens_kappa` and
`tpr_tnr`/`bias_correct`/`bootstrap_ci` are computed *from*. If a "human"
label is actually an AI guess the human passively accepted, kappa stops
measuring independent agreement and TPR/TNR stops measuring the judge
against real ground truth — both start silently measuring "does this agree
with an AI" instead, with no error or warning anywhere downstream to catch
it. Everything below exists to make that risk visible and auditable, not to
eliminate the option — this repo's convention is opt-in AI hints with
mandatory human confirmation, same as `open-codin-new`.

**Ask once per session, before labeling starts:**

> "Do you want an AI-suggested label per trace — a guess at `human_label`
> plus its reasoning, for you to confirm, edit, or ignore? This speeds up
> labeling but **the label you approve becomes the ground truth this
> judge's accuracy is measured against** — an AI guess you passively accept
> is not independent validation, it's the judge partially grading itself.
> Default is off. If you use it, consider keeping it off for at least the
> test split specifically, since that's the number that becomes your final
> reported accuracy."

Default **off**.

**Ask which interface to label through, once per session, before labeling
starts (same pattern as `open-codin-new`, never switch silently):**

> "Annotate right here in chat, or hand off to `label_tool` — a browser UI
> like the open-coding one, scoped to this one failure mode? Either way the
> same `evals/labels/<failure_mode_id>.jsonl` gets written."

**Interface: chat.** For each trace: show the full trace, then (hint mode
only) show "**AI-suggested label (unvalidated):** `<True/False>` —
`<one-line reasoning>`. Confirm, edit, or give your own." Whatever the human
ends up with is what's written as `human_label` — always their call, never a
default-accepted AI value.

**Interface: tool.** Locate `label_tool/app.py` — `${CLAUDE_PLUGIN_ROOT}/label_tool/app.py`
when running as a plugin, `agent-eval-suite/label_tool/app.py` standalone.
If hint mode is on, first write hint rows to
`evals/labels/<failure_mode_id>_hints.jsonl` (same guess-generation as chat
mode, one row per dev/test trace_id: `{"trace_id": ..., "suggested_label":
<bool>, "reasoning": "..."}`). Launch in the background (never foreground):
```
python <resolved app.py path> --traces evals/traces.jsonl \
    --splits evals/labels/<failure_mode_id>_splits.json \
    --failure-mode-id <failure_mode_id> \
    --hints evals/labels/<failure_mode_id>_hints.jsonl \
    --annotations evals/labels/<failure_mode_id>.jsonl \
    --annotator <name>
```
Give the user the URL, then wait — don't proceed until they say they're
done. The tool enforces the dev/test-only boundary itself (it reads
`_splits.json` and never shows a train-split trace) and writes `annotator`
and `label_source` the same way chat mode does. Once they're done, run
`python -m evallib.cli validate --model label-record --file evals/labels/<failure_mode_id>.jsonl`
before doing anything else with the file — its writes happened in a
separate process, so this is real verification that what's on disk is what
(b)/(c)/(d) can actually consume, not an assumption.

**Either interface: every `LabelRecord` must carry the labeling annotator's
name in `annotator`** — ask for it once per session (chat) or pass it as
`--annotator` (tool) and reuse it for every row written that session. This
is what makes a second annotator's rows distinguishable from the first
within the same `evals/labels/<failure_mode_id>.jsonl` file — without it,
`cohens_kappa` has no way to pair "annotator A's label for trace X" against
"annotator B's label for trace X." Record `label_source` accordingly:
`"human"` (hint mode off, or hint shown but the human's answer didn't come
from it), `"ai_confirmed"` (accepted as-is), or `"ai_edited"` (changed).

**Designate a primary annotator.** The first person to label is the primary
by default (confirm this with the user, don't assume) — their rows are what
steps (b)/(c)/(d) read as `human_dev`/`human_test`. A second annotator's
rows exist only to compute kappa (filter both annotators' rows by
`annotator`, pair by `trace_id`, same order, call
`evallib.stats.cohens_kappa(labels_a, labels_b)`) — never merged, averaged,
or silently substituted for the primary's labels, even where the two agree.

**Before reporting kappa, check both annotators' `label_source` mix.** If
both sets are mostly `ai_confirmed`, say so explicitly alongside the kappa
number — two people confirming the same AI hints will agree with each other
for reasons that have nothing to do with the failure-mode definition being
clear, and a high kappa under those conditions is not evidence of anything.
Recommend re-labeling with hints off for at least one annotator before
trusting a kappa computed this way.

**kappa < 0.6 stops the pipeline here.** Tell the user plainly: two humans
disagreeing this much means the failure-mode definition in `taxonomy.yaml`
(and the judge prompt's "what you are checking" section) is ambiguous, not
that one annotator is wrong. Send them back to sharpen the definition before
re-labeling — do not average, tiebreak, or proceed with a low-kappa label
set.

**Before step (c)'s test read, check the test-split `label_source` mix on
its own, regardless of kappa.** If test-split labels are mostly
`ai_confirmed`, warn the user plainly that the TPR/TNR and CI this run
produces will be measuring the judge against partially AI-generated ground
truth, and offer to re-label the test split independently (hints off)
before proceeding — this is advisory, not a hard block, but it must be said
out loud before (c) runs, not discovered later.

## (b) Iterate against dev only

Run the judge prompt, under the model id pinned in its frontmatter (see
above — never a different one chosen ad hoc), against dev-split traces.
Build `human_dev` from the **primary annotator's** `LabelRecord` rows only
(filter by `annotator` — see (a)) — never a second annotator's rows, even
post-kappa. Compute
`evallib.stats.tpr_tnr(human_dev, judge_dev)`. Report TPR/TNR after every
round. If TPR/TNR looks weak, revise the judge prompt (sharpen the
definition, adjust few-shot examples — still train-only) and re-run against
dev. Cache judge calls by `(trace_id, sha256(judge_prompt), model_id)` under
`evals/.cache/judge_results/` so re-running dev after a small prompt edit
doesn't re-bill unchanged traces. Before the first real run each session,
run in `--estimate` mode to print projected call count and cost, and get
explicit approval per this repo's real-API-cost-approval rule before the
real run.

Do not loop over dev traces one-by-one inside your own turns for this — shell
out to a script that batches, retries, and applies the cache, and have it
return you the aggregate TPR/TNR plus the disagreement list. Iterating a
judge prompt means many rounds; keeping each round cheap and low-turn is
what makes that practical.

## (c) Read test — exactly once

Ask the user to explicitly confirm iteration is done ("yes, run final
validation" or equivalent — do not infer this from silence or from TPR/TNR
looking good enough). On confirmation, set `EVAL_FINAL_VALIDATION=1` for
that one read (this is what satisfies hook H1's guard on test-split paths —
without it, the read is denied). Run the judge (same pinned model id, same
prompt) against test-split traces once. Build `human_test` from the
primary annotator's rows only, same rule as (b). Compute
`evallib.stats.tpr_tnr(human_test, judge_test)`. This TPR/TNR — not the dev
numbers from (b) — feeds step (d).

If, after seeing the test result, the user wants to change the judge prompt
and re-check: that requires a fresh split (`/judge-split-new` with a new
`random_state`) and a full re-run of (a)-(d) here (plus re-curating few-shot
examples in `judge-builder-new` against the new train split). Say this
explicitly rather than letting them re-read the same test split.

## (d) Bias-corrected estimate + CI

Decide the target population (ask the user if unclear; default: all of
`evals/traces.jsonl`). Run the judge (same pinned model id) over it to get
`p_observed` (positive rate). Then:

```
theta_hat = evallib.stats.bias_correct(p_observed, tpr, tnr)   # tpr/tnr from step (c)
ci_low, ci_high = evallib.stats.bootstrap_ci(human_test, judge_test, p_observed,
                                              n_resamples=5000, alpha=0.05, random_state=<seed>)
```

If `bias_correct` raises (tpr + tnr <= 1), stop — the judge is at or below
chance on test and no correction is valid. Report this plainly and send the
user back to `judge-builder-new` to rebuild the prompt, not back to (b) to
keep tuning against dev (a judge this bad on held-out data needs a rebuild,
not a tweak).

Write `evallib.schema.MetricsRecord(failure_mode_id, n_test=len(test_split),
tpr, tnr, p_observed, theta_hat, ci_low, ci_high)`. Merge into
`evals/results/metrics.json` (JSON array; replace any existing record for
this `failure_mode_id`, don't duplicate).

Then call `evals/scripts/append_metrics_history.py --run-type calibration
...` (see `eval-dashboard-new`'s SKILL.md for the exact flags) so this run
joins the accumulating history behind `evals/results/dashboard.html` — this
overwrites nothing (unlike `metrics.json` above), it's the append-only
record of every calibration this failure mode has ever had. If that script
doesn't exist yet in this project, run `/eval-dashboard-new` once to set it
up, then continue.

## (e) Report

State, side by side: the raw observed rate (`p_observed`) and the
bias-corrected estimate (`theta_hat`). State the CI width in plain language
— `ci_high - ci_low` as a percentage-point spread, and say directly whether
that's a tight or wide interval for the decision the user is trying to make
with it. Report kappa (if computed) and the dev-round history from (b) for
context. **Report the dev and test `label_source` mix** (counts of
`human`/`ai_confirmed`/`ai_edited`) alongside the numbers, every time hint
mode was used at all this run — this is what lets a reader of
`evals/results/metrics.json` (or `eval-critic`) tell a fully independent
calibration apart from an AI-assisted one without having to ask. Tell the
user this judge is now validated and safe to cite in CI gates or reports —
until this ran, hook H4 will keep warning that it isn't.
