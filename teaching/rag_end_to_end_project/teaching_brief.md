# Teaching Brief: Full End-to-End RAG Project

## Description (as given by user)
A full-scale, end-to-end RAG project runnable locally, with a Streamlit
chat frontend (Claude/ChatGPT-style chat window). Users can upload/ingest
documents via a "+" button in the chat window; ingested content is stored
in Qdrant Cloud. Users ask questions and get retrieved/generated answers.
A sidebar lets users configure the RAG pipeline per-query:

- Chunking: default recursive; options — character text splitter, token
  text splitter, semantic chunker
- Embedding: default OpenAI small; options — Cohere, BGE-large (open
  source, local), MiniLM (open source, local)
- Vector DB: default Qdrant Cloud (only option for now)
- Search mechanism: default hybrid search; options — semantic-only,
  metadata filtering, others as useful
- Retrieval k: default 20; options — 3, 5, 10, 50
- Reranking: default cross-encoder reranker; option — no reranking
- Prompt template: default template; option — custom text entry

Session/conversation history must persist within a session. Observability
via Phoenix Cloud, default ON, toggleable off from the UI. RAG eval
metrics (faithfulness, answer relevancy, context precision/recall, etc.)
computed and shown per-answer. Chat window shows interim pipeline
progress as it happens (ingesting → query embedded → vector search →
chunks retrieved → reranking → final answer).

Eventually deployable — originally asked about Vercel; resolved during
clarification (see Decisions) to Render-only hosting since Streamlit/
FastAPI cannot run on Vercel's serverless model.

## Steps (in order, each builds on the previous)
a) Streamlit chat UI shell with "+" upload control — optional, flexible:
   zero-to-many files (any mix of PDF/text/other supported types) and/or
   a URL field, single-type or mixed-type, in one ingestion action — plus
   persistent session chat history
b) Document ingestion pipeline: configurable chunking → configurable
   embedding → upsert into Qdrant Cloud
c) Query pipeline: query embedding → configurable search (hybrid/
   semantic/metadata-filtered) → configurable k → configurable reranking
   → prompt construction (default or custom template) → LLM answer
d) Streaming interim-step progress display in the chat window during
   query handling
e) Phoenix observability wiring (toggleable from sidebar)
f) Per-answer RAG eval metrics panel in the sidebar
g) Conversational context resolution: follow-up questions are rewritten/
   answered using prior chat history (e.g. condense-question step before
   retrieval), not treated as standalone queries
h) Sidebar pipeline controls are live-editable by the user at any time
   (before or between questions), not fixed at session start
i) Cost tracking and display: per-ingestion cost (embedding tokens),
   per-answer cost (retrieval/embedding + generation tokens), and a
   running session-total, shown in the sidebar and/or after each
   ingestion/answer
j) Inline citations — the default prompt instructs the model to cite
   retrieved-chunk numbers ([1], [2], ...) inline in its answer; the
   backend maps cited markers back to source/chunk/snippet and returns
   them as a `citations` field; the frontend shows a "Sources" expander
   under each answer — added 2026-07-18
k) Clear entire vector database (all sessions) — destructive, confirm-
   gated sidebar control + POST /admin/clear_all, distinct from the
   existing per-session Reset — added 2026-07-18
l) Retrieved + reranked chunks shown live in the UI during query
   streaming (vector-search order vs. cross-encoder order, with scores)
   — added 2026-07-18
m) Full per-question cost breakdown (query embedding / condense /
   generation, tokens + USD each) shown in an expander under each answer
   — added 2026-07-18
n) Fixed: citation snippets were rendering cut off because chunk text's
   embedded newlines broke markdown bullet rendering — now whitespace-
   collapsed before display — fixed 2026-07-18
o) Fixed: st.status() is itself expander-like, so nesting a real
   st.expander (retrieved/reranked chunks) inside it raised
   StreamlitAPIException — replaced with plain labeled sections inside
   the live status block — fixed 2026-07-18
p) Retrieved/reranked chunks, citations, and per-answer cost now persist
   across reruns — stored as structured "extras" on each chat message and
   re-rendered (as real expanders, safe outside st.status) on every
   history replay, not just visible transiently right after the answer
   — added 2026-07-18
q) Sidebar cost breakdown — running session total now split into
   cumulative ingestion cost vs. cumulative Q&A cost (both were already
   included in the backend's session total; this just exposes the split)
   — added 2026-07-18
r) Sidebar observability status — calls GET /observability/status and
   honestly shows whether Phoenix is actually connected (phoenix-remote/
   phoenix-local/stdout-json fallback), with a dashboard link when
   connected — added 2026-07-18.
