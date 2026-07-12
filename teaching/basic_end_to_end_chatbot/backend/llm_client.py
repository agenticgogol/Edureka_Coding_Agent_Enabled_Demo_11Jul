"""Provider-swappable LLM client for the chatbot demo.

Unlike _shared/llm_client.py (which reads one globally-configured key),
this demo needs per-request provider selection and an optional
user-supplied key from the Streamlit frontend, defaulting to OpenAI from
.env only when nothing is chosen. No mock mode — every call goes to a
real provider and raises loudly on failure.
"""
from __future__ import annotations

from .config import config

SUPPORTED_PROVIDERS = ["openai", "anthropic", "groq", "gemini"]

DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-sonnet-5",
    "groq": "llama-3.1-70b-versatile",
    "gemini": "gemini-2.0-flash",
}


class MissingAPIKeyError(RuntimeError):
    pass


def resolve_provider_and_key(provider: str | None, api_key: str | None) -> tuple[str, str]:
    """Applies the default-to-OpenAI rule: if provider or key is missing,
    fall back to OpenAI + the .env key. Otherwise use exactly what the
    caller supplied."""
    if not provider or not api_key:
        if not config.openai_api_key:
            raise MissingAPIKeyError(
                "No provider/key chosen and OPENAI_API_KEY is not set in .env — "
                "there is no fallback."
            )
        return "openai", config.openai_api_key

    provider = provider.lower()
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(f"Unsupported provider: {provider}")
    return provider, api_key


def complete(provider: str, api_key: str, messages: list[dict], model: str | None = None) -> str:
    """messages is a list of {"role": "user"|"assistant", "content": str}
    in chronological order (multi-turn history)."""
    model = model or DEFAULT_MODELS[provider]

    if provider == "openai":
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(model=model, messages=messages)
        return response.choices[0].message.content

    if provider == "anthropic":
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            messages=messages,
        )
        for block in response.content:
            if block.type == "text":
                return block.text
        raise RuntimeError("Anthropic response had no text block (only thinking/tool_use).")

    if provider == "groq":
        from groq import Groq

        client = Groq(api_key=api_key)
        response = client.chat.completions.create(model=model, messages=messages)
        return response.choices[0].message.content

    if provider == "gemini":
        from google import genai as google_genai
        from google.genai import types as google_genai_types

        client = google_genai.Client(api_key=api_key)
        # Gemini uses "user"/"model" roles.
        contents = [
            google_genai_types.Content(
                role="user" if m["role"] == "user" else "model",
                parts=[google_genai_types.Part(text=m["content"])],
            )
            for m in messages
        ]
        response = client.models.generate_content(model=model, contents=contents)
        return response.text

    raise ValueError(f"Unsupported provider: {provider}")


def verify_key(provider: str, api_key: str) -> str:
    """One cheap real call to confirm a key actually works. Raises on failure."""
    complete(provider, api_key, [{"role": "user", "content": "Reply with the word OK."}])
    return provider
