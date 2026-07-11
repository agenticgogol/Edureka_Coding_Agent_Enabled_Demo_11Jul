---
name: teaching-brief
description: Use to start a lightweight teaching demo — a progressive sequence of small steps (e.g. "a) basic API call, b) add system prompt, c) add tool calling, d) add memory, e) basic RAG"), as notebook or small project. Drafts teaching/<slug>/teaching_brief.md.
---

# Teaching Brief

For live-teaching or classroom demos, not certification-grade course
content. If you want a polished, fully-contracted atomic concept notebook
for the course itself, use `write-concept-brief` under `concepts/`
instead — this skill is for quick, progressive, instructor-driven demos.

## When to use

- The user wants to demonstrate a *sequence* of related concepts that
  build on each other in one sitting (each step adds to the previous
  code), rather than one isolated atomic concept.
- Output can be a single progressive notebook, or a small incrementally-
  growing script/project — the brief should capture which.

## Procedure

1. Ask:
   - What's the ordered list of steps/features to demonstrate? (e.g. "a)
     basic OpenAI API call, b) add system prompt, c) add tool calling,
     d) add session memory, e) basic RAG over a PDF")
   - Notebook or small script/project? (notebook is default and usually
     right for teaching — cells make the progression visible step by step)
   - Which provider (OpenAI/Anthropic/Groq)? A real, working key for it is
     required before anything gets built — there is no mock mode, so
     confirm the user has (or will add) a key before proceeding.
   - Audience level (affects how much explanation prose goes between
     steps).
2. **Paraphrase back before drafting the file — mandatory.** Restate the
   ordered steps in plain language as you understood them and ask "did I
   get that right, and is the order/scope correct?" Do this even if the
   request seemed clear — it's the cheapest point to catch a
   misunderstanding, and this lightweight track has no later test-review
   checkpoint to catch it instead.
3. Create `teaching/<slug>/teaching_brief.md` — treat this as a **living
   log**, not a one-time spec, since the demo will likely grow throughout
   the day via `teaching-add-step`:

```markdown
# Teaching Brief: <Name>

## Steps (in order, each builds on the previous)
a) <step> — added <date/session>
b) <step> — added <date/session>
c) <step> — added <date/session>
...

## Format
notebook | script | small project

## Constraints
<library/provider requirements — which provider key is required>

## Audience level
<beginner / intermediate / advanced>
```

4. Show the brief to the user for final approval, then run
   `require-api-key` — a real, verified provider key is mandatory before
   `teaching-build` runs. No mock mode exists in this repo; if no key is
   set or it fails verification, stop and tell the user exactly what to
   set, and do not build anything until it passes. Later additions during
   the day go through `teaching-add-step` (which does not need to re-run
   `require-api-key` unless the key has changed or stopped working).
