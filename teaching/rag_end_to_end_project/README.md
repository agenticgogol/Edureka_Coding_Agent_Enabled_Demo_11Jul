# Full End-to-End RAG Project

A teaching demo of a full, configurable RAG pipeline: Streamlit chat frontend
+ FastAPI backend + Qdrant Cloud vector store, with live interim-step
streaming, per-answer eval metrics, cost tracking, conversational memory,
and toggleable Phoenix observability.

See `teaching_brief.md` for the full requirements and decisions history.

## Run it

```bash
cd teaching/rag_end_to_end_project
python3.11 -m venv .venv        # use 3.11 or 3.12 — tiktoken/pydantic-core
                                  # have no prebuilt wheels for 3.14 yet
.venv/bin/pip install -r requirements.txt
```

Make sure the repo-root `.env` (or a project-level `.env` here) has:

```
OPENAI_API_KEY=...
QDRANT_URL=...
QDRANT_API_KEY=...
# optional:
COHERE_API_KEY=...
PHOENIX_COLLECTOR_ENDPOINT=...
```

### Option A — one command (Makefile)

```bash
make install   # creates .venv, installs requirements.txt
make run       # starts backend, waits for /health, then starts frontend
make stop      # kills anything left on ports 8000/8501 (if Ctrl-C didn't clean up)
```

`make run` runs both processes in one terminal and stops both on Ctrl-C.
Individual targets are also available: `make run-backend`, `make
run-frontend`, `make clean` (removes `.venv` and `__pycache__`).

### Option B — two terminals

Terminal 1 — backend:
```bash
.venv/bin/uvicorn backend.main:app --reload --port 8000
```

Terminal 2 — frontend:
```bash
.venv/bin/streamlit run frontend/app.py
```

Open the Streamlit URL it prints (default `http://localhost:8501`).

## What's verified

Verified 2026-07-18 against the **real** OpenAI (`gpt-4o-mini` chat +
`text-embedding-3-small` embeddings) and **real** Qdrant Cloud, driven
directly via HTTP (not the UI) for the backend, plus a live Streamlit
process confirmed serving and wired to the same verified endpoints:

- `POST /ingest` — ingested a synthetic test document, got back real chunk
  count + real embedding token cost.
- `POST /query/stream` — real NDJSON streaming, correct answer grounded in
  the ingested document, real per-answer eval scores (faithfulness /
  answer_relevancy / context_precision, scripted LLM-judge via
  `gpt-4o-mini`), real cost breakdown.
