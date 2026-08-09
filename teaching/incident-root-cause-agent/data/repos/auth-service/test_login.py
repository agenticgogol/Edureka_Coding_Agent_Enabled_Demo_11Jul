"""Tests for auth-service login flow (synthetic, working code — these all
pass; auth-service is a negative-match repo in the demo)."""
from __future__ import annotations

import sys

from login import LoginError, login, register_user
from password_hashing import hash_password
from tokens import validate_token

SECRET = "test-secret"


def test_successful_login_issues_valid_token():
    digest, salt = hash_password("correct-horse-battery-staple")
    register_user("alice", digest, salt)
    token = login("alice", "correct-horse-battery-staple", SECRET)
    assert validate_token(token, SECRET)


def test_wrong_password_rejected():
    digest, salt = hash_password("hunter2")
    register_user("bob", digest, salt)
    try:
        login("bob", "wrong-password", SECRET)
        raise AssertionError("expected LoginError")
    except LoginError:
        pass


def test_unknown_user_rejected():
    try:
        login("nobody", "whatever", SECRET)
        raise AssertionError("expected LoginError")
    except LoginError:
        pass


if __name__ == "__main__":
    tests = [
        test_successful_login_issues_valid_token,
        test_wrong_password_rejected,
        test_unknown_user_rejected,
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
