from __future__ import annotations

from dataclasses import dataclass

from flask import Flask

from jottit.auth import (
    generate_change_password_token,
    hash_password,
    is_action_allowed,
    is_signed_in_to,
    sign_in,
    sign_out,
    verify_password,
)


@dataclass
class _FakeSite:
    id: int
    password: str | None = None
    security: str = "private"


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


# ---- session helpers ----


def test_sign_in_adds_site_to_session(app: Flask) -> None:
    with app.test_request_context("/"):
        assert is_signed_in_to(42) is False
        sign_in(42)
        assert is_signed_in_to(42) is True


def test_sign_in_is_idempotent(app: Flask) -> None:
    from flask import session

    with app.test_request_context("/"):
        sign_in(42)
        sign_in(42)
        assert session["signed_in_sites"] == [42]


def test_sign_in_supports_multiple_sites(app: Flask) -> None:
    with app.test_request_context("/"):
        sign_in(1)
        sign_in(2)
        assert is_signed_in_to(1)
        assert is_signed_in_to(2)


def test_sign_out_removes_one_site_only(app: Flask) -> None:
    with app.test_request_context("/"):
        sign_in(1)
        sign_in(2)
        sign_out(1)
        assert is_signed_in_to(1) is False
        assert is_signed_in_to(2) is True


def test_sign_out_unknown_site_is_noop(app: Flask) -> None:
    with app.test_request_context("/"):
        sign_out(99)  # should not raise
        assert is_signed_in_to(99) is False


# ---- permission matrix ----


def test_no_site_denies_everything(app: Flask) -> None:
    with app.test_request_context("/"):
        assert is_action_allowed(site=None, action="view") is False
        assert is_action_allowed(site=None, action="edit") is False


def test_unclaimed_site_allows_everything(app: Flask) -> None:
    site = _FakeSite(id=1, password=None, security="private")
    with app.test_request_context("/"):
        assert is_action_allowed(site=site, action="view") is True
        assert is_action_allowed(site=site, action="edit") is True
        assert is_action_allowed(site=site, action="admin") is True


def test_signed_in_user_can_do_anything(app: Flask) -> None:
    site = _FakeSite(id=1, password="$argon2id$x", security="private")
    with app.test_request_context("/"):
        sign_in(1)
        assert is_action_allowed(site=site, action="view") is True
        assert is_action_allowed(site=site, action="edit") is True
        assert is_action_allowed(site=site, action="admin") is True


def test_private_site_denies_signed_out_visitors(app: Flask) -> None:
    site = _FakeSite(id=1, password="$argon2id$x", security="private")
    with app.test_request_context("/"):
        assert is_action_allowed(site=site, action="view") is False
        assert is_action_allowed(site=site, action="edit") is False
        assert is_action_allowed(site=site, action="admin") is False


def test_public_site_allows_view_but_blocks_edit_and_admin(app: Flask) -> None:
    site = _FakeSite(id=1, password="$argon2id$x", security="public")
    with app.test_request_context("/"):
        assert is_action_allowed(site=site, action="view") is True
        assert is_action_allowed(site=site, action="view_revision") is False
        assert is_action_allowed(site=site, action="edit") is False
        assert is_action_allowed(site=site, action="admin") is False


def test_open_site_allows_view_and_edit_but_blocks_admin(app: Flask) -> None:
    site = _FakeSite(id=1, password="$argon2id$x", security="open")
    with app.test_request_context("/"):
        assert is_action_allowed(site=site, action="view") is True
        assert is_action_allowed(site=site, action="edit") is True
        assert is_action_allowed(site=site, action="admin") is False


def test_session_is_scoped_per_site(app: Flask) -> None:
    site_a = _FakeSite(id=1, password="$argon2id$x", security="private")
    site_b = _FakeSite(id=2, password="$argon2id$x", security="private")
    with app.test_request_context("/"):
        sign_in(1)
        assert is_action_allowed(site=site_a, action="admin") is True
        assert is_action_allowed(site=site_b, action="admin") is False
