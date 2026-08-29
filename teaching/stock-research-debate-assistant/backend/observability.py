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

import json
import os
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from dotenv import load_dotenv

load_dotenv()

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
    }

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
                otel_span.set_attribute("latency_seconds", attrs["latency_seconds"])
                otel_span.set_attribute("output.value", str(attrs.get("final_answer", "")))
                otel_span.set_attribute("stance", str(attrs.get("stance")))
                otel_span.set_attribute(
                    "trail_events_json", json.dumps(attrs.get("trail_events", []), default=str)
                )
    else:
        try:
            yield attrs
        except Exception as exc:  # noqa: BLE001
            attrs["error"] = str(exc)
            raise
        finally:
            attrs["latency_seconds"] = time.time() - start
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
