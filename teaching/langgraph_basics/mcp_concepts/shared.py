"""Small, provider-neutral helpers shared by the MCP concepts notebooks.

Mirrors the shape of single_agent_architectures/shared.py and
multi_agent_architectures/shared.py -- each course subfolder keeps its own
small copy rather than a cross-folder import, matching this repo's existing
convention.
"""
import json
import subprocess
import time as _time
import urllib.request
import urllib.error
from collections.abc import Callable
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler


class Timer:
    """Wall-clock timer for a representative run. Usage: ``with Timer() as t: ...``"""

    def __enter__(self):
        self._start = _time.time()
        self.elapsed_s = None
        return self

    def __exit__(self, *exc_info):
        self.elapsed_s = _time.time() - self._start
        return False


class ScorecardCallback(BaseCallbackHandler):
    """Counts real LLM calls -- attached at the provider client level so it
    captures every call regardless of `bind_tools()` wrapping."""

    def __init__(self):
        self.call_count = 0

    def on_chat_model_start(self, serialized, messages, **kwargs):
        self.call_count += 1

    def reset(self) -> None:
        self.call_count = 0


# Illustrative per-1K-token USD rates -- not authoritative, live pricing. Only
# precise enough to keep relative cost comparisons consistent, not to
# reproduce an exact provider invoice.
MODEL_COST_PER_1K_USD = {
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "claude-sonnet-5": {"input": 0.003, "output": 0.015},
}


def estimate_cost_usd(
    call_count: int,
    model: str,
    avg_input_tokens: int = 600,
    avg_output_tokens: int = 150,
) -> float:
    """Illustrative, order-of-magnitude cost estimate for a representative run."""
    rates = MODEL_COST_PER_1K_USD.get(model, MODEL_COST_PER_1K_USD["gpt-4o-mini"])
    return call_count * (
        avg_input_tokens / 1000 * rates["input"] + avg_output_tokens / 1000 * rates["output"]
    )


def pretty(obj: Any) -> str:
    """Pretty-print an MCP result (or any JSON-ish object) for notebook output."""
    if hasattr(obj, "model_dump"):
        obj = obj.model_dump()
    try:
        return json.dumps(obj, indent=2, default=str)
    except TypeError:
        return str(obj)


def start_http_server(script_path: str, port: int, health_path: str = "/mcp") -> subprocess.Popen:
    """Launches a FastMCP server script in HTTP mode as a background process
    and waits until it responds, so a client can connect immediately after
    this returns. Caller is responsible for calling `.terminate()` when done
    (see `stop_server`) -- unlike stdio servers, an HTTP server must already
    be running before a client connects, so this notebook manages its
    lifecycle explicitly instead of relying on the client library to spawn it."""
    proc = subprocess.Popen(
        ["python3", script_path, "--http", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    url = f"http://127.0.0.1:{port}{health_path}"
    for _ in range(30):
        try:
            req = urllib.request.Request(url, method="GET")
            urllib.request.urlopen(req, timeout=1)
            break
        except urllib.error.HTTPError:
            # Any HTTP response (even a 4xx from a bare GET on the MCP
            # endpoint) means the server process is up and listening.
            break
        except Exception:
            _time.sleep(0.3)
    return proc


def stop_server(proc: subprocess.Popen) -> None:
    """Terminates a background server process started by `start_http_server`."""
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
