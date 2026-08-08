---
description: Turn a raw usecase description into a full agent-system-design (staged or one-shot), a teaching_brief.md that honors it, and a built + verified end-to-end app under teaching/<slug>/ — clarify, design, brief, build, verify, in one command invocation instead of separate design-then-pipeline steps.
argument-hint: <usecase description>
---

The user has described a usecase in `$ARGUMENTS`. This command's job is to
go from that raw description all the way to a **built and verified**
teaching demo under `teaching/<slug>/`, without the user having to
separately run a design command and then `/run-teaching-pipeline` — but it
does this by *composing* those exact same gated stages in one continuous
run, not by skipping any of their approval gates. "Onego" means one
command invocation carries the user through every stage; it does not mean
fewer stops.

This differs from `/build_single_agent_from_idea` in three ways: (1) it
targets `teaching/<slug>/`, not `projects/<slug>/`, (2) it does not assume
single-agent — the full `agent-system-design` staged pipeline (or
`agent-architecture-design` one-shot) decides single-vs-multi like any
other usecase, and (3) it does not stop after the brief — it continues
through `teaching-build` and `teaching-verify` automatically once the
brief is fully approved.

## Step 0 — Slug and scope check

Derive a short `<slug>` from `$ARGUMENTS` (kebab-case). If
`teaching/<slug>/` already exists with a `teaching_brief.md`, read it and
the resume rules below instead of starting over silently — tell the user
what's already approved/built and confirm whether they want to resume,
revise, or pick a different slug.

Otherwise create `teaching/<slug>/` (same as `/new-teaching-demo <slug>`).

## Step 1 — Parse what the usecase already answers

Before asking anything, read `$ARGUMENTS` line by line and build two lists
silently, same discipline as `write-project-brief`/
`build_single_agent_from_idea`:

- **Already specified** — anything stated or clearly implied (a named
  provider, a specific data source, a UI preference, "no paid APIs",
  etc.). Restate these for confirmation, don't re-ask.
- **Still open** — everything the checklist below needs that the
  description didn't cover.

## Step 2 — Fixed clarifying checklist

Ask only the "still open" items, batched in one numbered message, grouped
by category. Every item with a defensible default gets 2-4 concrete
options plus a recommended default and a one-line reason. Only the first
two rows are genuinely open-ended.

1. **Problem & user** — what problem does this solve, for whom, and what
   does "done" look like as one concrete demo scenario?
2. **Input** — what does the system receive per invocation, in what exact
   shape?
3. **Output** — what does it produce, and does it need human review
   before taking effect (HITL) or can it act autonomously?
4. **Tools** — what does it need to call (DB, vector search, file
   parsing, external API, deterministic function)? Read-only or
   read/write? Free/local or paid (flag paid explicitly — Step 4's design
   stage resolves sourcing via `agent-decision-external-tool-sourcing` if
   the staged path is chosen)?
