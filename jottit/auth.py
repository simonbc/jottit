from __future__ import annotations

import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Argon2id hash of a site password, suitable for storing in `sites.password`."""
    return _hasher.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    """Return True if `password` matches `stored_hash`, False otherwise.

    Argon2's `verify` raises on mismatch; this wrapper swallows the
    expected exceptions so callers can just branch on the bool.
    """
    try:
        _hasher.verify(stored_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False
    return True


def generate_change_password_token() -> str:
    """One-time URL-safe token emailed for the password-reset flow."""
    return secrets.token_urlsafe(32)
