"""Login flow for auth-service (synthetic, working code)."""
from __future__ import annotations

from password_hashing import verify_password
from tokens import issue_token

# Synthetic in-memory user store: user_id -> (password_digest, salt)
USERS: dict[str, tuple[str, str]] = {}


class LoginError(Exception):
    pass


def register_user(user_id: str, digest: str, salt: str) -> None:
    USERS[user_id] = (digest, salt)


def login(user_id: str, password: str, secret: str) -> dict:
    if user_id not in USERS:
        raise LoginError("unknown user")
    digest, salt = USERS[user_id]
    if not verify_password(password, digest, salt):
        raise LoginError("invalid credentials")
    return issue_token(user_id, secret)
