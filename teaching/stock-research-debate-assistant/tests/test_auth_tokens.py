"""Unit tests for server-issued session-token auth (replaces free-text
`user_key`): `backend/agent/memory.py`'s `create_session`/`resolve_user_key`,
and `backend/api/routes.py`'s `_authenticate` dependency.

Uses a real temporary SQLite file (not a mock) — `memory.py`'s functions
are plain deterministic DB reads/writes, no LLM/network call involved, so
these are safe to run without spending anything.
"""
from __future__ import annotations

import os
import tempfile
import unittest

from backend.agent import memory
from backend.agent.config import config


class SessionTokenMemoryTests(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._tmp_db_path = os.path.join(self._tmp_dir.name, "test_memory.db")
        # `config` is a frozen dataclass singleton; bypass immutability just
        # for the test so `memory._connect()` (which reads
        # `config.memory_db_path`) points at an isolated temp DB instead of
        # the real `backend/data/memory.db`.
        self._original_db_path = config.memory_db_path
        object.__setattr__(config, "memory_db_path", self._tmp_db_path)

    def tearDown(self):
        object.__setattr__(config, "memory_db_path", self._original_db_path)
        self._tmp_dir.cleanup()

    def test_create_session_returns_token_and_user_key(self):
        token, user_key = memory.create_session()
        self.assertTrue(token)
        self.assertTrue(user_key)

    def test_create_session_tokens_are_unique_and_unguessable_length(self):
        token1, _ = memory.create_session()
        token2, _ = memory.create_session()
        self.assertNotEqual(token1, token2)
        # secrets.token_urlsafe(32) -> ~43 base64url chars; assert it's not
        # some short/guessable value.
        self.assertGreater(len(token1), 30)

    def test_resolve_user_key_returns_the_mapped_user_key(self):
        token, user_key = memory.create_session()
        self.assertEqual(memory.resolve_user_key(token), user_key)

    def test_resolve_user_key_returns_none_for_unknown_token(self):
        self.assertIsNone(memory.resolve_user_key("this-token-was-never-issued"))

    def test_resolve_user_key_returns_none_for_empty_token(self):
        self.assertIsNone(memory.resolve_user_key(""))

    def test_two_sessions_get_distinct_user_keys(self):
        _, user_key1 = memory.create_session()
        _, user_key2 = memory.create_session()
        self.assertNotEqual(user_key1, user_key2)

    def test_create_session_can_reuse_an_explicit_user_key(self):
        token, user_key = memory.create_session(user_key="explicit-user")
        self.assertEqual(user_key, "explicit-user")
        self.assertEqual(memory.resolve_user_key(token), "explicit-user")


class AuthenticateDependencyTests(unittest.TestCase):
    """`routes._authenticate` — the FastAPI dependency every protected
    endpoint calls. Tested directly (not via a live HTTP request) since it
    has no LLM/network dependency."""

    def setUp(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._tmp_db_path = os.path.join(self._tmp_dir.name, "test_memory.db")
        self._original_db_path = config.memory_db_path
        object.__setattr__(config, "memory_db_path", self._tmp_db_path)

    def tearDown(self):
        object.__setattr__(config, "memory_db_path", self._original_db_path)
        self._tmp_dir.cleanup()

    def test_valid_token_resolves_to_user_key(self):
        from backend.api.routes import _authenticate

        token, user_key = memory.create_session()
        self.assertEqual(_authenticate(token), user_key)

    def test_missing_token_raises_401(self):
        from fastapi import HTTPException

        from backend.api.routes import _authenticate

        with self.assertRaises(HTTPException) as ctx:
            _authenticate(None)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_empty_token_raises_401(self):
        from fastapi import HTTPException

        from backend.api.routes import _authenticate

        with self.assertRaises(HTTPException) as ctx:
            _authenticate("")
        self.assertEqual(ctx.exception.status_code, 401)

    def test_unknown_token_raises_401(self):
        from fastapi import HTTPException

        from backend.api.routes import _authenticate

        with self.assertRaises(HTTPException) as ctx:
            _authenticate("not-a-real-token")
        self.assertEqual(ctx.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()
