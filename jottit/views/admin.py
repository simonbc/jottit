from __future__ import annotations

from flask import abort, g, redirect, render_template, request
from flask.typing import ResponseReturnValue

from jottit import auth
from jottit.db import get_request_conn, update_site
from jottit.urls import site_root

_ALLOWED_SECURITY_LEVELS = {"private", "public", "open"}


def settings(site_slug: str) -> ResponseReturnValue:
    if (response := _gate_admin()) is not None:
        return response

    if request.method == "GET":
        return render_template(
            "admin_settings.html",
            title=g.site.title or "",
            subtitle=g.site.subtitle or "",
            email=g.site.email or "",
            security=g.site.security or "private",
            public_url=g.site.public_url or "",
            error=None,
        )

    title = request.form.get("title", "")
    subtitle = request.form.get("subtitle", "")
    email = request.form.get("email", "")
    security = request.form.get("security", g.site.security or "private")

    error = _validate_settings(email=email, security=security)
    if error is not None:
        return render_template(
            "admin_settings.html",
            title=title,
            subtitle=subtitle,
            email=email,
            security=security,
            public_url=g.site.public_url or "",
            error=error,
        ), 400

    conn = get_request_conn()
    if conn is None:
        abort(500)
    update_site(
        conn,
        site_id=g.site.id,
        title=title,
        subtitle=subtitle,
        email=email,
        security=security,
    )
    return redirect(site_root(), code=303)


def _validate_settings(*, email: str, security: str) -> str | None:
    if email and "@" not in email:
        return "Please enter a valid email address."
    if security not in _ALLOWED_SECURITY_LEVELS:
        return "Pick a valid security level."
    return None


def _gate_admin() -> ResponseReturnValue | None:
    if g.site is None:
        abort(404)
    return auth.gate("admin")


def design(site_slug: str) -> str:
    return f"admin:{site_slug} admin/design {request.method} (TODO)"


def url_available(site_slug: str) -> str:
    return f"admin:{site_slug} admin/url-available POST (TODO)"


def delete(site_slug: str) -> str:
    return f"admin:{site_slug} admin/delete {request.method} (TODO)"


def change_site_address(site_slug: str) -> str:
    return f"admin:{site_slug} admin/change-site-address {request.method} (TODO)"


def change_password(site_slug: str) -> str:
    return f"admin:{site_slug} admin/change-password {request.method} (TODO)"


def export(site_slug: str) -> str:
    return f"admin:{site_slug} admin/export GET (TODO)"
