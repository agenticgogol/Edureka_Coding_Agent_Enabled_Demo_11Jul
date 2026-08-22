---
name: open-codin-new
description: Serve unannotated traces in batches for open coding — full trace shown, freeform note taken, first-failure-turn marked. Freeform by default; an opt-in AI-hint mode can suggest a failure/category as a starting point for lazy or new annotators, always caveated and always overridable. Annotation can happen inline in chat, or handed off to the local annotation_tool browser UI — asked explicitly before any handoff.
disable-model-invocation: true
argument-hint: "[batch-size]"
---

# open-codin-new

Phase 2 of the discovery pipeline: open coding. Requires `evals/traces.jsonl`
from `/eval-dataset-new` — if missing or empty, stop and say so.

`$ARGUMENTS` is the batch size. If not provided, ask the user (default: 10).

**Default posture: you must never suggest, name, or hint at a failure
category while the user is annotating**, unless the user has explicitly
turned on hint mode for this session (Step 2). Open coding exists to let
categories emerge from the user's own words in Phase 3 (axial coding) — an
unprompted suggestion contaminates the taxonomy with your priors instead of
theirs. If the user asks you directly what you think the issue is and hint
mode is off, decline and redirect: "I want your read on it before I say
anything — what did you notice?" — or point them at Step 2 to turn hints on
for the rest of the session.

**Hint mode does not change what "the record" means.** Even with hints on,
what gets written to `evals/open_codes.jsonl` must reflect the human's
actual judgment — confirmed, edited, or overridden — never the AI's guess
accepted by default. See Step 3b and the provenance-tagging rule below.

## Step 1 — Load state

Read `evals/traces.jsonl` (`evallib.schema.Trace`, via `evallib.jsonl`).
Read `evals/open_codes.jsonl` if it exists (`evallib.schema.OpenCode`) —
otherwise treat it as empty. A trace is "annotated" if its `query_id`
appears as `trace_id` in any existing `OpenCode` record. Compute the
unannotated set; if empty, report that open coding is complete and stop
(don't loop back to axial coding here — that's a separate skill).

## Step 2 — Ask about hint mode (once per session)

Before serving the first batch, ask the user directly:

> "Do you want AI-generated hints while annotating — a suggested failure
> description and rough category per trace, for you to confirm, edit, or
> ignore? This is meant for a first pass or when you're new to this agent,
> **not a substitute for your own read** — an AI guess can anchor your
> judgment toward categories that seem plausible but aren't what's actually
> there, which is exactly what open coding exists to avoid. Default is off."

Record the answer for the rest of the session (don't re-ask per batch).
Default to **off** if the user doesn't express a preference — the burden of
opting in is deliberate.

## Step 2b — Ask which interface to annotate through (once per session)

**Ask explicitly before handing off — never switch interfaces silently,**
even if the tool is present in the repo. Ask:

> "Do you want to annotate right here in this conversation (I ask you about
> each trace, one at a time), or should I hand off to the local annotation
> tool — a browser UI at `agent-eval-suite/annotation_tool/` where you
> click through traces yourself at your own pace? Either way the same
> `evals/open_codes.jsonl` gets written, in the same format."

Record the answer for the rest of the session, same as hint mode. If the
user wants to switch mid-session, honor that immediately rather than
waiting for the next batch. If `agent-eval-suite/annotation_tool/app.py`
isn't present in this repo, don't offer the tool option — chat is the only
choice.

## Step 3 — Serve one batch

Take the next `batch_size` unannotated traces, in file order (don't shuffle
— reproducible batches make saturation tracking in Step 4 meaningful).

### Interface: chat (Step 2b answer)

For each trace, one at a time:

1. **Show the full trace.** Every turn, in order: role, content, tool calls
   with arguments, tool results, retrieved docs if present, and the final
   response. Don't summarize or truncate — the whole point of open coding is
   the annotator sees exactly what happened. Include `query_id` and
   `dimension_tuple` for context.

2. **(Hint mode only) Show the AI hint before asking anything.** Generate,
   from the trace alone: a guess at `is_failure`, a guess at
   `first_failure_turn_index` (or none), a one-line description of the
   suspected problem, and a rough candidate category label. Present it
   clearly marked as unvalidated, e.g.:

   > **AI hint (unvalidated — please check this yourself):**
   > Looks like a possible failure at turn 2. Rough description: the agent
   > confirmed a refund without checking eligibility first. Rough category:
   > *skipped-eligibility-check*.
   > This is a guess, not a finding — confirm, edit, or ignore it below.

   This candidate category is scratch context for the human only — it is
   **never** written to `evals/open_codes.jsonl` as structured data (the
   `OpenCode` schema has no category field, and axial coding in Phase 3 is
   the only place categories get formally derived). If the human's final
   note repeats the hint's category language, that's their own word choice,
   not a system-assigned label.

3. **Ask for a freeform note.** Literally ask "What did you notice? Anything
   that seems off, or nothing?" — open text, no multiple choice, no
   suggested options beyond the hint already shown (if hint mode is on).
   Accept any of: their own independent note, "confirm the hint as
   written," or an edited version of the hint's description. If the user's
   note is empty or just "looks fine," that is a valid note (record
   `is_failure: false`).
4. **Ask which turn was the FIRST place things went wrong** — not which turn
   contains the final wrong answer. Say this explicitly: "Which turn index
   is where things first went off track — not necessarily where the bad
   answer appears, but the earliest turn where a mistake, a missed check, or
   a bad decision happened?" Accept "none" / null for a non-failure trace.
   Turn indices are 0-based, matching `Trace.turns` list order. If hint mode
   suggested an index, the human confirming it counts as their answer — but
   the question must still be asked, never silently defaulted to the hint.
