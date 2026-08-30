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
import time

from .config import DEFAULT_ANTHROPIC_MODEL, DEFAULT_GROQ_MODEL, DEFAULT_OPENAI_MODEL, config
from backend.observability import record_llm_usage, traced_operation


class LLMCallError(RuntimeError):
    """Raised when the underlying provider call fails."""


# Attempts (including the first try) for a transient provider failure
# (rate limit, timeout, connection error, 5xx) before giving up. Genuine
# 4xx/auth errors are never retried — they won't succeed on retry and
# retrying them just burns API calls/time.
_MAX_ATTEMPTS = 3
_BACKOFF_BASE_SECONDS = 1.0

# OpenAI-API-compatible providers, reached via the `openai` SDK with a
# custom base_url instead of a bespoke client per provider. Covers both
# paid (Kimi/Moonshot, GLM/Zhipu, DeepSeek) and free-tier-capable
# (OpenRouter proxies many free models) options with one code path.
_OPENAI_COMPATIBLE_BASE_URLS: dict[str, str] = {
    "kimi": "https://api.moonshot.cn/v1",
    "moonshot": "https://api.moonshot.cn/v1",
    "glm": "https://open.bigmodel.cn/api/paas/v4",
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
    "deepseek": "https://api.deepseek.com",
    "openrouter": "https://openrouter.ai/api/v1",
}
_OPENAI_COMPATIBLE_DEFAULT_MODELS: dict[str, str] = {
    "kimi": "kimi-k2-0711-preview",
    "moonshot": "kimi-k2-0711-preview",
    "glm": "glm-4-plus",
    "zhipu": "glm-4-plus",
    "deepseek": "deepseek-chat",
    "openrouter": "meta-llama/llama-3.1-8b-instruct:free",
}


def _is_transient(exc: Exception) -> bool:
    """Best-effort classification shared across the anthropic/openai/groq
    SDKs (all three expose a similar exception hierarchy: a `status_code`
    attribute on HTTP-backed errors, plus dedicated RateLimit/Timeout/
    Connection/InternalServerError classes)."""
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        if status_code == 429 or status_code >= 500:
            return True
        if 400 <= status_code < 500:
            return False
    class_name = type(exc).__name__
    transient_markers = (
        "RateLimit",
        "Timeout",
        "APIConnectionError",
        "APIConnectionTimeoutError",
        "InternalServerError",
        "ServiceUnavailable",
        "APITimeoutError",
    )
    return any(marker in class_name for marker in transient_markers)


