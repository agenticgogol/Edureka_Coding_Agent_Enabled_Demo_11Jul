# Eval-suite skill trigger tests

Only the 5 **model-invocable** eval skills are in scope here — the other 8
(`eval-init-new`, `eval-dataset-new`, `open-codin-new`, `axial-coding-new`,
`judge-align-new`, `eval-ci-new`, `cost-optimize-new`, `eval-loop`) all set
`disable-model-invocation: true` by design (per the P3/P4/P7 gates), so
"fires only on `/name`" is the *intended* behavior for those, not a finding.

**Methodology note:** this is a static/analytical review of each
description against Claude Code's documented matching behavior (semantic
relevance of the user's message to `description` + `when_to_use`, loaded
into every session's context), not an empirical run — empirically verifying
auto-trigger would mean spawning ~25 fresh Claude Code sessions (5 skills ×
5 queries) to observe real routing behavior, which is real API spend I
didn't have approval for and haven't run. `/name` invocation is not
analytical: it's a documented mechanical guarantee (any user-invocable
skill fires on its literal `/name`, regardless of description quality), so
that column is marked from the spec, not tested per-skill. If you want the
empirical version run for real, say so and I'll give a call-count/cost
estimate first.

## Description-length check (via a narrowed `/doctor` pass)

All 13 eval-suite skills' `description` fields are far under the
1,536-character truncation cap that determines what's actually visible to
Claude in the skill listing — largest is `retrieval-eval-new` at 283 chars,
smallest is `open-codin-new` at 146. **No description-budget truncation.**
(Full `/doctor` also does unrelated things — unused-extension cleanup,
permission-mode changes, transcript scanning across every project on the
machine — none of which this task asked for, so I ran only the
skill-listing-budget portion, read-only, and didn't touch settings.)

## eval-report-new

> Assemble evals/scorecard.md — failure taxonomy with counts, per-mode judge TPR/TNR, corrected pass rates with CIs, open backlog, and cost per query. Flags any metric backed by an unvalidated judge. Read-only. Use to check current eval status or produce a summary for stakeholders.

| # | Query | Should fire? | Assessment |
|---|---|---|---|
| 1 | "give me the current eval scorecard" | yes | "scorecard" is a literal noun in the description — strong match |
| 2 | "how are our evals looking right now" | yes | matches "Use to check current eval status" near-verbatim |
| 3 | "summarize the eval results for the team" | yes | matches "produce a summary for stakeholders" near-verbatim |
| 4 | "run the evals" | no (near-miss) | describes *executing* evals, not reporting — should route to `baseline-runner`/CI, not here |
| 5 | "fix the judge that's failing calibration" | no (near-miss) | describes *changing* a judge, not reading state — should route to `judge-align-new` |
| `/eval-report-new` | — | yes (mechanical) | user-invocable, no restriction — always fires |

**Verdict: description is solid.** Literal phrases a user would type
("scorecard", "eval status", "summary for stakeholders") are already
present verbatim. No rewrite needed.

## evaluator-design-new

> For each failure mode in evals/backlog.md, decide whether it gets a code-based eval or an LLM judge, write the code evals, and record every routing decision with a one-line rationale. Use after axial coding produces a taxonomy and backlog.

| # | Query | Should fire? | Assessment |
|---|---|---|---|
| 1 | "should this be a code check or a judge?" | yes | "code-based eval or an LLM judge" is close in wording and concept |
| 2 | "route the backlog to evaluators" | yes | "backlog" + "evaluators" both appear |
| 3 | "write code evals for these failure modes" | yes | "write the code evals" appears near-verbatim |
| 4 | "write a judge prompt for tone-mismatch" | no (near-miss) | *authoring* a judge, not *routing* — should hit `judge-builder-new` |
| 5 | "build the golden dataset" | no (near-miss) | unrelated concept (CI golden set), should not match |

**Verdict: adequate, one gap.** Query 1's phrasing ("code check" instead of
"code-based eval") is a slightly looser match than the others — the
description never uses the word "check." Minor risk, not a rewrite-worthy
problem on its own, but worth strengthening opportunistically:

**Revised description** (adds the literal phrase a user is likely to type):
> Decide whether each failure mode in evals/backlog.md should be checked with code (a script/assertion) or an LLM judge, write the code checks, and record every routing decision with a one-line rationale. Use after axial coding produces a taxonomy and backlog, or when asking "should this be a code check or a judge?"