5. **Frontend** — Streamlit (this repo's default for demos) / Next.js
   (production-style) / notebook only (fastest path, no separate backend)
   / none (API only)? This directly decides `teaching_brief.md`'s
   `Format` field later — an architecture design alone does not determine
   this, so it must be asked here even when other answers are obvious
   from the description.
6. **Backend/API** — separate FastAPI backend, or in-process (notebook or
   single-process Streamlit)? Recommend in-process unless the usecase
   implies multiple clients or an external integration.
7. **Memory** — stateless, or does it need to remember anything across
   invocations? Roughly what shape?
8. **Provider/model** — which LLM provider (Anthropic default via
   `_shared/llm_client.py` unless stated)? Confirm no paid tools beyond
   the LLM call itself, or list which paid ones are accepted and why.
9. **Non-goals** — anything explicitly out of scope.

Ground every recommendation in the specific usecase from `$ARGUMENTS`, not
a generic category default — propose a concrete first-draft answer and
invite correction, per `build_single_agent_from_idea`'s Step 2 discipline.

## Step 2a — When the user is unsure

Same escalation as `build_single_agent_from_idea` Step 2a: offer 2-3
concrete usecase-grounded suggestions, ask one narrower follow-up to pick
between them, and only record a "your call" default in `## Decisions` if
the user still declines to choose — never a silent guess, never left as a
genuinely open question either.

## Step 3 — Architecture design

Ask the user to choose the design process:

- **Staged** (`agent-system-design`) — the full 8-stage gated pipeline,
  each stage individually approved. Recommended when tools/memory/loop
  design are non-trivial, or the user wants to see the reasoning at each
  decision point.
- **One-shot** (`agent-architecture-design`) — a single interview
  producing one `architecture_design.md` directly. Recommended for a
  small, clearly-bounded usecase where Step 2's answers already make the
  pattern obvious.

Feed Step 1/2's answers in as pre-answered context so neither process
re-asks what's already settled. Point the output at `teaching/<slug>/`:

- Staged: `teaching/<slug>/system_design/` (eight stage files, then
  `agent-system-design-assemble` produces
  `teaching/<slug>/system_design/architecture_design.md`).
- One-shot: `teaching/<slug>/architecture_design.md` directly.

Run to completion (through explicit approval at every stage) before
continuing. Do not skip a stage or infer its answer — same ground rule as
`/agent-system-design`.

## Step 4 — Draft and approve `teaching_brief.md`

1. Run `teaching-brief-from-system-design` with the approved architecture
   design and Step 2's answers, to produce an initial
   `teaching/<slug>/teaching_brief.md` draft. This fills in `Description`,
   `Format` (from Step 2's Frontend/Backend answers plus the architecture's
   runtime shape), `Happy-path test case` (draft, from the architecture's
   rollout gates), `Observability`, `Vector store`, `Constraints`, and
   `Audience level` — but marks every checkpoint `pending`, not approved.
2. Run `teaching-brief` normally from that point. Because the draft
   already answers most of its questions, `teaching-brief` should mostly
   *restate and confirm* rather than ask from scratch — but every one of
   its checkpoints (format, happy-path test case, `.env`/
   `require-api-key` real verification, observability, vector store,
   ready-to-generate) still requires real explicit approval. **Do not
   treat a pre-filled draft value as approval** — this command's "onego"
   framing applies to not needing a second command invocation later, not
   to skipping confirmation now.
3. `require-api-key`'s verification call is a hard stop exactly as in
   `/run-teaching-pipeline` — if it fails, stop completely and report the
   exact error.

## Step 5 — Build and verify, continuing automatically

Once `teaching-brief`'s step 2g ("ready to generate?") is explicitly
approved, continue immediately into the rest of `/run-teaching-pipeline`'s
sequence for this slug — this is the step that makes this command
"onego" rather than "design-then-separately-run-the-pipeline":

1. **Build** — `teaching-build`, per `teaching_brief.md`'s `Format`.
2. **Verify** — `teaching-verify`. On any failure, it automatically
   invokes `teaching-debug`/`project-debug` to iterate to a real fix, per
   its own procedure — don't stop at the first failure and report it.
3. Before `teaching-verify` (or anything else in this stage) makes a real
   LLM API call purely to verify the build works, tell the user
   approximately how many calls and an approximate cost, and get explicit
   go-ahead first — this repo's rule applies here exactly as it would in
   any other pipeline run, and it is not satisfied by the user having
   approved earlier stages of this same command.

## Step 6 — Report

Summarize: the chosen architecture pattern and where its design doc
lives, the final `teaching_brief.md`, what was built, the exact run
command(s), which provider/model (and vector store/observability, if any)
it was verified against. Point to `/add-teaching-step <slug>` for future
extension and `/fix-bug teaching <slug> <description>` for a reported bug
— don't suggest re-running this whole command for either of those.

## Ground rules

- Never skip Step 2's checklist categories, even for a usecase that
  sounds simple — an incomplete brief downstream just means the design
  and build stages guess, which is exactly what this command exists to
  prevent.
- Never skip or compress a stage from `agent-system-design`/
  `agent-architecture-design`, `teaching-brief`, `teaching-build`, or
  `teaching-verify` — this command's value is running them back-to-back
  automatically, not running them faster by cutting corners.
- Never mark a `teaching_brief.md` checkpoint approved because
  `teaching-brief-from-system-design` pre-filled it — pre-filling is a
  draft, not consent; `teaching-brief`'s own confirmation step must still
  happen for real.
- Never invoke `teaching-build`/`teaching-verify` before `teaching-brief`
  reaches an explicit "ready to generate" approval, and never make a real
  verification-purpose API call without a fresh cost estimate + go-ahead
  for that specific call, even if earlier stages in this same run already
  got approval for something else.
- If Step 3's design process surfaces a conflict with a Step 2 answer
  (e.g. user said "no memory needed" but the chosen pattern requires it),
  stop and resolve it with the user before drafting the brief — don't
  silently pick a side.
- This command produces exactly one teaching demo per invocation, for one
  usecase.
