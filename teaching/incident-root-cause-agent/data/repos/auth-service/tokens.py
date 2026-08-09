"""Token issuance/validation helpers for auth-service (synthetic, working
code — used as a negative-match repo and for the infra-issue scenario,
where the root cause is outside application code)."""
from __future__ import annotations

import hashlib
import time

TOKEN_TTL_SECONDS = 3600


def _sign(payload: str, secret: str) -> str:
    return hashlib.sha256(f"{payload}:{secret}".encode()).hexdigest()


def issue_token(user_id: str, secret: str) -> dict:
    issued_at = int(time.time())
    expires_at = issued_at + TOKEN_TTL_SECONDS
    payload = f"{user_id}|{issued_at}|{expires_at}"
    signature = _sign(payload, secret)
    return {"payload": payload, "signature": signature}


def validate_token(token: dict, secret: str) -> bool:
    expected_signature = _sign(token["payload"], secret)
    if expected_signature != token["signature"]:
        return False
    _, _, expires_at = token["payload"].split("|")
    return int(expires_at) >= int(time.time())
