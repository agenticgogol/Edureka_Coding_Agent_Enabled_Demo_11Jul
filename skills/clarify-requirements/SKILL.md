---
name: clarify-requirements
description: Use immediately after reading any project_brief.md or concept_brief.md, before writing design.md. Resolves ambiguity by asking the user directly instead of assuming.
---

# Clarify Requirements

The single gate between "brief exists" and "design gets written." Its job is
to make sure nothing in `design.md` rests on a guess.

## When to use

- Every time, right after reading a brief, before `technical-design`.
- Skip only if the brief has zero open questions AND every constraint is
  explicit (rare — most first-draft briefs have gaps).

## Procedure

1. Re-read the brief. First separate what it already answers explicitly
   (frameworks, providers, data flow choices stated in the brief's prose or
   `## Decisions`) from what's genuinely open — a brief drafted from a
   detailed user description often already resolves most of these; do not
   ask about anything the brief already states, even implicitly, just
   restate it as a confirmed assumption. Then list every place where:
   - a requirement is vague ("fast," "simple," "robust" with no metric)
   - a choice is implied but not stated (which frontend framework, which
     LLM provider, sync vs async, single-user vs multi-user)
   - the "Open questions" section has entries
   - constraints conflict with each other or with what generic skills in
     this repo default to (e.g. brief says "no paid APIs" but also "must
     use GPT-4" — surface the conflict, don't silently pick one)
2. Ask the user these questions in one batch, grouped and numbered. Always
   prefer concrete options with a recommended default over open-ended
   questions (e.g. "Retrieval top-k: 3 / 5 / 10? Recommend 5 for this
   corpus size unless you have a reason otherwise") — the user should be
   able to answer most items with a word or a pick, not a paragraph.
3. Do not proceed to `technical-design` until answered. If the user says
   "your call" on something, record that decision explicitly in the brief
   (append to a `## Decisions` section) so it's not re-litigated later.
4. Never silently narrow scope to avoid asking — asking is cheap, rework is
   not.
