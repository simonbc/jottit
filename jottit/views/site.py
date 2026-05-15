from __future__ import annotations

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


def signin(site_slug: str) -> str:
    return f"site:{site_slug} site/signin {request.method} (TODO)"


def signout(site_slug: str) -> str:
    return f"site:{site_slug} site/signout POST (TODO)"


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
