# teaching/

Lightweight, progressive teaching demos — for live classroom use, not
certification-grade course content. If you want a polished, fully-
contracted atomic concept notebook for the actual course, use
`concepts/` instead (see its own README).

## What belongs here

A sequence of small steps that build on each other in one artifact, e.g.:

```
a) basic OpenAI API call in Python
b) add a system prompt
c) add tool-calling support
d) add session memory
e) basic naive RAG reading a PDF and answering questions
```

Each step is shown as an addition to the previous one's code — a student
sees the concept accumulate live, not five disconnected examples.

## How to use

```
/new-teaching-demo <slug>          # create the folder only
/run-teaching-pipeline <slug>      # description, checkpoints, build + verify (auto-debugs failures)
/add-teaching-step <slug> [desc]   # keep extending it later — desc may be inline or asked next
/status-project ...                # (use the projects/concepts one; teaching has no separate status command yet)
```

This is a deliberately short pipeline — no formal
security/eval/lint/env/integrate/deploy gates by default. Ask for any of
those explicitly for a specific demo if you need them (e.g. "add a
security-check pass because step (e) queries a database"). It still keeps
real gates before code generation: open-ended description, clarification
for genuine gaps, format choice (notebook/script or Streamlit+FastAPI),
one user-flow happy-path test case, `.env`/API-key verification,
Phoenix/no-Phoenix choice, vector-store choice, and final ready-to-generate
approval. It also keeps three things every other lightweight shortcut
would normally drop:

- **No mock mode.** `require-api-key` runs before anything is built or
  added — a real, working provider key is mandatory, verified with an
  actual call, not just checked for presence. If the key ever stops
  working mid-day, that's a hard stop, not something the demo silently
  works around.
- **Clarify + paraphrase, every time** (`teaching-brief` for the initial
  demo, `teaching-add-step` for every later addition) — before any file is
  touched, the agent restates what it understood and waits for
  confirmation. This is the one requirements checkpoint this track keeps,
  because there's no later test-review step to catch a misunderstanding
  instead.
- **Automatic debugging on failure** (`teaching-debug`, invoked by
  `teaching-verify`) — if a step doesn't run, the agent iterates on the
  real error until it's fixed, rather than reporting the failure once and
  stopping.

## Growing a demo across the day

This track is built for exactly that: `/new-teaching-demo` once, then
`/add-teaching-step <slug> [<feature description>]` as many times as you
want (before class, live during class, after class to extend for
tomorrow). You can pass the feature inline, or omit it and the agent will
ask for it first. Each call loads the existing notebook/script or
Streamlit+FastAPI app and its full step log, clarifies and paraphrases
the new addition back to you, appends cells/code or backend routes plus UI
without disturbing earlier already-verified steps, and re-verifies old
and new functionality together (a new step can break an earlier one —
this is caught, not assumed away).

## Layout

```text
teaching/<slug>/
  teaching_brief.md   # ordered steps, format, decisions, checkpoint status
  notebook.ipynb       # or app.py / backend/ + Streamlit app — progressive artifact
  data/                 # small synthetic/sample files if a step needs them
  README.md             # how to run, which provider/model was verified
```

One demo at a time, same discipline as `projects/`/`concepts/`.