def _output_token_budget() -> int:
    """Keep classroom-demo responses concise and costs bounded.

    Multi-point debate arguments (several bolded sub-claims per rebuttal)
    were hitting the old 1024-token default mid-sentence and getting cut
    off — 2048 default / 4096 ceiling gives real answers room to finish
    while still bounding cost for a teaching demo.
    """
    try:
        return max(256, min(int(os.environ.get("LLM_MAX_OUTPUT_TOKENS", "2048")), 4096))
    except ValueError:
        return 2048


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
            "Set its key in .env (anthropic/openai/groq only) or provide the sidebar "
            "API key override — required for kimi/moonshot/glm/zhipu/deepseek/openrouter, "
            "which have no .env default."
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
    node: str | None = None,
) -> str:
    """Single entrypoint every agent node calls for a real LLM completion.

    `provider`/`api_key` let a caller (e.g. a Streamlit-sidebar-selected
    session override) bypass the `.env` default for this one call; both
    must be supplied together to take effect.

    `node` is a short label for which agent/graph node is making this call
    (e.g. "orchestrator", "debate_bull", "judge") — purely for cost/token
    observability (`backend.observability.record_llm_usage`); it has no
    effect on the call itself and defaults to None if the caller doesn't
    pass one.
    """
    resolved_provider, resolved_key = _resolve(provider, api_key)

    def _call_once() -> str:
        if resolved_provider == "anthropic":
            import anthropic

            resolved_model = model or DEFAULT_ANTHROPIC_MODEL
            with traced_operation("llm_call", provider=resolved_provider, model=resolved_model):
                client = anthropic.Anthropic(api_key=resolved_key)
                call_start = time.time()
                response = client.messages.create(
                    model=resolved_model,
                    max_tokens=_output_token_budget(),
                    system=system or "",
                    messages=[{"role": "user", "content": prompt}],
                )
                usage = getattr(response, "usage", None)
                record_llm_usage(
                    node=node,
                    provider=resolved_provider,
                    model=resolved_model,
                    tokens_in=getattr(usage, "input_tokens", 0) or 0,
                    tokens_out=getattr(usage, "output_tokens", 0) or 0,
                    latency_seconds=time.time() - call_start,
                )
            return response.content[0].text

        if resolved_provider == "openai":
            from openai import OpenAI

            resolved_model = model or DEFAULT_OPENAI_MODEL
            client = OpenAI(api_key=resolved_key)
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            with traced_operation("llm_call", provider=resolved_provider, model=resolved_model):
                call_start = time.time()
                response = client.chat.completions.create(
                    model=resolved_model,
                    messages=messages,
                    max_tokens=_output_token_budget(),
                )
                usage = getattr(response, "usage", None)
                record_llm_usage(
                    node=node,
                    provider=resolved_provider,
                    model=resolved_model,
                    tokens_in=getattr(usage, "prompt_tokens", 0) or 0,
                    tokens_out=getattr(usage, "completion_tokens", 0) or 0,
                    latency_seconds=time.time() - call_start,
                )
            return response.choices[0].message.content

        if resolved_provider == "groq":
            from groq import Groq

            resolved_model = model or DEFAULT_GROQ_MODEL
            client = Groq(api_key=resolved_key)
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            with traced_operation("llm_call", provider=resolved_provider, model=resolved_model):
                call_start = time.time()
                response = client.chat.completions.create(
                    model=resolved_model,
                    messages=messages,
                    max_tokens=_output_token_budget(),
                )
                usage = getattr(response, "usage", None)
                record_llm_usage(
                    node=node,
                    provider=resolved_provider,
                    model=resolved_model,
                    tokens_in=getattr(usage, "prompt_tokens", 0) or 0,
                    tokens_out=getattr(usage, "completion_tokens", 0) or 0,
                    latency_seconds=time.time() - call_start,
                )
            return response.choices[0].message.content

        if resolved_provider in _OPENAI_COMPATIBLE_BASE_URLS:
            from openai import OpenAI

            resolved_model = model or _OPENAI_COMPATIBLE_DEFAULT_MODELS[resolved_provider]
            client = OpenAI(api_key=resolved_key, base_url=_OPENAI_COMPATIBLE_BASE_URLS[resolved_provider])
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            with traced_operation("llm_call", provider=resolved_provider, model=resolved_model):
                call_start = time.time()
                response = client.chat.completions.create(
                    model=resolved_model,
                    messages=messages,
                    max_tokens=_output_token_budget(),
                )
                usage = getattr(response, "usage", None)
                record_llm_usage(
                    node=node,
                    provider=resolved_provider,
                    model=resolved_model,
                    tokens_in=getattr(usage, "prompt_tokens", 0) or 0,
                    tokens_out=getattr(usage, "completion_tokens", 0) or 0,
                    latency_seconds=time.time() - call_start,
                )
            return response.choices[0].message.content

        raise LLMCallError(f"Unknown provider '{resolved_provider}'.")

    last_exc: Exception | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            return _call_once()
        except LLMCallError:
            raise
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt >= _MAX_ATTEMPTS or not _is_transient(exc):
                raise LLMCallError(
                    f"LLM call to provider '{resolved_provider}' failed: {exc}"
                ) from exc
            time.sleep(_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)))
    # Unreachable, but keeps type-checkers happy.
    raise LLMCallError(f"LLM call to provider '{resolved_provider}' failed: {last_exc}")


def verify_key() -> str:
    """Makes one cheap real call to confirm the configured key actually
    works. Returns the provider name on success; raises on failure."""
    provider, _ = _resolve(None, None)
    complete("Reply with the word OK.", provider=provider, api_key=None)
    return provider
