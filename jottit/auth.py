from __future__ import annotations

import secrets
from typing import Any
from urllib.parse import quote

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from flask import abort, g, redirect, request, session
from flask.typing import ResponseReturnValue

from jottit.urls import site_root

_hasher = PasswordHasher()

_SESSION_KEY = "signed_in_sites"


# ---- Password hashing ----


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


# ---- Multi-site session state ----


def sign_in(site_id: int, *, remember: bool = False) -> None:
    """Mark the current visitor as signed in to `site_id`.

    A single Flask cookie holds the list of all sites the visitor is
    currently signed in to — so going from site A to site B doesn't sign
    you out of A. When `remember` is True, mark the session as permanent
    so the cookie outlives the browser session (lifetime is governed by
    PERMANENT_SESSION_LIFETIME on the Flask app).
    """
    signed_in = _signed_in_sites()
    if site_id not in signed_in:
        session[_SESSION_KEY] = [*signed_in, site_id]
    if remember:
        session.permanent = True


def sign_out(site_id: int) -> None:
    signed_in = _signed_in_sites()
    if site_id in signed_in:
        session[_SESSION_KEY] = [s for s in signed_in if s != site_id]


def is_signed_in_to(site_id: int) -> bool:
    return site_id in _signed_in_sites()


def _signed_in_sites() -> list[int]:
    return list(session.get(_SESSION_KEY, []))


# ---- Permission matrix ----


def is_action_allowed(*, site: Any, action: str) -> bool:
    """Return True if the current visitor can perform `action` on `site`.

    Actions: "view" (read latest revision), "view_revision" (read an old
    revision), "edit" (write a page, including draft endpoints), "admin"
    (settings/design/delete/export/change-password while signed in).

    Mirrors the matrix from the 2007 auth module:
    - unclaimed sites are wide open
    - private sites (the default) require a signed-in user for everything
    - public sites expose the latest revision but lock down history / edits
    - open sites expose view + edit but still gate admin behind a login
    """
    if site is None:
        return False
    if site.password is None:
        return True

    if is_signed_in_to(site.id):
        return True

    security = site.security or "private"
    if security == "open":
        return action != "admin"
    if security == "public":
        return action == "view"
    return False


def gate(action: str) -> ResponseReturnValue | None:
    """Enforce `action` on `g.site` for the current request.

    Returns `None` when the visitor may proceed; otherwise returns a
    Response the caller should return immediately:
    - GETs that need a login redirect to /site/signin with `return_to`
      preserved so the visitor lands back where they were.
    - POSTs (or anything other than GET) get a 401 — they're typically
      JSON/AJAX endpoints where a redirect chain doesn't help.
    """
    if is_action_allowed(site=g.site, action=action):
        return None
    if request.method == "GET":
        rel = _current_path_relative_to_site()
        return redirect(
            f"{site_root()}site/signin?return_to={quote(rel, safe='/?=&')}",
            code=303,
        )
    abort(401)


def _current_path_relative_to_site() -> str:
    """The current request path+query stripped of the site_root prefix.

    Used to build a `return_to` value that, after sign-in, gets
    concatenated back onto site_root() — so the same physical URL works
    for both subdomain and secret-URL sites.
    """
    path = request.path
    root = site_root()
    relative = path[len(root) :] if path.startswith(root) else path.lstrip("/")
    query = request.query_string.decode("utf-8") if request.query_string else ""
    return f"{relative}?{query}" if query else relative
