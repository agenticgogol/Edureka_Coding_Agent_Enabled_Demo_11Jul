"""Phoenix tracing, default ON, toggleable per-request via
`observability_enabled` on the /query request.

Fallback chain (checked once at process start, then reused):
1. If PHOENIX_COLLECTOR_ENDPOINT is set: use arize-phoenix's OTLP exporter
   pointed at that endpoint, instrumented via
   openinference-instrumentation-openai, so real spans go to Phoenix
   Cloud (or any self-hosted Phoenix collector at that URL).
2. Else, if the `phoenix` package is installed locally: launch a local
   OSS Phoenix app (`phoenix.launch_app()`) and send spans there
   (viewable at http://localhost:6006).
3. Else (neither configured nor installed): fall back to structured JSON
   span logs written to stdout — still gives visible per-query tracing
   for the demo without any extra infra.

This module is defensive about missing packages (arize-phoenix /
openinference are optional extras — see requirements.txt) since a
teaching environment may not have them installed; it never blocks the
query/ingest pipeline if tracing setup fails.
"""
from __future__ import annotations

import json
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, field

from .config import config

_tracer_initialized = False
_tracer = None
_mode = "uninitialized"


def _init_tracer() -> None:
    global _tracer_initialized, _tracer, _mode
    if _tracer_initialized:
        return
    _tracer_initialized = True

    if config.phoenix_collector_endpoint:
        try:
            from openinference.instrumentation.openai import OpenAIInstrumentor
            from phoenix.otel import register

            # HTTP/protobuf transport requires the full OTLP traces path —
            # a bare Phoenix Cloud space URL (https://app.phoenix.arize.com/s/<space>)
            # returns 405 Method Not Allowed without the /v1/traces suffix.
            endpoint = config.phoenix_collector_endpoint.rstrip("/")
            if not endpoint.endswith("/v1/traces"):
                endpoint = f"{endpoint}/v1/traces"

            tracer_provider = register(
                endpoint=endpoint,
                api_key=config.phoenix_api_key or None,
                project_name="rag_end_to_end_demo",
                auto_instrument=False,  # we call OpenAIInstrumentor explicitly below
                batch=True,
            )
            OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)
            _tracer = tracer_provider.get_tracer(__name__)
            _mode = "phoenix-remote"
            return
        except Exception as e:  # pragma: no cover - environment dependent
            print(f"[observability] remote Phoenix setup failed, falling back: {e}", file=sys.stderr)

    try:
        import phoenix as px

        px.launch_app()
        from openinference.instrumentation.openai import OpenAIInstrumentor
        from phoenix.otel import register

        tracer_provider = register(project_name="rag_end_to_end_demo")
        OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)
        _tracer = tracer_provider.get_tracer(__name__)
        _mode = "phoenix-local"
        return
    except Exception as e:  # pragma: no cover - environment dependent
        print(f"[observability] local Phoenix setup unavailable, falling back to stdout spans: {e}", file=sys.stderr)

    _mode = "stdout-json"


def get_mode() -> str:
    _init_tracer()
    return _mode


def get_status() -> dict:
    """Used by GET /observability/status so the frontend can honestly show
    whether Phoenix is actually connected, rather than assuming the
    default-ON toggle means it's live."""
    mode = get_mode()
    return {
        "mode": mode,
        "phoenix_collector_endpoint": config.phoenix_collector_endpoint or None,
        "description": {
            "phoenix-remote": "Connected to Phoenix Cloud / a remote Phoenix collector.",
            "phoenix-local": "Using a local Phoenix instance (http://localhost:6006).",
            "stdout-json": "Not connected to Phoenix — tracing spans are printed as "
            "structured JSON to the backend's stdout (no PHOENIX_COLLECTOR_ENDPOINT set, "
            "and/or the arize-phoenix package isn't installed).",
        }.get(mode, "unknown"),
    }


@contextmanager
def span(name: str, enabled: bool = True, **attributes):
    """Wraps a pipeline stage. If enabled=False (observability_enabled=false
    on the request), this is a pure no-op context manager."""
    if not enabled:
        yield
        return

    _init_tracer()
    start = time.time()

    if _mode in ("phoenix-remote", "phoenix-local") and _tracer is not None:
        with _tracer.start_as_current_span(name) as otel_span:
            for key, value in attributes.items():
                try:
                    otel_span.set_attribute(key, value)
                except Exception:
                    pass
            yield
        return

    # stdout-json fallback
    yield
    duration_ms = round((time.time() - start) * 1000, 2)
    print(
        json.dumps({"span": name, "duration_ms": duration_ms, **attributes}, default=str),
        file=sys.stdout,
    )
