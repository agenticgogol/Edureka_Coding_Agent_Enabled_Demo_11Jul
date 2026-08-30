"""Tracing/observability wiring for the stock-research-debate-assistant backend.

Per this repo's `eval-and-observability` skill: prefer Arize Phoenix,
falling back to a local OSS Phoenix instance, falling back to structured
JSON span logs written to a local file. This module is purely additive
instrumentation at the FastAPI call boundary — it does not modify
`backend/agent/`'s behavior.

Tier selection (checked once at import time):
1. `PHOENIX_COLLECTOR_ENDPOINT` set in `.env` -> configure the OpenInference/
   OTel exporter to ship spans to that remote Phoenix collector.
2. `arize-phoenix` installed but no collector endpoint set -> launch a local
   Phoenix app (`phoenix.launch_app()`) and point the OTel exporter at it.
3. `arize-phoenix` not installed / launch fails -> last-resort structured
   JSON span logs appended to `backend/data/trace_log.jsonl`.

Every tier exposes the same `traced_chat_call(session_id, user_message)`
context manager so `main.py` doesn't need to know which tier is active.
"""
from __future__ import annotations

import contextvars
import json
import os
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from dotenv import load_dotenv

load_dotenv()

# Per-turn LLM usage accumulator. Set to a fresh list by `traced_chat_call`
# at the start of each `/chat`-style request, appended to by
# `record_llm_usage` (called from `agent/llm_client.py` right after every
# real provider response comes back), and read back out into
# `attrs["usage"]` when the request context manager exits. A ContextVar
# rather than a module-level list because `/chat/start` runs each turn on
# its own background thread — a brand-new thread gets its own empty
# Context, so concurrent turns never see each other's usage entries.
_USAGE_CTX: contextvars.ContextVar[list[dict[str, Any]] | None] = contextvars.ContextVar(
    "usage_ctx", default=None
)

# Approximate published per-1K-token USD pricing, (input_rate, output_rate).
# These are intentionally rough — good enough for "roughly how much did this
# turn cost" visibility in a teaching demo, not a billing-grade figure.
# Update here if a model's list price changes; unknown models fall back to
# the provider's "default" entry.
_COST_PER_1K_TOKENS_USD: dict[str, dict[str, tuple[float, float]]] = {
    "anthropic": {
        "claude-3-5-sonnet-20241022": (0.003, 0.015),
        "claude-3-5-haiku-20241022": (0.0008, 0.004),
        "claude-3-haiku-20240307": (0.00025, 0.00125),
        "default": (0.003, 0.015),
    },
    "openai": {
        "gpt-4o": (0.0025, 0.01),
        "gpt-4o-mini": (0.00015, 0.0006),
        "default": (0.0025, 0.01),
    },
    "groq": {
        # Groq's Llama/Mixtral hosting is priced far below Anthropic/OpenAI;
        # this default approximates their published Llama-3.1-70b rate.
        "default": (0.00059, 0.00079),
    },
}


def estimate_cost_usd(provider: str, model: str | None, tokens_in: int, tokens_out: int) -> float:
    """Best-effort USD cost estimate for one LLM call. See
    `_COST_PER_1K_TOKENS_USD`'s docstring note above: approximate, not
    billing-grade."""
    table = _COST_PER_1K_TOKENS_USD.get(provider, {})
    in_rate, out_rate = table.get(model or "", table.get("default", (0.0, 0.0)))
    return (tokens_in / 1000.0) * in_rate + (tokens_out / 1000.0) * out_rate


def record_llm_usage(
    *,
    node: str | None,
    provider: str,
    model: str,
    tokens_in: int,
    tokens_out: int,
    latency_seconds: float,
) -> None:
    """Called by `agent/llm_client.py` right after every real provider
    response, so the current request's usage list (if any) gets one entry
    per LLM call: node name, tokens in/out, latency, estimated cost.
    No-ops outside of a `traced_chat_call` context (e.g. `verify_key()` at
    startup), since there's no per-turn usage list to append to then."""
    usage_list = _USAGE_CTX.get()
    if usage_list is None:
        return
    usage_list.append(
        {
            "node": node,
            "provider": provider,
            "model": model,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "latency_seconds": round(latency_seconds, 3),
            "estimated_cost_usd": round(estimate_cost_usd(provider, model, tokens_in, tokens_out), 6),
        }
    )

_DATA_DIR = Path(__file__).resolve().parent / "data"
_DATA_DIR.mkdir(parents=True, exist_ok=True)
_JSON_TRACE_LOG = _DATA_DIR / "trace_log.jsonl"

