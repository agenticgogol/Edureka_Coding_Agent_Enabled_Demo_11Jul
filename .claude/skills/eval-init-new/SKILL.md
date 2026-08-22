---
name: eval-init-new
description: Bootstrap an eval suite for an agent in this repo — detect its entrypoint, scaffold evals/, always draft candidate must-always/must-never rules from whatever signal exists (prior eval artifacts, docs, code), then interview the user to confirm/sharpen/extend them into evals/spec.md.
disable-model-invocation: true
---

# eval-init-new

Phase 0 of the discovery pipeline. Run this once per agent before any other
`eval-*-new` skill. It produces two things: a scaffolded `evals/` directory,
and `evals/spec.md` — the behavioral contract every later phase (labeling,
judging, CI gating) measures against.

Do not compute statistics, write traces, or invent taxonomy here. Import
nothing from `evallib.stats` in this skill — there is nothing to compute yet.

## Step 1 — Detect the agent's entrypoint

Search the repo (Glob/Grep) for how the agent under eval is actually invoked:
a CLI script, an HTTP server route, a Python function/class, a LangGraph
graph, etc. Look for `main.py`, `app.py`, `server.py`, `graph.py`, FastAPI/
Flask route decorators, `if __name__ == "__main__"` blocks, and any
`README.md`/`Makefile` run instructions.

Do not guess silently. Once you have a candidate, state it back to the user
in one sentence ("I found the agent entrypoint at `backend/agent.py:run()`,
invoked via `python -m backend.agent`") and confirm before proceeding. If you
find more than one plausible entrypoint (e.g. a CLI and an HTTP server for
the same agent), ask which one the eval suite should drive.

## Step 2 — Scaffold evals/

Create, if not already present:

```
evals/
  spec.md
  config.yaml
  traces.jsonl
  open_codes.jsonl
  labels/
  judges/
  results/
  scripts/
  .cache/judge_results/
```

**If `evallib/` doesn't already exist at the project root, copy it there
now** — every later skill imports it (`import evallib`, `python -m
evallib.cli`). If this skill is running from an installed plugin, copy from
`${CLAUDE_PLUGIN_ROOT}/evallib`; if running standalone in a repo that
already has `evallib/` at its root (e.g. this suite's own source repo),
this is a no-op. Never copy over an existing `evallib/` that has local
edits (check `git status`/diff first) — ask before overwriting.

Write `evals/config.yaml` with the confirmed entrypoint so later skills never
re-detect it:

```yaml
entrypoint:
  type: cli | http | python_function   # pick one
  command: "python -m backend.agent"    # cli: shell command; http: base URL; python_function: import path
  input_format: "stdin json | http json body | function kwarg"
  output_field: "final_response"        # where the agent's answer lands in raw output
```

Add `evals/.cache/` and `evals/results/runs/` to `.gitignore` if not already
ignored — cache and per-run output are not source of truth.

## Step 3 — Always draft candidate rules from available signal first

**This step is never skipped and never conditional on anything existing.**
Whether the project has a prior eval attempt, only docs, or nothing but the
entrypoint code, you always produce a draft before asking the user a single
question — the difference is only how much signal feeds the draft, never
whether a draft happens.

1. **Search broadly for prior eval signal — don't hardcode a name.** Glob
   for any directory anywhere under the project root that looks
   eval-related by pattern (`**/*eval*/`, `**/*qa*/` where distinct from
   test suites, etc.), not just a literal `eval_old`. If found, read
   whatever's inside — metrics/task definitions, golden sets, judge
   prompts, scan reports — for documented failure modes and invariants.
   Treat every one you use as a *candidate*, not a given: it was written by
   a different process with different assumptions, so it still needs the
   user's confirmation in Step 4, same as everything else.
2. **Independent of (1), always also scan the project itself:**
   `project_brief.md`/`design.md`/`README.md` for the problem statement,
   a "Definition of Done," or named invariants; the agent's own source for
   gate/guard/validation logic (grep for `gate`, `confirm`, `invariant`,
   `assert`, `raise`, `except`, docstrings using "must"/"never"/"always");
   and any existing test files whose names or docstrings describe expected
   behavior contracts. This runs even when step (1) found nothing, and even
   when it found plenty — code-level invariants are usually more precise
   than whatever prose described them.
3. **Draft 8-15 candidate rules** from everything gathered above, each
   phrased as must-always/must-never with a concrete "violating this looks
   like" scenario **grounded in what you actually found** — a specific gate
   name, tool name, code path, or documented task, never an invented
   generic scenario standing in for a real one.
4. If truly nothing turns up anywhere — a bare entrypoint with no docs, no
   prior eval, no comments, no tests — say so explicitly in what you present
   next, and note the draft will be thinner as a result. This is the only
   case where the draft can be very short (even zero rules), but it must
   still be presented as an explicit, stated outcome of a real search, not
   a silent skip straight to interviewing from nothing.

## Step 4 — Interview: confirm, sharpen, and extend the draft

Present the full draft from Step 3 to the user before asking anything else.
`evals/spec.md` is not a vibes document — every rule exists because grading
needs a bright line, and every rule must be falsifiable against a real
trace.

**Hard rule for every entry that ends up in the file, drafted or
user-supplied:** it must cite a concrete scenario where a real user would be
unhappy if the rule were violated. See
[references/spec_rules.md](references/spec_rules.md) for the accept/reject
examples — read it before presenting the draft.

Reject on sight and push back, asking for a sharper version, on any rule
(yours or the user's) that:

- Is unfalsifiable against a trace ("be helpful", "be professional", "use
  good judgment").
- Has no concrete failure scenario attached.
- Restates a generic LLM-safety platitude rather than something specific to
  *this* agent's domain.

Then interview (use `AskUserQuestion` where the space of answers is small,
freeform follow-up otherwise) as a **critique-and-extend** pass on the
draft, not a cold start:

1. Ask the user to edit, reject, or confirm each drafted rule.
2. Ask: "Is there anything from your own experience with this agent — a
   real session that went wrong, something you'd worry about that isn't in
   the draft — that should become its own rule?" Push for the same
   concreteness as the draft rules. Convert answers into new must-never
   rules with the scenario attached.
3. Ask the same for must-always rules: "What must this agent always do, no
   matter what the user asks, that the draft doesn't already cover?"
4. Keep going until the user is out of additions, then read the full final
   list back for confirmation before writing the file.

Target 8-20 rules total — fewer than 8 usually means the search-and-interview
stopped too early; more than 20 usually means some rules are overlapping and
should merge.

## Step 5 — Write evals/spec.md

Format:

```markdown
# Eval Spec — <agent name>

## Must always
- **[MA-1]** <rule>. Violating this looks like: <concrete scenario>.
- **[MA-2]** ...

## Must never
- **[MN-1]** <rule>. Violating this looks like: <concrete scenario>.
- **[MN-2]** ...
```

Number rules stably (`MA-1`, `MN-1`, ...) — later phases (judge prompts, the
backlog, CI gates) reference these IDs, so don't renumber on edits; append or
mark deprecated instead.

## Step 6 — Report

Summarize: entrypoint detected, files created, rule count by must-always/
must-never, and how many rules originated from the Step 3 draft vs. were
added fresh in the Step 4 interview. Tell the user the next step is
`/eval-dataset-new`.
