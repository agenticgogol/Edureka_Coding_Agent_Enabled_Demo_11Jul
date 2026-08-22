---
description: Run the full eval-init-new -> eval-ci-new (-> cost-optimize-new) grounded-theory eval pipeline end to end for one agent, stage by stage, respecting every skill's own human-judgment pause and cost-approval gate.
argument-hint: [project-folder] [fast-forward] [through-cost-optimize]
allowed-tools: Skill, Bash, Read
---

Run the "-new" eval suite (`eval-init-new` through `eval-ci-new`, optionally
`cost-optimize-new`) end to end for the agent under evaluation, in the exact
sequence `eval-loop`'s phase table defines. This command's only job is
**continuity of state and not re-typing each slash command between
phases** — it does NOT replace any skill's own interview, approval, or
cost-confirmation step. Every one of those still happens exactly as it
would if the user ran the skill standalone.

## Step 0 — Resolve the working directory

Parse `$ARGUMENTS`. The first token, if present and not `fast-forward` or
`through-cost-optimize`, is the project folder to run the eval suite
against (e.g. `teaching/incident-root-cause-agent`) — treat all `evals/`
paths below as relative to that folder for the rest of this run. If no
folder is given, ask which project/agent this run targets before doing
anything else; do not guess from whatever the current directory happens to
be.

Recognize `fast-forward` and `through-cost-optimize` anywhere in
`$ARGUMENTS` (see Step 3 and Step 5).

## Step 1 — Determine current state

Invoke the `eval-loop` skill (Step 1 of its own SKILL.md) to read
`evals/pipeline_state.json` and cross-check it against `references/phase_detection.md`'s
artifact map, scoped to the resolved project folder. Report the current
cycle/phase before doing anything else — this command resumes from wherever
the project actually is, it never restarts from phase 0 on an existing
project.

## Step 2 — The phase sequence

Run phases **in this exact order**, one at a time, each via its own skill
(never skip a phase, never reorder, never run two phases' skills
concurrently):

| Phase | Skill(s) to invoke | Notes |
|---|---|---|
| 0 | `eval-init-new` | Entrypoint detection + `spec.md` interview. |
| 1 | `eval-dataset-new` | Dataset generation — involves a real-API cost-approval gate. |
| 2 | `open-codin-new` | Freeform human annotation — cannot be automated away; see Step 4. |
| 3 | `axial-coding-new` | Taxonomy synthesis — requires explicit user approval of the proposed clusters. |
| 4 | `evaluator-design-new` | Code-vs-judge routing. |
| 5 | `judge-split-new`, then `judge-builder-new` | **Repeat this pair once per `method: judge` entry** in `evals/evaluators/routing.yaml` — `judge-split-new` first (split), then `judge-builder-new` for that same `failure_mode_id` (few-shot curation + the exact-model-id question). If a failure mode has no `method: judge` entries at all, skip straight to phase 6 with nothing to do here. |
| 6 | `judge-align-new` | **Repeat once per judge-routed failure mode from phase 5.** Involves the kappa gate, the mandatory explicit "yes" before reading test, and real-API cost approval for dev/test/population runs. |
| 7 | `eval-ci-new` | CI wiring — reads each judge's pinned model id from its own frontmatter (no separate question here, per the fix already applied to these skills). |
| 8 | `cost-optimize-new` | **Only if `through-cost-optimize` is in `$ARGUMENTS`.** Gated on the backlog having no open high-severity items (same Gate C `eval-loop` enforces) — if that gate isn't met, stop here and report it rather than running phase 8 anyway. |

`eval-dashboard-new` is not a numbered phase — it's invoked automatically by
`judge-align-new` (phase 6) and `eval-ci-new` (phase 7) every time either
produces a metric, per those skills' own instructions. If either phase
reports its append-history call didn't fire (e.g. the project predates
`eval-dashboard-new`), run `/eval-dashboard-new` once yourself before
continuing, rather than letting the dashboard silently fall behind.

Skip a phase only if `eval-loop`'s own artifact check (Step 1) already
shows it complete for this project — never because it "seems done." If
resuming mid-pipeline, start at the first phase `eval-loop` reports as not
yet complete.