- Conversational memory — a follow-up ("What did you just say the budget
  was for?") was correctly resolved via the condense-question step using
  prior session history, without repeating the entity in the new message.
- `GET /session/{id}/cost` and `POST /reset/{id}` — both confirmed working.
- Streamlit frontend started successfully and its `/ingest` and
  `/query/stream` calls match the backend's actual field names exactly
  (verified by reading `frontend/app.py` against the live-tested contract
  above — this was not click-through browser tested in this environment).

## Step j — inline citations (added 2026-07-18)

The default prompt template now instructs the model to cite retrieved
chunks inline as `[1]`, `[2]`, etc., right after the claim they support.
`/query` and `/query/stream`'s `final` payload now include a `citations`
field: a list of `{marker, source, chunk_index, snippet}` built from
whichever markers the model actually used (a chunk retrieved but not
cited is not included). The Streamlit frontend renders these in a
"Sources" expander under each answer, and persists them into the replayed
chat history. Custom prompt templates do **not** get citation behavior
automatically — only the default template includes the citation
instruction.

Re-verified 2026-07-18 against real OpenAI + Qdrant Cloud: a multi-fact
question correctly produced `[1][2]` markers mapped to the right two
chunks; the existing conversational-context follow-up and reset endpoints
were re-tested alongside this change and still work correctly.

## Steps k-n (added 2026-07-18)

- **Clear entire vector database** — sidebar control (checkbox-confirmed,
  destructive) calling `POST /admin/clear_all`, wipes every point in every
  `rag_demo_*` collection across all sessions. Distinct from `Reset
  session`, which only clears the current session's data — useful because
  Streamlit keeps the same `session_id` across page reloads (only a fresh
  browser tab or clicking Reset gets a new one), so repeated manual
  testing without resetting can leave stale documents behind.
- **Retrieved/reranked chunks in the UI** — `/query/stream` now emits
  `retrieved_chunks` (vector-search order) and `reranked_chunks`
  (cross-encoder order, if reranking is on) events with full chunk
  content + scores; the frontend renders both as expanders inside the
  live pipeline status block.
- **Full cost breakdown** — each answer now shows an expander with a
  per-stage table (query embedding / condense / generation — tokens and
  USD each) instead of just a one-line total.
- **Citation snippet fix** — snippets are now whitespace-collapsed before
  display; previously embedded newlines in chunk text broke Streamlit's
  markdown bullet rendering, making citations look cut off.

Re-verified 2026-07-18 against real OpenAI + Qdrant Cloud: confirmed
`retrieved_chunks`/`reranked_chunks` stream events carry real chunk data,
citations render as clean single-line snippets, the cost table's four
values are all populated from a real query, and `/admin/clear_all`
genuinely empties the vector store (a post-clear query against the same
session returned zero chunks and "I don't have enough information").

**Bug fixed 2026-07-18**: `st.status(...)` (used for the live pipeline
progress display) is itself an expander-like container, and Streamlit
raises `StreamlitAPIException: Expanders may not be nested inside other
expanders` if a real `st.expander` is opened inside it — which the
retrieved/reranked-chunks display from steps k-n did. Fixed by rendering
those as plain labeled sections instead of nested expanders. Re-verified
via `streamlit.testing.v1.AppTest` driving the actual `app.py` against
the real running backend (ingest → ask a question) — confirmed no
exception is raised where the reported crash occurred, and the answer,
citations, and cost table all render correctly.

## How to inspect what's stored in the vector database

Go to `cloud.qdrant.io` → your cluster → **Collections**. This demo
creates one collection per embedding model actually used
(`rag_demo_openai-small`, `rag_demo_cohere`, `rag_demo_bge-large`,
`rag_demo_minilm`). Open a collection → **Points** to browse individual
stored chunks and their full payload (`text`, `source`, `chunk_index`,
`session_id`) — useful for a live "here's literally what got embedded and
stored" moment when teaching this module.

## Steps o-r (added 2026-07-18)

- **Fixed**: `st.status()` is itself expander-like; nesting a real
  `st.expander` inside it (the retrieved/reranked chunk display) raised
  `StreamlitAPIException`. Replaced with plain labeled sections.
- **Persisted interim output**: retrieved chunks, reranked chunks,
  citations, and per-answer cost are now stored as structured "extras" on
  each chat message and re-rendered on every history replay — they no
  longer disappear once you ask a follow-up question.
- **Cost breakdown**: sidebar now shows cumulative ingestion cost vs.
  cumulative Q&A cost separately (both were always included in the
  backend's running session total — this just exposes the split).
- **Observability status**: sidebar calls `GET /observability/status` and
  shows the real connection state — **Phoenix Cloud is currently NOT
  connected** (no `PHOENIX_COLLECTOR_ENDPOINT` set; `arize-phoenix` isn't
  installed due to the dependency conflict noted below). The demo runs on
  the JSON-stdout tracing fallback until that's wired up.

Re-verified 2026-07-18 via `streamlit.testing.v1.AppTest` driving the
real app against the real backend: asked two questions in one session and
confirmed both answers' retrieved/reranked-chunk expanders, sources, and
cost breakdowns were simultaneously present (proving persistence across
reruns) — no exceptions raised.

## Phoenix Cloud — now actually connected (2026-07-18)

With `PHOENIX_API_KEY` and `PHOENIX_COLLECTOR_ENDPOINT` set in `.env`,
observability now really connects to Phoenix Cloud instead of falling
back to stdout JSON spans. Two real bugs were found and fixed while
wiring this up (both via live testing against the real Phoenix Cloud
endpoint, not assumed from docs):

1. Installing the full `arize-phoenix` package forces a major
   `fastapi`/`pydantic`/`starlette` upgrade that conflicts with this
   project's pins. Fixed by installing `arize-phoenix-otel` instead — the
   lightweight OTEL client, which is all that's needed to *send* traces
   to a remote collector (no local Phoenix server/evals bundle required).
2. A bare Phoenix Cloud space URL (`https://app.phoenix.arize.com/s/<space>`)
   returns `405 Method Not Allowed` for HTTP/protobuf span export — it
   needs the `/v1/traces` suffix. `observability.py` now appends this
   automatically if missing.

Also bumped `openai` to `1.69.0` (from `1.59.6`) — the minimum version
`openinference-instrumentation-openai` requires; confirmed the rest of
the backend still works unchanged at this version.

Verified: `GET /observability/status` reports `"mode": "phoenix-remote"`,
and a real ingest + query against the live backend produced **zero**
span-export errors in the log (previously: a `405` on every batch, before
the path fix). Check your Phoenix Cloud project (`rag_end_to_end_demo`)
at the URL shown in the sidebar to see the actual trace data.

## Known deviations / trade-offs from the original spec

- **Hybrid search** is a pragmatic dense-score + keyword-match boost, not
  full Qdrant sparse-vector hybrid search — documented in
  `backend/vector_store.py`.
- **Chunking** strategies (recursive/character/token/semantic) are
  reimplemented directly rather than pulling in `langchain_text_splitters`
  / `langchain_experimental`, to keep the dependency footprint small.
- **Eval metrics** use a scripted single-call LLM-judge (`gpt-4o-mini`)
  rather than `ragas` — judged too heavy/fragile for this demo's scope.
  Context recall is omitted (needs ground-truth answers not available
  live).
- **Phoenix observability**: resolved — see "Phoenix Cloud — now actually
  connected" above. `arize-phoenix-otel` (not the full `arize-phoenix`
  package) is pinned in `requirements.txt` and works alongside this
  project's FastAPI/pydantic pins. Without `PHOENIX_API_KEY`/
  `PHOENIX_COLLECTOR_ENDPOINT` set, it still falls back to structured
  JSON stdout spans.
- **Python version**: use 3.11 or 3.12 for the venv. `tiktoken` and
  `pydantic-core` don't yet ship prebuilt wheels for 3.14, and building
  them from source requires a Rust toolchain.

## Deployment

Target is **Render only** (both FastAPI backend and Streamlit frontend) —
Vercel cannot host either (no long-running server support). Not yet
configured; run `deployment-advisor`/`containerize-project` when ready to
deploy.
