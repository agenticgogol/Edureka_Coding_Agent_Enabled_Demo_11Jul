# Basic End-to-End Chatbot (Teaching Demo)

Streamlit frontend + FastAPI backend chatbot demonstrating:
- Provider/model selection from the UI (OpenAI, Anthropic, Groq, Gemini)
- User-supplied API key from the UI
- Default-to-OpenAI-from-.env when provider/key isn't chosen
- Multi-turn conversation via server-side, in-memory session history

## Structure

```
backend/
  main.py            FastAPI app: POST /chat, POST /reset/{session_id}, GET /health
  llm_client.py       Provider-swappable client (openai/anthropic/groq/gemini)
  config.py           Loads OPENAI_API_KEY from .env, fails loudly if unset
  session_store.py    In-memory history keyed by session_id
frontend/
  app.py              Streamlit UI: provider/key sidebar + chat
requirements.txt
```

## Setup

From this folder:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Ensure `OPENAI_API_KEY` is set in the repo-root `.env` (required for the
default-provider flow). Other providers require the user to paste their
own key in the sidebar — no other provider key is read from `.env`.

## Run

Two terminals, both from this folder:

```bash
# Terminal 1
.venv/bin/uvicorn backend.main:app --reload --port 8000

# Terminal 2
.venv/bin/streamlit run frontend/app.py
```

Open the Streamlit URL it prints (usually http://localhost:8501).

## Verified

- **Provider verified:** OpenAI, `gpt-4o-mini`, live call succeeded
  (`require-api-key` check, 2026-07-13).
- **Scenario 1 (default flow):** left provider/key at default in the
  sidebar → backend used `OPENAI_API_KEY` from `.env` → "What is the
  capital of France?" → "Paris" → follow-up "What is its population?"
  answered correctly using session history, no restating "Paris".
  Verified via direct `/chat` calls against the running backend.
- **Scenario 2 (explicit choice flow):** passed `provider` + `api_key`
  explicitly in the request (proving the non-default code path) →
  same Q&A + follow-up succeeded with session history intact.
  Note: this was verified using an OpenAI key (the only key with live
  quota at verification time) rather than Anthropic/Groq/Gemini — the
  Gemini key in `.env` returned a real `429 RESOURCE_EXHAUSTED` quota
  error, which the backend correctly surfaced as an HTTP 502 with detail
  rather than silently falling back. To demo with Anthropic/Groq/Gemini
  live, paste a key with available quota into the sidebar.
- Both `backend/main.py` calling into `llm_client.py`, and
  `frontend/app.py` calling the backend's actual `/chat` route, were
  manually contract-checked and exercised end to end (no
  `integrate-and-assemble`/`lint-and-typecheck` — per the lighter
  teaching-track pipeline).

## Testing

**Bug fix (2026-07-13):** Choosing "anthropic" as provider with a real
API key and sending a message returned `Error: anthropic call failed:
'ThinkingBlock' object has no attribute 'text'`. Root cause:
`llm_client.py`'s Anthropic branch assumed `response.content[0]` was
always a text block, but Anthropic's Messages API can return a
`ThinkingBlock` first (extended thinking), which has no `.text`
attribute. Fixed by iterating `response.content` and returning the first
block where `block.type == "text"`. Reproduced with a real Anthropic key
before the fix (confirmed the exact error), then re-verified after the
fix: same question ("What is the capital of France?") + multi-turn
follow-up ("What is its population?") both succeeded via Anthropic, and
the default OpenAI flow was re-checked afterward with no regression.

## Extension ideas

- Add streaming responses (SSE/websockets) instead of one-shot replies.
- Persist session history to disk/DB instead of in-memory.
- Add Phoenix observability (`/add-teaching-step` to wire this in later).
