---
name: retrieval-eval-new
description: Evaluate retrieval quality separately from end-to-end generation quality — adversarial retrieval set (near-miss distractors, multi-hop, negation, entity confusion) scored with Recall@k/MRR/NDCG. Use when working on retriever/RAG source files or when retrieval quality is in question.
paths: "**/retriev*/**, **/*retriev*.py, **/rag/**, **/*rag*.py, **/vector_store/**, **/embeddings/**"
---

# retrieval-eval-new

Evaluates the retriever in isolation from the generator. A trace can have a
perfect final response despite bad retrieval (the generator compensated) or
a bad final response despite perfect retrieval (the generator ignored good
context) — conflating the two hides which component to fix. This skill only
ever scores `Trace.turns[*].retrieved_docs` against ground truth; it never
scores `final_response`.

## Step 1 — Confirm the retriever is in scope

This skill activates automatically when you're working on retrieval/RAG
source files (see this file's `paths` frontmatter). If invoked manually,
confirm the agent under eval actually has a retrieval step — `Trace.turns`
should contain `retrieved_docs` on at least some traces in
`evals/traces.jsonl`. If none do, say so and stop; there's nothing to
evaluate here.

## Step 2 — Generate the adversarial retrieval set

Read [references/adversarial_retrieval.md](references/adversarial_retrieval.md)
for the four required category types (near-miss distractors, multi-hop,
negation, entity confusion) before generating anything. Produce at least
3-5 examples per category, grounded in the actual corpus the retriever
indexes (read a sample of the corpus/doc store first — don't invent doc_ids
that don't exist). For each example, record: query, category, and the
ground-truth relevant doc_id(s) (with graded relevance 0-3 if the corpus
supports grading finer than binary relevant/not).

Write `evals/retrieval/adversarial_set.jsonl`: one JSON object per line —
`{"query": ..., "category": ..., "relevant_docs": {"doc_id": relevance, ...}}`.

## Step 3 — Run retrieval and score

Run the retriever (not the full agent) against every query in the
adversarial set, plus a sample of ordinary queries from
`evals/dimension_tuples.jsonl` / `evals/traces.jsonl` for a non-adversarial
baseline. Capture the ranked `doc_id` list returned for each.

Score with `scripts/ir_metrics.py` (`recall_at_k`, `mrr`, `ndcg_at_k` — do
not reimplement these inline, import from the script). Pick `k` values that
match how many docs the generator actually consumes (e.g. if the agent uses
top-5 context, report Recall@5 and NDCG@5, not an arbitrary k).

Report metrics broken out **by category** (near-miss / multi-hop / negation
/ entity-confusion / ordinary-baseline) — an aggregate score hides which
adversarial category is actually weak, and each category points at a
different fix (near-miss failures suggest a re-ranking gap, multi-hop
failures suggest a chunking/retrieval-count gap, negation failures suggest
an embedding-model limitation, entity-confusion failures suggest a metadata
filtering gap).

## Step 4 — Write results

Write `evals/retrieval/results.json`: per-category and overall Recall@k,
MRR, NDCG@k, plus the worst-scoring individual examples per category (so the
user can inspect exactly which doc got buried or missed).

## Step 5 — Report

Summarize scores by category, call out the weakest category plainly, and
suggest which layer it points to (re-ranking, chunking, embedding model,
metadata filtering) per the mapping above — but don't prescribe a fix beyond
that; this skill measures, it doesn't rebuild the retriever.

## Step 6 — Agentic-retrieval-specific checks (only if the retriever is agentic)

If the agent under eval was built with `agent-agentic-rag` (check its
`design.md`/`teaching_brief.md` for which capabilities were wired — see
that skill's capability list), the retrieval trace has more decision points
than a fixed pipeline, and each wired capability gets its own check on top
of Steps 2-4's Recall/MRR/NDCG (which still apply to whichever retrieval
round actually fed the generator):

- **Retry/self-grading (always wired if agentic):** for each trace with
  more than one retrieval round, confirm the grade that triggered the retry
  was actually correct (i.e. the first round's docs really were
  insufficient, not a false-negative grade wasting a round) — report grade
  precision/recall against your own read of the retrieved docs, not just
  "did it retry."
- **Multi-tool routing (if wired):** report routing accuracy — did the
  agent pick the tool/source that actually contained the answer, per query
  category, not just whether *a* retrieval happened.
- **Multi-hop planning (if wired):** for multi-hop adversarial examples
  (Step 2's category), report whether the sub-questions the planner
  generated actually decompose the query correctly, separate from whether
  the final retrieval succeeded — a good final answer can hide a bad plan
  that got lucky.
- **Reranking (if wired):** compare Recall/NDCG@k before vs. after the
  rerank step on the same retrieval round, so a reranker that isn't
  actually improving ordering is visible rather than assumed to help.
- **Groundedness verification (if wired):** this checks `final_response`
  against `retrieved_docs`, which is normally out of this skill's scope
  (Step 0's boundary) — hand this one to `eval-and-observability`'s
  faithfulness/groundedness metric instead of scoring it here; just confirm
  in this report whether it's wired, since a missing groundedness check on
  a design that claims one is itself a finding.
- **Abstention (if wired):** report abstention precision/recall separately
  — false abstentions (evidence was actually sufficient but the agent
  declined) and missed abstentions (evidence was insufficient but the agent
  answered anyway) are different failure modes and point at different
  fixes (grading threshold vs. abstention threshold).

Skip this step entirely, and say so, if the retriever isn't agentic — don't
manufacture these checks for a plain fixed-pipeline RAG retriever.
