"""FastAPI backend for the basic end-to-end chatbot teaching demo.

Endpoint: POST /chat
- Accepts provider, optional api_key, session_id, and message.
- Defaults to OpenAI + OPENAI_API_KEY from .env if provider/api_key is
  not supplied (Feature 3 from teaching_brief.md).
- Appends to and reads from in-memory session history (Feature 4).
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from . import session_store
from .llm_client import MissingAPIKeyError, resolve_provider_and_key, complete

app = FastAPI(title="Basic End-to-End Chatbot")


class ChatRequest(BaseModel):
    session_id: str
    message: str
    provider: str | None = None
    api_key: str | None = None


class ChatResponse(BaseModel):
    reply: str
    provider_used: str
    history: list[dict]


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    try:
        provider, api_key = resolve_provider_and_key(req.provider, req.api_key)
    except MissingAPIKeyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    history = session_store.get_history(req.session_id)
    messages = history + [{"role": "user", "content": req.message}]

    try:
        reply = complete(provider, api_key, messages)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"{provider} call failed: {e}")

    session_store.append_turn(req.session_id, "user", req.message)
    session_store.append_turn(req.session_id, "assistant", reply)

    return ChatResponse(
        reply=reply,
        provider_used=provider,
        history=session_store.get_history(req.session_id),
    )


@app.post("/reset/{session_id}")
def reset(session_id: str) -> dict:
    session_store.clear_session(session_id)
    return {"status": "cleared", "session_id": session_id}
