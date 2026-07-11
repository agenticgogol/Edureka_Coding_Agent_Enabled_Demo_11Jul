"""Shared provider-swappable LLM client template — copied per-project.

Copy into the project (e.g. backend/llm_client.py) alongside config.py.
No mock mode: if no provider key is configured, config.py already raised
MissingAPIKeyError at import time (see require_llm_key()), so by the time
complete() runs, a key is guaranteed present — this module still verifies
the actual call succeeds rather than assuming a present key is a valid
one.
"""
from __future__ import annotations

from .config import config  # adjust relative import after copying into project


def complete(prompt: str, system: str | None = None, model: str | None = None) -> str:
    """Single entrypoint every project's backend/agent code should call.

    Never call a provider SDK directly from application code — go through
    this function so provider swapping stays centralized. Raises on any
    provider error rather than returning a placeholder — there is no
    fallback response in this repo.
    """
    if config.anthropic_api_key:
        import anthropic

        client = anthropic.Anthropic(api_key=config.anthropic_api_key)
        response = client.messages.create(
            model=model or "claude-sonnet-5",
            max_tokens=1024,
            system=system or "",
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    if config.openai_api_key:
        from openai import OpenAI

        client = OpenAI(api_key=config.openai_api_key)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        response = client.chat.completions.create(model=model or "gpt-4o-mini", messages=messages)
        return response.choices[0].message.content

    if config.groq_api_key:
        from groq import Groq

        client = Groq(api_key=config.groq_api_key)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        response = client.chat.completions.create(
            model=model or "llama-3.1-70b-versatile", messages=messages
        )
        return response.choices[0].message.content

    # Unreachable in practice: config.require_llm_key() already raised at
    # import time if no key was set. Kept as a defensive final check.
    raise RuntimeError(
        "No LLM provider configured. Set ANTHROPIC_API_KEY, OPENAI_API_KEY, "
        "or GROQ_API_KEY in .env — there is no mock fallback."
    )


def verify_key() -> str:
    """Makes one cheap real call to confirm the configured key actually
    works. Used by the require-api-key skill before any build starts.
    Returns the provider name on success; raises on failure."""
    if config.anthropic_api_key:
        complete("Reply with the word OK.", model="claude-sonnet-5")
        return "anthropic"
    if config.openai_api_key:
        complete("Reply with the word OK.", model="gpt-4o-mini")
        return "openai"
    if config.groq_api_key:
        complete("Reply with the word OK.", model="llama-3.1-70b-versatile")
        return "groq"
    raise RuntimeError("No LLM provider configured.")
