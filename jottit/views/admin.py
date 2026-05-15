from __future__ import annotations

import re

from flask import abort, current_app, g, jsonify, redirect, render_template, request
from flask.typing import ResponseReturnValue
from sqlalchemy import Connection

from jottit import auth
from jottit.db import (
    change_public_url,
    get_request_conn,
    is_public_url_available,
    set_password,
    update_site,
)
from jottit.urls import site_root

_ALLOWED_SECURITY_LEVELS = {"private", "public", "open"}
_PUBLIC_URL_RE = re.compile(r"^[a-z0-9-]+$")


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

    conn = _conn()
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


def url_available(site_slug: str) -> ResponseReturnValue:
    """JSON probe used by the change-site-address form: is this slug free?"""
    if (response := _gate_admin()) is not None:
        return response

    url = request.form.get("url", "").strip().lower()
    if not url:
        return jsonify(available=False)

    if not _PUBLIC_URL_RE.fullmatch(url):
        return jsonify(available=False)

    conn = _conn()
    return jsonify(available=is_public_url_available(conn, public_url=url))


def delete(site_slug: str) -> str:
    return f"admin:{site_slug} admin/delete {request.method} (TODO)"


def change_site_address(site_slug: str) -> ResponseReturnValue:
    if (response := _gate_admin()) is not None:
        return response

    if request.method == "GET":
        return render_template(
            "admin_change_site_address.html",
            public_url=g.site.public_url or "",
            error=None,
        )

    new_url = request.form.get("public_url", "").strip().lower()

    # No-op: same slug as before — skip the DB write and just redirect home.
    if new_url == (g.site.public_url or ""):
        return redirect(_admin_settings_url(new_url), code=303)

    conn = _conn()
    error = _validate_public_url(new_url, conn)
    if error is not None:
        return render_template(
            "admin_change_site_address.html",
            public_url=new_url,
            error=error,
        ), 400

    change_public_url(conn, site_id=g.site.id, public_url=new_url)
    return redirect(_admin_settings_url(new_url), code=303)


def _validate_public_url(url: str, conn: Connection) -> str | None:
    if not url:
        # Empty value clears the slug — site stays reachable via secret URL only.
        return None
    if not _PUBLIC_URL_RE.fullmatch(url):
        return "Site address can only contain lowercase letters, numbers, and dashes."
    if not is_public_url_available(conn, public_url=url):
        return "That site address is already taken."
    return None


def _admin_settings_url(new_public_url: str) -> str:
    """Absolute URL for /admin/settings after a public_url change.

    Goes to the new subdomain when a public_url is set, otherwise to the
    secret-URL path. Cross-subdomain redirect is required because the
    current request's host (the OLD subdomain) no longer resolves to a
    site after the DB update.
    """
    scheme = request.scheme
    domain = current_app.config["SERVER_NAME"]
    if new_public_url:
        return f"{scheme}://{new_public_url}.{domain}/admin/settings"
    return f"{scheme}://{domain}/{g.site.secret_url}/admin/settings"


def _conn() -> Connection:
    conn = get_request_conn()
    if conn is None:
        abort(500)
    return conn


def change_password(site_slug: str) -> ResponseReturnValue:
    """Change the site password while signed in.

    Distinct from the token-based recovery flow in /site/change-password —
    this path requires the current password to be supplied and re-typed.
    """
    if (response := _gate_admin()) is not None:
        return response

    if request.method == "GET":
        return render_template("admin_change_password.html", error=None)

    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")

    if not auth.verify_password(current_password, g.site.password):
        return render_template(
            "admin_change_password.html",
            error="That isn't your current password.",
        ), 401

    if not new_password:
        return render_template(
            "admin_change_password.html",
            error="Please enter a new password.",
        ), 400

    conn = _conn()
    set_password(conn, site_id=g.site.id, password_hash=auth.hash_password(new_password))
    return redirect(f"{site_root()}admin/settings", code=303)


def export(site_slug: str) -> str:
    return f"admin:{site_slug} admin/export GET (TODO)"