## Step 3 — Respect every pause, always

**"Run the whole pipeline" does not mean "skip review points."** Every
pause built into the individual skills still fires exactly as it would if
invoked standalone:
- `eval-dataset-new`'s dimension interview and trace-generation cost
  approval.
- `open-codin-new`'s hint-mode question, interface choice, and the
  human note/first-failure-turn question for every single trace — this
  cannot be shortened or answered on the user's behalf.
- `axial-coding-new`'s cluster approval (approve/merge/split/reject).
- `evaluator-design-new`'s routing (usually fully mechanical, but still
  report the routing table before moving on).
- `judge-builder-new`'s Step 0 (split existence + the exact judge-model-id
  question) and Step 2's few-shot curation approval.
- `judge-align-new`'s hint-mode/interface questions, the kappa gate, and
  — this is the one that must NEVER be inferred — the explicit "yes, run
  final validation" confirmation before reading the test split. A
  re-invocation of this command, or silence, is not that confirmation;
  ask directly, the same way the skill's own SKILL.md requires.
- Every real-API-cost step across every phase (`--estimate` first, then
  explicit approval) — never bypass this repo's cost-approval rule
  regardless of `fast-forward`.

**Unless `fast-forward` is in `$ARGUMENTS`**, stop and wait at every one of
these points, exactly as standalone. **If `fast-forward` is present**, you
may proceed through *judgment-call* pauses on your own best judgment where
a skill explicitly allows a default (e.g. hint-mode default off, primary
annotator default to first labeler) — but real-money cost approvals and the
test-split "yes" confirmation are never skipped by `fast-forward`; those
require the user regardless. Log every assumption made in place of a user
decision plainly in your Step-6 report ("ASSUMED: kept hint mode off for
open coding, no user preference given").

## Step 4 — Phase 2 (open coding) cannot be fully automated

Be explicit with the user before starting phase 2: this phase's entire
purpose is capturing an independent human read of the traces (see
`open-codin-new`'s own hint-mode caveats) — this command will drive the
batch loop and ask the required questions per trace, but it cannot supply
the human's own judgment for "what did you notice." If the user wants to
delegate this to hints, that's their call to make via the hint-mode
question, not a default this command picks silently.

## Step 5 — Cross-phase invariants

Keep enforcing, across every phase this command runs, the three
AI-eval-suite invariants from this project's CLAUDE.md: no metrics before
real error analysis, no statistics computed outside `evallib.stats`, and no
test-split read outside `judge-align-new` step (c) with
`EVAL_FINAL_VALIDATION=1` explicitly set for that one call. If any phase's
own skill would violate one of these, that skill's own instructions already
stop it — this command doesn't add new logic here, it's a reminder that
"run everything" is not license to relax any of them.

## Step 6 — Report after every phase, and at the end

After each phase completes, narrate: which skill ran, what artifact(s) it
produced (file path), and any user decision captured (or, in fast-forward
mode, assumed). Update `evals/pipeline_state.json` the same way `eval-loop`
does after every phase (this command IS driving `eval-loop`'s dispatch
logic phase by phase, not a separate state machine).

When the sequence reaches its stopping point (phase 7 by default, phase 8
if `through-cost-optimize` was given, or an unmet gate/required pause it
had to stop at), give a final summary:
- a table of every artifact produced this run and its path
- taxonomy size and backlog top items (if phases 2-3 ran)
- routing split (N code / M judge) and, per judge, its pinned model id and
  calibration TPR/TNR/theta_hat (if phases 4-6 ran)
- CI status: hook installed, workflow path, model(s) pinned (if phase 7 ran)
- the path to `evals/results/dashboard.html` and its current run count (if
  any phase 6/7 work happened this run)
- what phase is next and what (if anything) is blocking it

## Step 7 — Re-invocation

On a later run of this same command against the same project folder,
re-read `evals/pipeline_state.json` first (Step 1) and resume from the
first incomplete phase — never restart from phase 0 on a project that
already has progress, and never silently re-run a phase whose gate is
already satisfied.
