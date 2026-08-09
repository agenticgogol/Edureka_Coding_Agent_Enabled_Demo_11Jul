"""Tests for notifications-service (synthetic, working code — these all
pass; notifications-service is a negative-match repo in the demo)."""
from __future__ import annotations

import sys

from dispatcher import SENT_LOG, dispatch
from retry_policy import backoff_delay, should_retry
from templates import UnknownTemplateError, render_template


def test_dispatch_renders_template_and_logs():
    SENT_LOG.clear()
    record = dispatch("email", "user@example.com", "order_confirmed", name="Alice", order_id="42", total="19.99")
    assert "Alice" in record["body"]
    assert "42" in record["body"]
    assert len(SENT_LOG) == 1


def test_unknown_template_raises():
    try:
        render_template("does_not_exist")
        raise AssertionError("expected UnknownTemplateError")
    except UnknownTemplateError:
        pass


def test_backoff_and_retry_policy():
    assert backoff_delay(1) == 2
    assert backoff_delay(2) == 4
    assert should_retry(1) is True
    assert should_retry(3) is False


if __name__ == "__main__":
    tests = [
        test_dispatch_renders_template_and_logs,
        test_unknown_template_raises,
        test_backoff_and_retry_policy,
    ]
    failures = 0
    for t in tests:
        try:
            t()
            print(f"PASS: {t.__name__}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL: {t.__name__}: {e}")
    if failures:
        print(f"\n{failures}/{len(tests)} tests failed")
        sys.exit(1)
    print(f"\nAll {len(tests)} tests passed")
