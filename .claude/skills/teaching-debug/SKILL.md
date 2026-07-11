---
name: teaching-debug
description: Use whenever a teaching demo's code fails to run — during initial build, after adding a step, or any time during the day. Iterates on the real error until it's fixed, rather than reporting failure once and stopping.
---

# Teaching Debug

Live teaching code has to actually run. This skill is what `teaching-verify`
and `teaching-add-step` call automatically on any failure — it doesn't stop
at "here's the error," it keeps fixing until the artifact runs clean, or
until it's genuinely blocked on something only the user can resolve.

## When to use

- Any time a notebook cell, script, or step fails to execute — first
  build, after an added step, or a rerun later in the day.

## Procedure

1. **Get the real error.** Run the failing cell/step in isolation and
   capture the actual traceback/output — never guess at the cause from
   the code alone without executing it.
2. **Diagnose before editing.** Common categories, cheapest checks first:
   - Missing/wrong import or package not installed -> check
     `requirements.txt`/installed packages, install if missing.
   - API signature mismatch (function renamed, arg changed) -> if this is
     a framework covered by `research-first` (non-core: CrewAI, DSPy, MCP,
     GraphRAG, or anything unfamiliar), fetch current docs before guessing
     a fix — don't flail with trial-and-error on an API you're unsure of.
   - Missing/expired/rate-limited API key -> this is a hard stop, not a
     bug to code around. There is no mock mode. Tell the user exactly
     which key needs fixing and re-run `require-api-key` before continuing
     — do not add a fallback path to keep the demo running without one.
   - State/variable from an earlier cell not available -> check whether
     cells were run out of order, or whether an earlier step's rename/edit
     broke this one (common right after `teaching-add-step`).
   - Data file missing/malformed (e.g. the RAG step's sample PDF) -> check
     `teaching/<slug>/data/` actually has what the step expects.
3. **Fix and re-run immediately** — don't batch multiple hypothesized
   fixes before testing; change one thing, run again, observe.
4. **Repeat** until the step passes. There is no fixed retry limit — keep
   iterating on genuinely different hypotheses as long as you're learning
   something new from each attempt.
5. **When to stop and ask the user** instead of continuing to guess:
   - The fix requires a decision only the user can make (e.g. an API key
     they need to provide, or a genuine ambiguity in what the step should
     do that debugging revealed).
   - You've tried several genuinely different hypotheses and the error
     hasn't changed in a way that suggests progress — say exactly what
     you've tried, what the current error is, and what you think is
     needed to unblock it, rather than continuing to guess.
6. Once fixed, re-run the **entire artifact top to bottom** (not just the
   fixed step) to confirm the fix didn't break anything earlier that
   depended on the changed code.
