"""Code eval for stale-root-cause-reuse: flags a code-issue diagnosis that
asserts the checkout-service cart-total integer-overflow bug (an
'overflow'/'wraparound'/'16-bit' root cause targeting cart.py) even though
the actual file on disk contains no `_wrap_16bit(` call anywhere — the bug
was already fixed in an earlier session, so any root cause claiming it is
still active is reasserting a stale fact rather than one re-derived from the
file the agent actually read (see evals/taxonomy.yaml)."""

import re
from pathlib import Path

from evallib.schema import Trace

_OVERFLOW_KEYWORDS = re.compile(r"overflow|wrap.?around|16.?bit", re.IGNORECASE)

# Resolved relative to the project root (evals/../data/...), matching how
# every other path in this project's config/tools is anchored.
_CART_PY_PATH = Path(__file__).resolve().parents[2] / "data" / "repos" / "checkout-service" / "cart.py"


def _current_cart_py_has_active_overflow_bug() -> bool:
    """True if cart.py on disk still actually calls _wrap_16bit (i.e. the
    seeded bug is still present, so an overflow root cause would be valid)."""
    if not _CART_PY_PATH.exists():
        # Fixture missing entirely — can't confirm the bug is gone, so don't
        # flag a false positive.
        return True
    return "_wrap_16bit(" in _CART_PY_PATH.read_text()


def check_stale_root_cause_reuse(trace: Trace) -> bool:
    """Returns True if the trace PASSES (i.e. this failure mode did NOT occur)."""
    raw = trace.metadata.get("raw_result", {})
    if raw.get("classification") != "code-issue":
        return True  # not a code-issue diagnosis; not applicable
    if raw.get("identified_repo") != "checkout-service" or raw.get("identified_file") != "cart.py":
        return True  # not targeting the file this bug story is about; not applicable

    root_cause = raw.get("root_cause") or ""
    if not _OVERFLOW_KEYWORDS.search(root_cause):
        return True  # doesn't assert an overflow/wraparound story at all

    # Root cause asserts an active overflow bug in cart.py — only a real
    # failure if that bug doesn't actually exist in the file anymore.
    return _current_cart_py_has_active_overflow_bug()


def test_stale_root_cause_reuse_examples() -> None:
    from evallib.jsonl import read_jsonl

    traces = {t.query_id: t for t in read_jsonl(Trace, Path("evals/traces.jsonl"))}

    # Every member of stale-root-cause-reuse in taxonomy.yaml must FAIL (return False).
    for query_id in ("t-0000", "t-0001", "t-0009", "t-0015", "t-0016", "t-0017"):
        assert check_stale_root_cause_reuse(traces[query_id]) is False, query_id

    # A code-issue diagnosis on an unrelated file/repo must PASS.
    assert check_stale_root_cause_reuse(traces["t-0006"]) is True  # rate_limit.py, not cart.py
    assert check_stale_root_cause_reuse(traces["t-0003"]) is True  # templates.py, not cart.py
