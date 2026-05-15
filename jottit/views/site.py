from __future__ import annotations

from urllib.parse import urlparse

from flask import abort, g, redirect, render_template, request
from flask.typing import ResponseReturnValue

from jottit import auth, mail
from jottit.db import claim_site, get_request_conn
from jottit.urls import site_root

_ALLOWED_SECURITY_LEVELS = {"private", "public", "open"}


def claim(site_slug: str) -> ResponseReturnValue:
    if g.site is None:
        abort(404)
    if g.site.password is not None:
        # Already claimed — claim is one-shot, send the visitor home.
        return redirect(site_root(), code=303)

    if request.method == "GET":
        return render_template(
            "claim_site.html",
            password="",
            email="",
            security="private",
            error=None,
        )

    password = request.form.get("password", "")
    email = request.form.get("email", "")
    security = request.form.get("security", "private")

    error = _validate_claim(password=password, email=email, security=security)
    if error is not None:
        return render_template(
            "claim_site.html",
            password=password,
            email=email,
            security=security,
            error=error,
        ), 400

    conn = get_request_conn()
    if conn is None:
        abort(500)

    claim_site(
        conn,
        site_id=g.site.id,
        password_hash=auth.hash_password(password),
        email=email,
        security=security,
    )
    auth.sign_in(g.site.id)
    _send_welcome_email(to=email)
    return redirect(site_root(), code=303)


def _validate_claim(*, password: str, email: str, security: str) -> str | None:
    if not password:
        return "Please choose a password."
    if not email or "@" not in email:
        return "Please enter a valid email address."
    if security not in _ALLOWED_SECURITY_LEVELS:
        return "Pick a valid security level."
    return None


def _send_welcome_email(*, to: str) -> None:
    mail.send(
        to=to,
        subject="You claimed your Jottit site",
        body=(
            "Thanks for claiming your site at Jottit. You can sign back in "
            "any time at https://"
            f"{request.host}{site_root()}site/signin — and recover your "
            f"password at https://{request.host}{site_root()}site/forgot-password.\n"
        ),
    )


def signin(site_slug: str) -> ResponseReturnValue:
    if g.site is None:
        abort(404)
    # An unclaimed site has no password to compare against — sign-in is a no-op
    # there; send them home so they can claim instead.
    if g.site.password is None:
        return redirect(site_root(), code=303)

    return_to = _safe_return_to(request.values.get("return_to", ""))

    if request.method == "GET":
        return render_template(
            "signin.html",
            return_to=return_to,
            error=None,
        )

    password = request.form.get("password", "")
    if not auth.verify_password(password, g.site.password):
        return render_template(
            "signin.html",
            return_to=return_to,
            error="That password doesn't match.",
        ), 401

    auth.sign_in(g.site.id)
    return redirect(site_root() + return_to.lstrip("/"), code=303)


def signout(site_slug: str) -> ResponseReturnValue:
    if g.site is not None:
        auth.sign_out(g.site.id)
    return_to = _safe_return_to(request.form.get("return_to", ""))
    return redirect(site_root() + return_to.lstrip("/"), code=303)


def _safe_return_to(value: str) -> str:
    """Strip any scheme/host off a `return_to` parameter to block open redirects.

    Only same-site relative paths survive — `//evil.com/` becomes `""`, and
    so does `https://evil.com/`. The leading `/` is also stripped so the
    caller can concatenate with `site_root()` without doubling it up.
    """
    if not value:
        return ""
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc:
        return ""
    # `//foo` parses as netloc-only on some Python versions; belt-and-braces.
    if value.startswith("//"):
        return ""
    return value.lstrip("/")


def forgot_password(site_slug: str) -> str:
    return f"site:{site_slug} site/forgot-password {request.method} (TODO)"


def change_password(site_slug: str) -> str:
    return f"site:{site_slug} site/change-password {request.method} (TODO)"


def changes(site_slug: str) -> str:
    return f"site:{site_slug} site/changes GET (TODO)"


def changes_atom(site_slug: str) -> str:
    return f"site:{site_slug} site/changes.atom GET (TODO)"


def hide_primer(site_slug: str) -> str:
    return f"site:{site_slug} site/hide-primer POST (TODO)"