s) Phoenix Cloud actually wired up — 2026-07-18. User added
   PHOENIX_API_KEY + PHOENIX_COLLECTOR_ENDPOINT to .env. Resolved the
   earlier dependency conflict by installing arize-phoenix-otel (the
   lightweight OTEL client) instead of the full arize-phoenix package
   (which bundles a local server + evals + forces a major fastapi/
   pydantic/starlette upgrade that breaks this project's pins).
   config.py now reads PHOENIX_API_KEY; observability.py passes it to
   register() and appends the required /v1/traces suffix to the
   collector endpoint (a bare Phoenix Cloud space URL 405s without it —
   found via real testing, not assumed). Bumped openai pin to 1.69.0
   (openinference-instrumentation-openai's minimum). Verified end-to-end:
   backend reports mode="phoenix-remote", and a real ingest + query
   produced zero span-export errors in the backend log (previously: 405
   Method Not Allowed on every batch, before the /v1/traces fix).

## Format
full_app (Streamlit frontend + FastAPI backend)

## Happy-path test case (user-approved)

User opens the Streamlit app locally. The sidebar shows the current
pipeline settings (recursive chunking, OpenAI small embeddings, Qdrant
Cloud, hybrid search, k=20, cross-encoder reranking, default prompt
template, Phoenix ON) with controls to change any of them before or
between questions. The user clicks "+" and uploads one PDF file (a single
document of a single type — upload is flexible: zero-to-many files of
any mix of supported types, or a URL instead of/alongside files, all
optional per ingestion action); the chat window shows an ingestion status
step for the source as it completes and lands in Qdrant, followed by a
cost readout for that ingestion (e.g. embedding tokens used and
estimated $ cost). The user asks a question whose answer is contained in
the ingested content, hits send, and watches the chat window show interim
pipeline steps in order — embedding query, searching Qdrant, chunks
retrieved, reranking, generating answer — followed by a correct, streamed
answer and a per-answer cost breakdown (retrieval/embedding cost +
generation token cost) shown alongside the eval-metrics panel in the
sidebar. A running session-total cost is also visible in the sidebar. The
user then asks a follow-up question that only makes sense with context
from the previous turn (e.g. "what did you just say about X?" or
"summarize what I asked before") — the chatbot correctly resolves it
using conversation history, not just the new message in isolation. Both
Q&A turns remain visible in the chat. At any point the user can revisit
the sidebar and change pipeline settings (chunking, embedding, search
mechanism, k, reranking, prompt template) for subsequent ingestions and
questions.

## Observability
phoenix (default ON, toggleable off from sidebar)

## Vector store
qdrant

## Constraints
- LLM provider: OpenAI (OPENAI_API_KEY required in .env, real key verified
  via require-api-key before any build)
- Vector store: Qdrant Cloud (QDRANT_URL, QDRANT_API_KEY required in .env)
- Optional: COHERE_API_KEY if Cohere embedding option is exercised
- Open-source local embedding options (BGE-large, MiniLM) included via
  sentence-transformers — real model downloads on first use, cached
  locally, CPU inference
- Reranker: cross-encoder based, local (sentence-transformers
  CrossEncoder), no additional paid API required
- All provider/vector-store keys live server-side only (FastAPI backend
  env), never exposed in the Streamlit UI — sidebar only exposes
  non-secret pipeline choices
- Target hosting: Render only (single or split services) — Vercel is not
  viable for a Streamlit/FastAPI stack

## Audience level
intermediate

## Decisions
- Vercel hosting is not possible for Streamlit/Gradio + FastAPI (Vercel
  only supports static/serverless, not long-running servers). User chose
  Render-only hosting for both frontend and backend. Alternatives
  discussed: Railway, Fly.io, Hugging Face Spaces — Render confirmed as
  simplest for this stack.
- API keys (OpenAI, Qdrant) must live server-side (.env locally, Render
  env vars in production) — never in the Streamlit UI.
- RAG eval metrics shown as a sidebar panel per answer (not inline in
  chat), computed live via a lightweight judge (Ragas or scripted
  fallback).
- Local open-source embedding options (BGE-large, MiniLM) are included
  despite download/CPU cost, per user preference.
- Reranker default: cross-encoder (sentence-transformers CrossEncoder,
  local, no paid API).
- Ingestion is flexible per action: zero-to-many files (any mix of PDF/
  text/doc types) and/or a URL, single type or mixed, each shown as its
  own ingestion status step.
- Cost visibility: token usage and estimated $ cost is computed and shown
  for every embedding call (ingestion) and every generation call
  (answering), plus a running session-total, surfaced in the sidebar.
- Conversation history is used to resolve follow-up questions (context-
  dependent references like "what did you just say") via a condense-
  question rewrite step before retrieval, not just appended as raw
  context.
- Sidebar pipeline settings (chunking/embedding/search/k/reranking/
  prompt template/observability) are editable by the user at any point
  in the session, applying to subsequent questions.

## Checkpoint status
- Description: approved
- Clarifications: approved
- Format: approved
- Happy-path test case: approved
- API key verification: verified (OPENAI_API_KEY via gpt-4o-mini real call; QDRANT_URL/QDRANT_API_KEY via get_collections)
- Observability: approved
- Vector store: approved
- Ready to generate: approved
- Build: complete
- Verify: complete (backend end-to-end verified via real OpenAI + Qdrant
  Cloud calls, including a follow-up context-resolution question; frontend
  verified as a wired, serving process against the same tested contract —
  see README.md for full detail and known deviations)
