---
name: trajectory-eval-new
description: Evaluate tool selection, tool-argument validity, and execution success as separate code-based checks, and attribute failed traces to the earliest diverging step rather than the final answer. Use when trajectory/tool-use quality is in question, not just final-answer correctness.
---

# trajectory-eval-new

Most eval effort goes to the final answer. This skill deliberately doesn't
— it scores the *path* the agent took, and for failed traces, finds where
that path first went wrong. A trace can produce a correct final answer
despite a bad trajectory (it got lucky, or recovered) and a wrong final
answer despite a good trajectory up to the last step — treating "the final
answer was wrong" as the whole diagnosis blames the wrong turn most of the
time.

## Step 1 — Three separate code-based checks

Write these as pytest-style functions over `evallib.schema.Trace`, one file
per check under `evals/evaluators/trajectory/`, each returning a bare `bool`
(pass = True) — same convention as `evaluator-design-new`'s code evals:

1. **Tool selection.** For each `ToolCall` in a trace, was it an
   appropriate tool given the turn's context? This one usually needs a
   reference: build it from `evals/spec.md` rules that name specific tools
   (e.g. "must call `check_refund_eligibility` before `issue_refund`") and
   from patterns you see across `evals/traces.jsonl` — a tool called with no
   prior turn that would justify it is a selection failure.
2. **Argument syntax validity.** For each `ToolCall.arguments`, do they
   match the tool's actual parameter schema (types, required fields, enum
   values)? This is a pure structural check — validate against the tool
   definitions the agent's code exposes (read them from source, don't
   guess), not a semantic judgment.
3. **Execution success.** For each `ToolResult`, did it complete without
   `is_error`? This one's nearly free — it's already a field on the trace.

Keep these three independent and separately reported — a trace can pass (1)
and (3) but fail (2) (right tool, malformed args, yet the tool endpoint
silently coerced or ignored the bad arg and "succeeded" anyway), and
collapsing them into one score hides that.

## Step 2 — Build the transition failure matrix

Use `scripts/transitions.py` — do not reimplement state-sequence extraction
or divergence-finding inline.

1. `state_sequence_from_trace_dict(trace)` for every trace in
   `evals/traces.jsonl` (group by `dimension_tuple` or a task identifier —
   traces with the same intent should share a similar reference path).
2. For each group, pick or construct a **reference sequence**: either the
   most common sequence among non-failing traces in that group (the mode),
   or, if the group has no clean non-failing example, ask the user to
   confirm what the reference path *should* look like — the taxonomy
   `open_codes.jsonl`/`is_failure` markers tell you which traces to exclude
   from candidacy as reference.
3. `failure_divergence_report(failed_sequences, reference_sequence)` per
   group — gives each failed trace's earliest diverging state index.
4. `build_transition_matrix(all_sequences)` across the full trace set, and
   `most_common_divergence_state(...)` per group — this ranks which state
   (which tool call, which result type) is most often where things first go
   wrong, which is the thing worth fixing first.

Write `evals/trajectory/transition_matrix.json` (the raw counts) and
`evals/trajectory/divergence_report.json` (trace_id -> earliest divergence
index and state, per group).

## Step 3 — Report

Report, separately: pass rates for tool-selection / argument-validity /
execution-success across the trace set; then the divergence ranking —
"N of M failed traces first diverge at `<state>`" — as the primary
attribution signal. State explicitly that this ranking, not final-response
inspection, is where to start fixing the agent. Cross-reference against
`evals/backlog.md` if a taxonomy already exists — a state that shows up
heavily in the divergence ranking and matches a high-severity backlog item
is a strong double-confirmation of where to focus.
