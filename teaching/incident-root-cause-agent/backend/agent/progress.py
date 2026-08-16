"""Step-by-step progress events for the streaming API.

The blocking `/incidents` and `/incidents/{id}/approve` routes run the
entire graph invocation before returning anything — for the analysis leg
in particular (up to ANALYSIS_STEP_CEILING tool calls), that can be a
silent multi-second wait with no feedback. This module lets graph nodes
emit human-readable progress events DURING that run, which
`interface.py`'s stream_* generators forward to the client over SSE.

Same contextvar-scoping pattern as budget.py's incident_budget(): a
context manager sets an active sink for the duration of one graph
invocation; emit_progress() is a safe no-op when called outside any
active sink (e.g. seed_data.py, or the blocking non-streaming routes,
which never open a sink), so graph.py's node functions can call it
unconditionally without needing to know whether anyone's listening.
"""
from __future__ import annotations

import queue
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

_current_sink: ContextVar["queue.Queue | None"] = ContextVar("_current_sink", default=None)


@contextmanager
def progress_stream(sink: "queue.Queue[dict[str, Any]]"):
    """Context manager: progress events emitted anywhere in this call
    stack (including inside graph node functions several calls deep) are
    pushed onto `sink`. Must be entered from the SAME thread that will run
    the graph invocation — contextvars propagate down a call stack within
    one thread but are NOT inherited by a new threading.Thread, so
    interface.py's stream_* generators enter this from inside their
    worker thread's target function, not from the caller's thread."""
    token = _current_sink.set(sink)
    try:
        yield
    finally:
        _current_sink.reset(token)


def emit_progress(message: str, **fields: Any) -> None:
    """Push one progress event. No-op if no progress_stream() is active
    (blocking routes, seed_data.py, tests that don't opt in) — every
    graph.py call site uses this unconditionally rather than checking
    first, mirroring budget.record_tokens()'s same safe-no-op contract."""
    sink = _current_sink.get()
    if sink is not None:
        sink.put({"type": "progress", "message": message, **fields})
