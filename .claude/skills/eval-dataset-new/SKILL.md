---
name: eval-dataset-new
description: Get traces into evals/traces.jsonl two ways — self-drive the agent under eval (define dimensions, sample the cross-product, generate queries, run it, no external tool needed) or import already-collected traces from Arize Phoenix, Braintrust, or a raw JSON export.
disable-model-invocation: true
argument-hint: "[n-queries]"
---

# eval-dataset-new

Phase 1 of the discovery pipeline. Requires `evals/config.yaml` and
`evals/spec.md` from `/eval-init-new` — if either is missing, stop and tell
the user to run `/eval-init-new` first.

`$ARGUMENTS` is the target number of queries to generate, for self-drive
mode only (Path A). If not provided, ask the user once Path A is chosen.

## Step 0 — Ask where traces come from, every invocation

This skill has two independent trace sources — ask which one applies this
time, every time it's invoked (a user may self-drive once and later import
a batch of production traces from Phoenix, or the reverse):

> "How should I get traces this time?
> **(a) Self-drive the agent** — I generate queries and run your agent for
> real. No external tool needed, this is the default.
> **(b) Import from an existing trace store** — you've already got traces
> in Arize Phoenix, Braintrust, or a JSON export, and want them normalized
> into `evals/traces.jsonl` instead of (or in addition to) generating new
> ones."

**(a)** → continue to Step 1. **(b)** → skip to Step 1b. Either path ends at
the shared Step 6 (normalize + write) and Step 7 (report).

---
## Path A — self-drive (no external tool required)

## Step 1 — Dimensions must exist before any query is generated

Check for `evals/dimensions.yaml`. **If it does not exist, you must not
generate a single query yet** — go to Step 2 first. If it exists, read it
back to the user and ask whether to reuse it or redo the interview.

## Step 2 — Interview for dimensions.yaml

Interview for exactly 3-4 dimensions:

1. **persona** — who is asking (e.g. new user, power user, enterprise admin).
2. **intent** — what they're trying to accomplish (grounded in the agent's
   actual tools/domain from `evals/spec.md`, not generic).
3. **complexity** — how hard the request is (e.g. single-step vs. multi-step,
   one constraint vs. several conflicting constraints).
4. **one domain-specific dimension** — something specific to this agent that
   the first three don't capture (e.g. "account tier", "urgency", "data
   sensitivity"). Ask the user what varies in their real traffic that isn't
   persona/intent/complexity.

For each dimension, get 2-4 concrete values (not open-ended text) — these
are the axes of a cross-product, so they must be a small enumerable set.
Push back if a value is really a full scenario in disguise (that belongs in
query generation, Step 4, not here).

Write `evals/dimensions.yaml`:

```yaml
dimensions:
  - name: persona
    values: [new_user, power_user, enterprise_admin]
  - name: intent
    values: [refund, troubleshoot, upgrade]
  - name: complexity
    values: [simple, multi_step]
  - name: <domain_specific_name>
    values: [...]
```

## Step 3 — Sample the cross-product

