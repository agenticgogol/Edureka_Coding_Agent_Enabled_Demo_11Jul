---
name: evaluator-design-new
description: Decide whether each failure mode in evals/backlog.md should be checked with code (a script/assertion) or an LLM judge, write the code checks, and record every routing decision with a one-line rationale. Use after axial coding produces a taxonomy and backlog, or when asking "should this be a code check or a judge?"
---

# evaluator-design-new

Phase 4: routing. Requires `evals/taxonomy.yaml` and `evals/backlog.md` from
`/axial-coding-new` — if missing, say so and stop.

Read [references/code-vs-judge.md](references/code-vs-judge.md) before
routing anything — it's the actual decision rule, including the accept
criteria for each route and the target mix. Do not route from memory.

## Step 1 — Route every failure mode

For each `AxialCode` in `evals/taxonomy.yaml`, decide `code` or `judge`
using the reference doc's criteria. Write the decision and a one-line
rationale immediately — don't batch this to the end, it's easy to lose the
reasoning if you defer it.

Target roughly 2-3 code evals per 1-2 judges. If your routing comes out
far from that mix (e.g. everything routed to judge), stop and re-read each
`definition` in `taxonomy.yaml` looking for a structural signal you missed
before accepting the judge route — see the reference doc's warning-sign
section.

Append to `evals/evaluators/routing.yaml`:

```yaml
- failure_mode_id: <code_id>
  method: code | judge
  rationale: "<one line, cites the specific structural signal or why none exists>"
```

## Step 2 — Write code evals

For every `method: code` entry, write one pytest-style function in
`evals/evaluators/<failure_mode_id>.py`:

```python
"""Code eval for <failure_mode_id>: <one-line summary of the check>."""

from evallib.schema import Trace


def check_<failure_mode_id>(trace: Trace) -> bool:
    """Returns True if the trace PASSES (i.e. this failure mode did NOT occur)."""
    ...


def test_<failure_mode_id>_examples() -> None:
    """Sanity-check the function against at least one known-failing and one
    known-passing trace from evals/traces.jsonl, referenced by query_id from
    this failure mode's member_trace_ids in taxonomy.yaml."""
    ...
```

The check function takes a `Trace` and returns a bare `bool` — this is what
later CI wiring and the harness call directly, not something that shells out
or hits an API. Write the check against the *structural* signal named in the
routing rationale (tool order, regex, schema, set membership, threshold) —
if you find yourself wanting semantic judgment inside the function body,
the routing decision was wrong; go back to Step 1 and re-route to judge
instead of writing a fuzzy code check.

Validate each function against its failure mode's `member_trace_ids` from
`taxonomy.yaml` (should return `False`/fail) and against a sample of
non-member traces (should return `True`/pass) before moving on — a code
eval that doesn't actually fire on the traces that motivated it is worse
than no eval, since it creates false confidence.

## Step 3 — Leave judge-routed modes for judge-builder-new

Do not author judge prompts here — that's `/judge-builder-new`. Just confirm
every `method: judge` entry in `routing.yaml` has a failure_mode_id that
exists in `taxonomy.yaml`, so the next skill has something to look up.

## Step 4 — Report

Report the routing split (N code / M judge), remind the target mix, list any
failure modes you flagged as off-mix, and confirm each code eval's sanity
check passed. Tell the user the next steps are `/judge-builder-new` for the
judge-routed modes.
