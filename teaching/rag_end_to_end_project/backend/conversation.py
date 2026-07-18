"""Session-scoped chat history + condense-question step.

Before retrieval, if there is prior history, a cheap/fast LLM call
(gpt-4o-mini, low max_tokens) rewrites the new user message into a
standalone query that resolves references to prior turns (e.g. "what did
you just say about X?") into something retrievable on its own. This call
itself contributes to cost tracking (see cost.py / main.py).
"""
from __future__ import annotations

from dataclasses import dataclass

from . import session_store
from .llm_client import chat_completion

CONDENSE_MODEL = "gpt-4o-mini"
CONDENSE_MAX_TOKENS = 200

CONDENSE_SYSTEM_PROMPT = (
    "You rewrite a user's follow-up question into a standalone question "
    "that can be understood without the conversation history. Resolve "
    "pronouns and references (e.g. 'that', 'what you just said', 'it') "
    "using the history. If the latest message is already standalone, "
    "return it unchanged. Reply with ONLY the rewritten question, no "
    "preamble or quotes."
)


@dataclass
class CondenseResult:
    standalone_query: str
    prompt_tokens: int
    completion_tokens: int
    was_condensed: bool


def get_history(session_id: str) -> list[dict]:
    return session_store.get_history(session_id)


def condense_question(session_id: str, message: str) -> CondenseResult:
    history = session_store.get_history(session_id)
    if not history:
        return CondenseResult(
            standalone_query=message, prompt_tokens=0, completion_tokens=0, was_condensed=False
        )

    history_text = "\n".join(f"{turn['role']}: {turn['content']}" for turn in history[-10:])
    messages = [
        {"role": "system", "content": CONDENSE_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Conversation history:\n{history_text}\n\nLatest message: {message}",
        },
    ]
    result = chat_completion(messages, model=CONDENSE_MODEL, max_tokens=CONDENSE_MAX_TOKENS)
    return CondenseResult(
        standalone_query=result.content.strip() or message,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        was_condensed=True,
    )