## judge-builder-new

> Author one LLM judge per failure mode routed to "judge" in evals/evaluators/routing.yaml, using assets/judge_template.md. Enforces binary output, critique-before-label, train-only few-shot, and spec.md-grounded definitions. Use after evaluator-design-new routes a failure mode to judge.

| # | Query | Should fire? | Assessment |
|---|---|---|---|
| 1 | "write a judge prompt for tone-mismatch" | yes | "Author one LLM judge" + "failure mode" both map closely |
| 2 | "build me a judge for the skipped-eligibility-check failure" | yes | same match strength as #1 |
| 3 | "author an LLM judge for this category" | yes | "Author one LLM judge" is near-verbatim |
| 4 | "calibrate the judge against the test set" | no (near-miss) | *calibration*, not *authoring* — should hit `judge-align-new` |
| 5 | "score these traces with the judge" | no (near-miss) | *running*, not authoring — should hit `judge-runner`/`judge-align-new` |

**Verdict: solid**, though the description never says the word "write" or
"prompt" — it says "Author." A user typing "write a judge prompt" relies on
semantic closeness between "author" and "write," which large models handle
fine, but it's the one skill here without a fully literal match on the verb.

**Revised description** (adds "write"/"prompt" literally, keeps everything else):
> Write (author) one LLM judge prompt per failure mode routed to "judge" in evals/evaluators/routing.yaml, using assets/judge_template.md. Enforces binary output, critique-before-label, train-only few-shot, and spec.md-grounded definitions. Use after evaluator-design-new routes a failure mode to judge, or when asked to "write a judge" or "build a judge prompt" for a specific failure mode.

## retrieval-eval-new

> Evaluate retrieval quality separately from end-to-end generation quality — adversarial retrieval set (near-miss distractors, multi-hop, negation, entity confusion) scored with Recall@k/MRR/NDCG. Use when working on retriever/RAG source files or when retrieval quality is in question.
> `paths: "**/retriev*/**, **/*retriev*.py, **/rag/**, **/*rag*.py, **/vector_store/**, **/embeddings/**"`

| # | Query | Should fire? | Assessment |
|---|---|---|---|
| 1 | "check if the retriever is finding the right docs" | yes | "retrieval quality" + "retriever" both present |
| 2 | "evaluate our RAG pipeline's recall" | yes | "RAG" + "Recall@k" both present |
| 3 | "is the retriever confused by similar-sounding products" | yes | maps to "entity confusion" adversarial category |
| 4 | "make the agent's responses cheaper" | no (near-miss) | should route to `cost-optimize-new` |
| 5 | "did the agent call the right tool" | no (near-miss) | should route to `trajectory-eval-new` |

**Verdict: strong**, and this skill has a second, independent trigger path
(`paths` frontmatter) — editing any file under `retrieval.py`/`rag/`/
`vector_store/`/`embeddings/` auto-activates it regardless of what the user
typed. No rewrite needed.

## trajectory-eval-new

> Evaluate tool selection, tool-argument validity, and execution success as separate code-based checks, and attribute failed traces to the earliest diverging step rather than the final answer. Use when trajectory/tool-use quality is in question, not just final-answer correctness.

| # | Query | Should fire? | Assessment |
|---|---|---|---|
| 1 | "did the agent call the right tools in the right order" | yes | "tool selection" maps directly |
| 2 | "check if the tool arguments were valid" | yes | "tool-argument validity" is near-verbatim |
| 3 | "where did this trace first go wrong" | yes | maps to "attribute failed traces to the earliest diverging step" |
| 4 | "is the final answer correct" | no (near-miss) | description explicitly excludes this ("not just final-answer correctness") — should NOT fire alone |
| 5 | "check retrieval quality" | no (near-miss) | should route to `retrieval-eval-new` |

**Verdict: solid.** Query 4 is a deliberately adversarial near-miss (the
skill's own description disclaims exactly this framing), and the wording
makes that disclaim explicit enough that a false-positive fire here would
be a real signal of a matching problem — worth re-checking if this skill
ever gets renamed/reworded.

## Summary

No skill in this set only fires on `/name` — all 5 have descriptions with
literal, user-typeable phrases covering their positive cases and clear
conceptual separation from their near-misses. Two got minor description
rewrites (`evaluator-design-new`, `judge-builder-new`) to close small
verb-choice gaps rather than a structural problem. Apply those two rewrites
below if you want them; the other three are unchanged.
