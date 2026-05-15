from __future__ import annotations

from jottit.auth import generate_change_password_token, hash_password, verify_password


def test_hash_password_returns_argon2_string() -> None:
    out = hash_password("hunter2")
    assert out.startswith("$argon2")
    assert "hunter2" not in out


def test_hash_password_is_salted_so_repeats_differ() -> None:
    assert hash_password("hunter2") != hash_password("hunter2")


def test_verify_password_accepts_correct_password() -> None:
    h = hash_password("hunter2")
    assert verify_password("hunter2", h) is True


def test_verify_password_rejects_wrong_password() -> None:
    h = hash_password("hunter2")
    assert verify_password("nope", h) is False


def test_verify_password_rejects_malformed_hash() -> None:
    assert verify_password("hunter2", "not-an-argon2-hash") is False


def test_generate_change_password_token_is_long_and_unique() -> None:
    a = generate_change_password_token()
    b = generate_change_password_token()
    # token_urlsafe(32) is 43 chars; bound loosely for libstdlib versioning.
    assert len(a) >= 40
    assert a != b
