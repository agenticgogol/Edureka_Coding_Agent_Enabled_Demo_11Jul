"""Phoenix tracing — actually wired, not just config scaffolding.

Previously `config.py` had `phoenix_collector_endpoint`/`phoenix_api_key`
fields but nothing ever read them: no `arize-phoenix`/`openinference` in
requirements.txt, no instrumentation call anywhere. This module closes that
gap. It's optional: if `PHOENIX_COLLECTOR_ENDPOINT` isn't set, `setup_tracing()`
is a no-op (logged once) rather than a hard failure — unlike OPENAI_API_KEY,
tracing isn't required for the agent to function, so there's no case for
failing loudly here the way config.py does for the LLM key.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any
from urllib.parse import urlparse, urlunparse

from .config import config

logger = logging.getLogger("incident_backend.tracing")

_tracing_initialized = False
_TRACER_NAME = "incident-root-cause-agent"


def _otlp_traces_endpoint(endpoint: str) -> str:
    """Normalize a Phoenix base/UI URL to the OTLP/HTTP traces endpoint."""
    parsed = urlparse(endpoint.rstrip("/"))
    path = parsed.path or ""
    if path.endswith("/v1/traces"):
        return urlunparse(parsed)
    if path.endswith("/v1"):
        path = f"{path}/traces"
    else:
        path = f"{path}/v1/traces"
    return urlunparse(parsed._replace(path=path))


def setup_tracing() -> bool:
    """Idempotent. Registers an OpenTelemetry tracer pointed at Phoenix and
    instruments the OpenAI SDK so every chat/embeddings call in llm.py is
    automatically traced. Returns True if tracing was actually enabled,
    False if skipped (no collector endpoint configured) or if the optional
    tracing dependencies aren't installed. Call once at backend startup."""
    global _tracing_initialized
    if _tracing_initialized:
        return True

    if not config.phoenix_collector_endpoint:
        logger.info(
            "PHOENIX_COLLECTOR_ENDPOINT not set — tracing disabled. Set it "
            "in .env to enable (see .env.example)."
        )
        return False

    try:
        from openinference.instrumentation.openai import OpenAIInstrumentor
        from phoenix.otel import register
    except ImportError:
        logger.warning(
            "PHOENIX_COLLECTOR_ENDPOINT is set but tracing dependencies are "
            "not installed. Run: pip install -r backend/requirements.txt "
            "(arize-phoenix-otel + openinference-instrumentation-openai)."
        )
        return False

    headers = {}
    if config.phoenix_api_key:
        headers["api_key"] = config.phoenix_api_key

    collector_endpoint = _otlp_traces_endpoint(config.phoenix_collector_endpoint)
    tracer_provider = register(
        project_name="incident-root-cause-agent",
        endpoint=collector_endpoint,
        headers=headers or None,
        batch=True,  # BatchSpanProcessor, not the default SimpleSpanProcessor
    )
    OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)

    _tracing_initialized = True
    logger.info("Phoenix tracing enabled -> %s", collector_endpoint)
    return True


@contextmanager
def span(name: str, **attributes: Any):
    """Manual span around agent-level work — graph nodes and tool calls —
    that `OpenAIInstrumentor` doesn't see because it only wraps the OpenAI
    SDK call itself. Without this, a Phoenix trace showed LLM latency/cost
    but nothing about which tool the agent actually invoked, how long
    `run_tests`/`apply_patch` took, or how long a human sat on the
    approval step. No-op (returns a null context) if tracing was never
    enabled or opentelemetry isn't importable, so every call site here is
    safe to use unconditionally regardless of whether PHOENIX_COLLECTOR_ENDPOINT
    is set.

    Attribute values are coerced to str/int/float/bool/None (OTel's
    allowed span-attribute types) — anything else is stringified.
    """
    if not _tracing_initialized:
        yield None
        return
    try:
        from opentelemetry import trace
    except ImportError:
        yield None
        return

    tracer = trace.get_tracer(_TRACER_NAME)
    with tracer.start_as_current_span(name) as current_span:
        for key, value in attributes.items():
            if value is None:
                continue
            if not isinstance(value, (str, int, float, bool)):
                value = str(value)
            current_span.set_attribute(key, value)
        yield current_span