5. **Confirm `is_failure`.** True if the note describes any problem, however
   minor — open coding should over-flag rather than under-flag; axial coding
   later decides what's worth a category.

**Provenance tagging (hint mode only).** Prefix the saved `note` text with
one of `[hint-confirmed]`, `[hint-edited]`, or `[independent]` (independent
= hint was shown but the human's note doesn't derive from it) so later
phases can see how much of the session was AI-assisted vs. fully human —
`axial-coding-new` and `eval-critic` both read this signal. When hint mode
is off, never add a prefix.

Append one `evallib.schema.OpenCode` per trace (`trace_id` = the trace's
`query_id`, `annotator` = the user — ask their name/handle once per session
and reuse it, `first_failure_turn_index`, `note`, `is_failure`). Read-modify-
write `evals/open_codes.jsonl` after each trace (not just at the end) so a
crash mid-batch doesn't lose earlier annotations in the batch.

### Interface: tool (Step 2b answer)

The tool makes no model calls itself (see its own README) — any AI hints
still have to come from you, written to a file, before you hand off.

1. **(Hint mode only) Pre-generate hints for this batch.** For each of the
   batch's traces, generate the same guess you'd otherwise show inline (a
   guess at `is_failure`, a guess at `first_failure_turn_index` or none, a
   one-line description, a rough candidate category) and append one row per
   trace to `evals/open_code_hints.jsonl`:
   `{"trace_id": "...", "note": "<one-line description>", "is_failure":
   <bool>, "first_failure_turn_index": <int|null>, "category": "<rough
   label>"}`. Read-modify-write (append, don't overwrite — hints from
   earlier batches must survive). If hint mode is off, skip this — the tool
   handles a missing/empty hints file fine, it just shows no hint.

2. **Locate `app.py` before launching** — it lives at
   `${CLAUDE_PLUGIN_ROOT}/annotation_tool/app.py` when running as an
   installed plugin, or `agent-eval-suite/annotation_tool/app.py` relative
   to the repo root when running standalone in this suite's own source repo
   (no `CLAUDE_PLUGIN_ROOT` set). Check which applies rather than assuming.

3. **Launch it, once per session, in the background** (it's a long-running
   local server — never run it in the foreground, that would block the
   rest of this skill):
   ```
   python <resolved app.py path> \
       --traces evals/traces.jsonl \
       --hints evals/open_code_hints.jsonl \
       --annotations evals/open_codes.jsonl
   ```
   If it's already running from an earlier batch this session, don't
   relaunch — it re-reads state on every page load, so new hint rows from
   step 1 show up automatically on refresh.

4. **Tell the user the URL** (`http://127.0.0.1:8765` unless a different
   `--port` was used) and that it covers every trace in
   `evals/traces.jsonl`, not just this batch — traces without a hint row
   yet just show "No AI hint for this trace," which is expected for
   anything outside the current batch.

5. **Wait.** Don't proceed to Step 4 until the user says they're done with
   this batch (or wants a progress check) — this interface is
   self-paced, not something you drive turn by turn. When they say so, read
   `evals/open_codes.jsonl` fresh to see what's actually been saved before
   reporting.

Provenance tagging is handled by the tool itself (`[hint-confirmed]` /
`[hint-edited]` / unprefixed for independent) — don't re-tag its output.

## Step 4 — Batch report

Identical for both interfaces — it only reads `evals/open_codes.jsonl`,
which has the same shape either way.

**Validate before reporting anything, every batch — this is what makes
downstream consumption safe.** Run
`python -m evallib.cli validate --model open-code --file evals/open_codes.jsonl`.
This matters for both interfaces, but especially the tool one: its writes
happen in a separate process outside your own construction of the record,
so this is the actual verification that what landed on disk is what
`axial-coding-new` (via `trace-reader`) can actually consume — not an
assumption. If it reports any invalid rows, stop and fix them (don't hand
this off broken) before continuing to the rest of this step's report.

After the batch, report:

- **New-failure-type rate for this batch.** You (Claude) may read the notes
  from this batch and compare them, at a glance, against notes from prior
  batches to estimate how many describe a *kind* of problem not seen before
  — this is a rough eyeball estimate for pacing, not a taxonomy decision, and
  it must not be phrased to the user as proposed categories. Report as e.g.
  "3 of 10 notes this batch look like new failure types; 7 look like repeats
  of what you've flagged before."
- **Saturation signal.** If the last two consecutive batches each had a
  new-failure-type rate at or near zero, tell the user saturation looks
  plausible and axial coding (`/axial-coding-new`) may already have enough
  signal — but this is advisory, not a stop condition; let the user decide
  whether to keep going.
- **Hint-mode breakdown, if hint mode was on this batch:** counts of
  `[hint-confirmed]` / `[hint-edited]` / `[independent]`. If
  `[hint-confirmed]` is most of the batch, say so plainly and suggest
  turning hints off for a few traces to sanity-check that the human read is
  still doing independent work, not just rubber-stamping.
- Remaining unannotated trace count.

## Step 5 — Continue or stop

Ask whether to run another batch now or stop here (hint-mode and interface
preferences from Step 2/2b carry over automatically). If continuing, repeat
from Step 3 with the next batch — for the tool interface, the server is
already running, so this just means generating the next batch's hints (if
hint mode is on) and telling the user to keep going in the browser.
