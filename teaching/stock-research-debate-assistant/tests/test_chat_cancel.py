"""Unit tests for server-side turn cancellation (see
`.claude/plans/vectorized-coalescing-garden.md` section B).

No real LLM/graph execution in either test:
- `CancelRegistryLoopTests` exercises the same "iterate + check cancel_event
  after each yielded value" pattern `run_turn` uses against a synthetic
  generator, confirming the loop stops as soon as the event is set.
- `CancelRouteTests` drives `POST /chat/cancel/{job_id}` via FastAPI's
  TestClient against `backend/api/routes.py`'s `_CANCEL_EVENTS` registry
  directly (no auth needed -- the route takes no session token), covering
  both the 202 (known job) and 404 (unknown job) paths.
"""
from __future__ import annotations

import threading
import unittest

from fastapi.testclient import TestClient

from backend.api import routes
from backend.main import app


def _synthetic_state_stream():
    """Mimics graph.stream(stream_mode='values')'s shape: a generator of
    full accumulated state dicts, one per node boundary."""
    for i in range(5):
        yield {"step": i}


class CancelRegistryLoopTests(unittest.TestCase):
    def test_loop_stops_after_event_is_set(self):
        cancel_event = threading.Event()
        seen = []
        for i, state_update in enumerate(_synthetic_state_stream()):
            seen.append(state_update)
            if i == 1:
                cancel_event.set()
            if cancel_event.is_set():
                break
        # Stopped right after the node where cancel was requested, not at
        # the end of the 5-item stream.
        self.assertEqual(seen, [{"step": 0}, {"step": 1}])

    def test_loop_runs_to_completion_when_never_cancelled(self):
        cancel_event = threading.Event()
        seen = []
        for state_update in _synthetic_state_stream():
            seen.append(state_update)
            if cancel_event.is_set():
                break
        self.assertEqual(len(seen), 5)

    def test_loop_with_no_cancel_event_behaves_like_plain_iteration(self):
        # run_turn's cancel_event param defaults to None -- callers that
        # don't pass it (e.g. /chat, /chat/start) must see identical
        # behavior to the old graph.invoke() path: full completion.
        cancel_event = None
        seen = []
        for state_update in _synthetic_state_stream():
            seen.append(state_update)
            if cancel_event is not None and cancel_event.is_set():
                break
        self.assertEqual(len(seen), 5)


class CancelRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def tearDown(self):
        routes._CANCEL_EVENTS.clear()

    def test_cancel_unknown_job_returns_404(self):
        response = self.client.post("/chat/cancel/does-not-exist")
        self.assertEqual(response.status_code, 404)

    def test_cancel_known_job_returns_202_and_sets_event(self):
        job_id = "test-job-123"
        event = threading.Event()
        with routes._JOB_LOCK:
            routes._CANCEL_EVENTS[job_id] = event

        response = self.client.post(f"/chat/cancel/{job_id}")

        self.assertEqual(response.status_code, 202)
        self.assertTrue(event.is_set())


if __name__ == "__main__":
    unittest.main()
