---
name: eval-and-observability
description: Use for any project/concept whose brief involves RAG, agent quality, or production-readiness claims. Wires lightweight tracing (Phoenix, local fallback) and an eval pass (Ragas or a scripted judge) so quality claims are measured, not asserted.
---

# Eval and Observability

"It works" for an agentic system means nothing without a trace and a
measured eval. This skill exists so demos don't just show a happy-path
answer — they show *why* it's trustworthy.

## When to use

- Any RAG project (naive/advanced/agentic) — must show retrieval + eval
  metrics, not just a final answer.
- Any agent project where the brief claims reliability, safety, or quality
  ("accurately answers," "safely handles") — that claim needs a measured
  eval, not just a demo run.
- Skip only for the simplest single-turn concept demos with no retrieval or
  quality claim — note the skip in `plan.md`.

## Procedure

1. **Tracing**: wire basic tracing via Phoenix if `PHOENIX_COLLECTOR_ENDPOINT`
   is set in env (Phoenix Cloud); otherwise fall back to local
   OSS Phoenix, and if neither is available, fall back further to
   structured JSON logs of each LLM/tool/retrieval span (input, output,
   latency, token count) via `helper-utils`' logger — never skip
   observability entirely just because no cloud key is set.
2. **Trace anatomy**: make sure each span is labeled by type (`llm`,
   `retrieval`, `tool`) so a reader can see the anatomy of a request, not
   just a single flat log line — this addresses a specifically-flagged gap
   (trace anatomy is invisible in most demos).
3. **Eval set**: write a small eval set (5-15 cases) of realistic
   input/expected-behavior pairs derived from `project_brief.md`'s
   "Definition of Done" — reuse cases from the `write-and-validate-tests`
   skill if that step already ran; don't duplicate test authorship.
4. **Eval run**: for RAG, run Ragas (faithfulness, answer relevancy, context
   precision/recall) if the dependency is available; otherwise fall back to
   a scripted LLM-judge or exact/fuzzy-match check against expected
   behavior — must run with no paid API key too (use a rule-based judge as
   the no-key fallback).
5. Record results in `## Eval Results` in the project README — actual
   numbers/pass-fail, not a narrative claim of quality.
6. This skill does not replace `run-and-verify` (one live end-to-end check)
   or `write-and-validate-tests` (correctness tests) — it adds a quality/
   trust measurement layer on top.
