"""API-key auth + per-key rate limiting for the FastAPI backend.

Fixes the "zero auth" gap flagged in the production-readiness review: every
route used to be reachable by anyone who could reach the port. This adds a
required `X-API-Key` header, checked against `INCIDENT_AGENT_API_KEYS`
(config.py fails loudly at import if that's unset — no unauthenticated
fallback), and layers the per-key rate limiter from `backend/agent/budget.py`
on top so one caller can't starve others within the same process.

Deliberately a simple static-key scheme, not OAuth/JWT: this is a
single-team internal tool (per system_design/04_tools_and_authorization.md)
with no end-user-facing auth requirement documented in the brief. A
multi-tenant deployment would need real per-user identity (JWT + an
issuer), not just a shared secret — noted here rather than silently scoped
in.
"""
from __future__ import annotations

import hmac

from fastapi import Header, HTTPException

from backend.agent import budget
from backend.agent.config import API_KEYS, require_api_keys_configured

require_api_keys_configured()  # fail loudly at import time, same policy as OPENAI_API_KEY


def _matches_any_key(candidate: str) -> bool:
    # Constant-time compare against each configured key so response timing
    # doesn't leak how close a guess got to a valid key.
    return any(hmac.compare_digest(candidate, key) for key in API_KEYS)


async def verify_api_key(x_api_key: str | None = Header(default=None)) -> str:
    """FastAPI dependency: require a valid `X-API-Key` header, then apply
    that key's rate limit. Returns the validated key so route handlers can
    use it as a rate-limit/audit identity if needed. Raises 401 for a
    missing/invalid key, 429 if that key's rate limit is exceeded."""
    if not x_api_key or not _matches_any_key(x_api_key):
        raise HTTPException(status_code=401, detail="Missing or invalid API key.")

    try:
        budget.check_rate_limit(x_api_key)
    except budget.RateLimitExceededError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc

    return x_api_key
