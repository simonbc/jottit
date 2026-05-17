from __future__ import annotations

from urllib.parse import urlparse

from flask import abort, flash, g, redirect, render_template, request
from flask.typing import ResponseReturnValue

from jottit import auth, mail
from jottit.db import (
    claim_site,
    get_changes,
    get_request_conn,
    recover_password,
    set_change_pwd_token,
    sites,
)
from jottit.render import format_content
from jottit.urls import page_slug, site_root

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
    flash("Congratulations! You've claimed your site.", "success")
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


def forgot_password(site_slug: str) -> ResponseReturnValue:
    if g.site is None:
        abort(404)
    if g.site.password is None:
        # Nothing to recover on an unclaimed site.
        return redirect(site_root(), code=303)

    if request.method == "GET":
        return render_template("forgot_password.html", sent=False)

    conn = get_request_conn()
    if conn is None:
        abort(500)

    token = auth.generate_change_password_token()
    set_change_pwd_token(conn, site_id=g.site.id, token=token)
    _send_recovery_email(to=g.site.email, token=token)
    return render_template("forgot_password.html", sent=True)


def change_password(site_slug: str) -> ResponseReturnValue:
    if g.site is None:
        abort(404)
    if g.site.password is None:
        return redirect(site_root(), code=303)

    token = request.values.get("d", "")
    stored = g.site.change_pwd_token
    # Both `not stored` and `token != stored` collapse to "no valid token".
    # Treat them identically to avoid leaking which one failed.
    if not stored or token != stored:
        return redirect(site_root(), code=303)

    if request.method == "GET":
        return render_template("change_password.html", token=token, error=None)

    new_password = request.form.get("new_password", "")
    if not new_password:
        return render_template(
            "change_password.html",
            token=token,
            error="Please enter a new password.",
        ), 400

    conn = get_request_conn()
    if conn is None:
        abort(500)

    recover_password(conn, site_id=g.site.id, password_hash=auth.hash_password(new_password))
    auth.sign_in(g.site.id)
    return redirect(site_root(), code=303)


def _send_recovery_email(*, to: str, token: str) -> None:
    change_url = f"https://{request.host}{site_root()}site/change-password?d={token}"
    forgot_url = f"https://{request.host}{site_root()}site/forgot-password"
    mail.send(
        to=to,
        subject="Password reset for your Jottit site",
        body=(
            "Someone asked to reset the password on your Jottit site. If it "
            "wasn't you, you can ignore this email.\n\n"
            f"To set a new password, visit:\n{change_url}\n\n"
            "This link works once. If you need another, visit:\n"
            f"{forgot_url}\n"
        ),
    )


def changes(site_slug: str) -> ResponseReturnValue:
    """Site-wide activity feed: recent revisions across all pages."""
    if g.site is None:
        abort(404)
    if (response := auth.gate("view_revision")) is not None:
        return response

    conn = get_request_conn()
    if conn is None:
        abort(500)

    before = request.args.get("before", type=int)
    rows = get_changes(conn, site_id=g.site.id, before=before, limit=20)
    older_before = rows[-1].id if len(rows) == 20 else None

    return render_template(
        "changes.html",
        changes=rows,
        older_before=older_before,
        site_root_path=site_root(),
        page_slug=page_slug,
    )


def changes_rss(site_slug: str) -> ResponseReturnValue:
    """RSS 2.0 site-wide changes feed."""
    if g.site is None:
        abort(404)
    if (response := auth.gate("view")) is not None:
        return response
    items = _changes_feed_items()
    body = render_template(
        "feeds/changes.rss.xml",
        items=items,
        site_title=g.site.title or g.site.public_url or g.site.secret_url,
        feed_url=_absolute_url("site/changes.rss"),
        site_url=_absolute_url(""),
    )
    return body, 200, {"Content-Type": "application/rss+xml; charset=utf-8"}


def changes_json(site_slug: str) -> ResponseReturnValue:
    """JSON Feed (jsonfeed.org) site-wide changes feed."""
    if g.site is None:
        abort(404)
    if (response := auth.gate("view")) is not None:
        return response
    items = _changes_feed_items()
    payload = {
        "version": "https://jsonfeed.org/version/1.1",
        "title": (g.site.title or g.site.public_url or g.site.secret_url) + " — changes",
        "home_page_url": _absolute_url(""),
        "feed_url": _absolute_url("site/changes.json"),
        "items": [
            {
                "id": item["url"],
                "url": item["url"],
                "title": item["title"],
                "content_html": item["content_html"],
                "content_text": item["content_markdown"],
                "date_published": item["created_iso"],
            }
            for item in items
        ],
    }
    from flask import jsonify

    response = jsonify(payload)
    response.headers["Content-Type"] = "application/feed+json"
    return response


def _changes_feed_items() -> list[dict[str, object]]:
    """Render every recent revision into the shape both feed formats want.

    Each entry carries the page content as both rendered HTML (the
    description / content_html) and raw markdown (source:markdown /
    content_text). Wikilinks are resolved against the absolute site root
    so they survive being read in an external reader.
    """
    rows = _recent_changes()
    absolute_root = _absolute_url("")
    items: list[dict[str, object]] = []
    for c in rows:
        items.append(
            {
                "url": _absolute_url(f"{page_slug(c.page_name)}?r={c.revision}"),
                "title": (c.page_name or "Home") + f" — revision {c.revision}",
                "created_rfc822": c.created.strftime("%a, %d %b %Y %H:%M:%S GMT"),
                "created_iso": c.created.isoformat() + "Z",
                "content_markdown": c.content,
                "content_html": format_content(c.content, site_root=absolute_root),
            }
        )
    return items


def _recent_changes():
    conn = get_request_conn()
    if conn is None:
        abort(500)
    return get_changes(conn, site_id=g.site.id, limit=20)


def _absolute_url(path: str) -> str:
    """Build an absolute URL inside this site for a feed entry."""
    return f"{request.scheme}://{request.host}{site_root()}{path}"


def hide_primer(site_slug: str) -> ResponseReturnValue:
    if g.site is None:
        abort(404)
    conn = get_request_conn()
    if conn is None:
        abort(500)
    conn.execute(sites.update().where(sites.c.id == g.site.id).values(show_primer=False))
    return redirect(site_root(), code=303)