Copy `scripts/sample_tuples.py` (in this skill's directory) to
`evals/scripts/sample_tuples.py` if not already present there (the project
owns its copy from here on — later edits to the skill don't retroactively
change it). Run it:

```
python evals/scripts/sample_tuples.py --dimensions evals/dimensions.yaml \
    --n $ARGUMENTS --out evals/dimension_tuples.jsonl --seed 0
```

If `$ARGUMENTS` exceeds the full cross-product size, the script uses every
tuple once and says so — tell the user, don't silently generate fewer.

## Step 4 — Generate one realistic query per tuple

Read `evals/dimension_tuples.jsonl`. For each tuple, write one realistic,
specific user query consistent with that persona/intent/complexity/domain
combination — the kind of thing a real user in that cell would actually
type, not a paraphrase of the dimension labels. Vary phrasing and tone across
tuples that share a persona so queries don't look templated.

Keep the tuple's `dimension_tuple` values in the same order as
`dimension_names` — this list becomes `Trace.dimension_tuple` and later
skills (open coding, axial coding) rely on that order matching
`dimensions.yaml`.

## Step 5 — Run the agent (real calls — cost gate applies)

This calls the agent under eval for every generated query. Before running:
state the query count and, if the entrypoint hits a paid LLM API, ask for
explicit approval per this repo's real-API-cost-approval rule — do not just
proceed because "it should work."

Drive the agent using the entrypoint recorded in `evals/config.yaml`
(`type`/`command`/`input_format`/`output_field`). Capture, per query: every
turn (role, content, tool calls, tool results, retrieved docs if the agent
does retrieval) and the final response. If the entrypoint only exposes the
final answer (no intermediate turns), record a single user turn + single
assistant turn — don't fabricate intermediate steps.

---
## Path B — import from an existing trace store

## Step 1b — Pick the adapter and locate the export file

Ask which store the traces are coming from, and confirm the matching
adapter — do not guess from the file's shape alone, ask explicitly:

- **Braintrust** → `evallib.adapters.BraintrustAdapter`. Ask the user to
  export their experiment/log as JSON (Braintrust UI export, or
  `braintrust`'s fetch API dumped to a file) and note the path.
- **Arize Phoenix** → `evallib.adapters.PhoenixAdapter`. Ask the user to
  export spans as JSON (`phoenix.Client().get_spans_dataframe(...)` then
  `.to_json(orient="records", path_or_buf=...)`, or the UI export) and note
  the path. **Read this adapter's module docstring before running it** —
  Phoenix exports spans, not conversations, and the docstring documents the
  grouping assumptions this adapter makes; if the user's span structure
  looks materially different (different `span_kind` vocabulary, multiple
  LLM spans per logical turn), say so before importing rather than after.
- **Raw JSON export** (already trace-shaped, from a bespoke harness or
  another tool entirely) → `evallib.adapters.RawJSONAdapter`.
- **None of these fit** → point the user at
  `evallib/adapters/base.py`'s `TraceAdapter` and offer to write a new
  subclass together, following `raw_json.py`'s pattern — don't force an
  ill-fitting adapter onto a shape it wasn't built for.

Copy the export file into `evals/imports/<source>_export.<ext>` so it's a
persistent, project-owned record of what was imported and when — don't
normalize directly from wherever the user's file happens to sit.

## Step 2b — Dry-run on a small sample before importing everything

Run the chosen adapter's `iter_raw_records`/`to_trace` on just the first 2-3
records and show the reconstructed `Trace` objects to the user for a sanity
check — this costs nothing (pure parsing, no API calls) and catches a
field-name mismatch before it silently produces dozens of malformed or
empty-turn traces. Only proceed to the full import once the sample looks
right; if it doesn't, fix the adapter (or the field-lookup assumptions) and
re-sample before going further.

Note plainly: imported traces have no `dimension_tuple` unless the source
export encodes something mappable to one (rare) — `Trace.dimension_tuple`
defaults to empty for these. Later skills all handle that fine, but any
by-dimension breakdown (`evaluator-design-new`, `eval-report-new`) will be
thinner for imported traces than for self-driven ones. This is expected,
not a bug to fix here.

---
## Step 6 — Normalize and write traces (shared by both paths)

**Path A:** build one `evallib.schema.Trace` per query (`query_id` = the
tuple_id, `dimension_tuple` = the tuple's values, `turns`, `final_response`,
`metadata` = `{"generated_query": true}`). If the raw agent output doesn't
already match `Trace` shape, write or extend a `TraceAdapter` subclass in
`evallib/adapters/` rather than hand-building dicts inline — see
`evallib/adapters/raw_json.py` for the pattern.

**Path B:** run the confirmed adapter's `.normalize(import_file)` over the
full export (Step 2b already validated the shape on a sample).

Either way: append to `evals/traces.jsonl` using `evallib.jsonl.write_jsonl`
(read the existing file first and write the union back — don't overwrite
prior traces; this is what makes repeated self-drive + import calls
additive rather than destructive). Validate the result:
`python -m evallib.cli validate --model trace --file evals/traces.jsonl`.
Fix and re-run if it reports failures — do not hand this off with invalid
rows.

## Step 7 — Report

**Path A:** dimension count and values, tuples sampled vs. cross-product
size, traces written, validate result.

**Path B:** source store, import file path (under `evals/imports/`), traces
written, validate result, and a reminder that `dimension_tuple` is empty for
these unless the export mapped one.

Either way, tell the user the next step is `/open-codin-new`.