_PHOENIX_COLLECTOR_ENDPOINT = os.environ.get("PHOENIX_COLLECTOR_ENDPOINT", "")

_tier = "json_log"
_tracer = None

try:
    import phoenix as px
    from openinference.instrumentation import using_attributes  # noqa: F401
    from opentelemetry import trace as _otel_trace
    from phoenix.otel import register

    if _PHOENIX_COLLECTOR_ENDPOINT:
        # Tier 1: ship to a remote/self-hosted Phoenix collector.
        _tracer_provider = register(
            endpoint=_PHOENIX_COLLECTOR_ENDPOINT,
            project_name="stock-research-debate-assistant",
        )
        _tracer = _tracer_provider.get_tracer(__name__)
        _tier = "phoenix_remote_collector"
    else:
        # Tier 2: launch a local OSS Phoenix app and trace into it.
        px.launch_app()
        _tracer_provider = register(project_name="stock-research-debate-assistant")
        _tracer = _tracer_provider.get_tracer(__name__)
        _tier = "phoenix_local_app"
except Exception:
    # Tier 3: arize-phoenix not installed, or launch failed for any reason
    # (e.g. port in use, no network for the local app UI). Structured JSON
    # span logs are always available and never block a chat request.
    _tracer = None
    _tier = "json_log"


def active_tier() -> str:
    """Returns which tracing tier is actually active, for /health reporting."""
    return _tier


def _write_json_span(span: dict[str, Any]) -> None:
    with _JSON_TRACE_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(span, default=str) + "\n")


@contextmanager
def traced_chat_call(session_id: str, user_message: str) -> Iterator[dict[str, Any]]:
    """One span per `/chat` request. Callers should mutate the yielded dict
    with `trail_events`, `stance`, `final_answer_len`, `error` etc. before
    the context exits, so those become span attributes / JSON log fields.

    This is instrumented at the FastAPI call boundary (wrapping the whole
    `run_turn` call), since the underlying LangGraph node/LLM calls inside
    `backend/agent/` are not this module's to modify.
    """
    span_id = str(uuid.uuid4())
    start = time.time()
    attrs: dict[str, Any] = {
        "span_id": span_id,
        "session_id": session_id,
        "user_message": user_message,
        "trail_events": [],
        "stance": None,
        "error": None,
        "usage": [],
    }
    usage_token = _USAGE_CTX.set([])

    if _tracer is not None:
        with _tracer.start_as_current_span("chat_turn") as otel_span:
            otel_span.set_attribute("session_id", session_id)
            otel_span.set_attribute("input.value", user_message)
            try:
                yield attrs
            except Exception as exc:  # noqa: BLE001
                attrs["error"] = str(exc)
                otel_span.set_attribute("error", str(exc))
                raise
            finally:
                attrs["latency_seconds"] = time.time() - start
                attrs["usage"] = _USAGE_CTX.get() or []
                _USAGE_CTX.reset(usage_token)
                otel_span.set_attribute("latency_seconds", attrs["latency_seconds"])
                otel_span.set_attribute("output.value", str(attrs.get("final_answer", "")))
                otel_span.set_attribute("stance", str(attrs.get("stance")))
                otel_span.set_attribute(
                    "trail_events_json", json.dumps(attrs.get("trail_events", []), default=str)
                )
                otel_span.set_attribute("usage_json", json.dumps(attrs["usage"], default=str))
    else:
        try:
            yield attrs
        except Exception as exc:  # noqa: BLE001
            attrs["error"] = str(exc)
            raise
        finally:
            attrs["latency_seconds"] = time.time() - start
            attrs["usage"] = _USAGE_CTX.get() or []
            _USAGE_CTX.reset(usage_token)
            _write_json_span(attrs)


@contextmanager
def traced_operation(name: str, **attributes: Any) -> Iterator[dict[str, Any]]:
    """Trace an individual LLM or external-tool operation."""
    start = time.time()
    attrs = {"span_id": str(uuid.uuid4()), "operation": name, **attributes}
    if _tracer is not None:
        with _tracer.start_as_current_span(name) as span:
            for key, value in attributes.items():
                span.set_attribute(key, str(value))
            try:
                yield attrs
            except Exception as exc:  # noqa: BLE001
                attrs["error"] = str(exc)
                span.set_attribute("error", str(exc))
                raise
            finally:
                attrs["latency_seconds"] = time.time() - start
    else:
        try:
            yield attrs
        except Exception as exc:  # noqa: BLE001
            attrs["error"] = str(exc)
            raise
        finally:
            attrs["latency_seconds"] = time.time() - start
            _write_json_span(attrs)
