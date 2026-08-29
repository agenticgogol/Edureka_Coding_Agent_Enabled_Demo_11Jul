"""Provider-swappable LLM client, adapted from `_shared/llm_client.py`.

Adds `provider`/`api_key` overrides on top of the shared template so the
Streamlit sidebar can override the provider/model/key at runtime for a
given session, per the teaching brief's constraint — falling back to
`.env` (via config.py) when the override args are left as None.

No mock mode: every call goes to a real provider. Raises on any provider
error rather than returning a placeholder.
"""
from __future__ import annotations

import os

from .config import DEFAULT_ANTHROPIC_MODEL, DEFAULT_GROQ_MODEL, DEFAULT_OPENAI_MODEL, config
from backend.observability import traced_operation


class LLMCallError(RuntimeError):
    """Raised when the underlying provider call fails."""


def _output_token_budget() -> int:
    """Keep classroom-demo responses concise and costs bounded."""
    try:
        return max(256, min(int(os.environ.get("LLM_MAX_OUTPUT_TOKENS", "1024")), 2048))
    except ValueError:
        return 1024


def _resolve(provider: str | None, api_key: str | None) -> tuple[str, str]:
    """Resolve which provider/key to use for this call.

    Explicit (provider, api_key) from a session override wins. Otherwise
    fall back to whichever real key is present in .env, Anthropic first.
    """
    if provider:
        if api_key:
            return provider.lower(), api_key
        configured_keys = {
            "anthropic": config.anthropic_api_key,
            "openai": config.openai_api_key,
            "groq": config.groq_api_key,
        }
        configured_key = configured_keys.get(provider.lower(), "")
        if configured_key:
            return provider.lower(), configured_key
        raise LLMCallError(
            f"Provider '{provider}' was selected but no API key is configured for it. "
            "Set its key in .env or provide the sidebar override."
        )
    if config.anthropic_api_key:
        return "anthropic", config.anthropic_api_key
    if config.openai_api_key:
        return "openai", config.openai_api_key
    if config.groq_api_key:
        return "groq", config.groq_api_key
    raise LLMCallError(
        "No LLM provider configured. Set ANTHROPIC_API_KEY, OPENAI_API_KEY, "
        "or GROQ_API_KEY in .env, or pass a provider/api_key override — "
        "there is no mock fallback."
    )


def complete(
    prompt: str,
    system: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    api_key: str | None = None,
) -> str:
    """Single entrypoint every agent node calls for a real LLM completion.

    `provider`/`api_key` let a caller (e.g. a Streamlit-sidebar-selected
    session override) bypass the `.env` default for this one call; both
    must be supplied together to take effect.
    """
    resolved_provider, resolved_key = _resolve(provider, api_key)

    try:
        if resolved_provider == "anthropic":
            import anthropic

            with traced_operation("llm_call", provider=resolved_provider, model=model or DEFAULT_ANTHROPIC_MODEL):
                client = anthropic.Anthropic(api_key=resolved_key)
                response = client.messages.create(
                    model=model or DEFAULT_ANTHROPIC_MODEL,
                    max_tokens=_output_token_budget(),
                    system=system or "",
                    messages=[{"role": "user", "content": prompt}],
                )
            return response.content[0].text

        if resolved_provider == "openai":
            from openai import OpenAI

            client = OpenAI(api_key=resolved_key)
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            with traced_operation("llm_call", provider=resolved_provider, model=model or DEFAULT_OPENAI_MODEL):
                response = client.chat.completions.create(
                    model=model or DEFAULT_OPENAI_MODEL,
                    messages=messages,
                    max_tokens=_output_token_budget(),
                )
            return response.choices[0].message.content

        if resolved_provider == "groq":
            from groq import Groq

            client = Groq(api_key=resolved_key)
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            with traced_operation("llm_call", provider=resolved_provider, model=model or DEFAULT_GROQ_MODEL):
                response = client.chat.completions.create(
                    model=model or DEFAULT_GROQ_MODEL,
                    messages=messages,
                    max_tokens=_output_token_budget(),
                )
            return response.choices[0].message.content

        raise LLMCallError(f"Unknown provider '{resolved_provider}'.")
    except LLMCallError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise LLMCallError(f"LLM call to provider '{resolved_provider}' failed: {exc}") from exc


def verify_key() -> str:
    """Makes one cheap real call to confirm the configured key actually
    works. Returns the provider name on success; raises on failure."""
    provider, _ = _resolve(None, None)
    complete("Reply with the word OK.", provider=provider, api_key=None)
    return provider
