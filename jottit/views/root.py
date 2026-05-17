from __future__ import annotations

from flask import abort, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from sqlalchemy import text
from werkzeug.wrappers import Response

from jottit import mail, turnstile
from jottit.db import get_request_conn, get_site, get_sites_by_email, new_site


def index() -> ResponseReturnValue:
    if request.method == "POST":
        if not turnstile.verify():
            return render_template("index.html", error="Please complete the challenge."), 400
        return _create_site()
    return render_template("index.html", error=None)


def _create_site() -> Response:
    conn = get_request_conn()
    if conn is None:
        abort(500)

    content = request.form.get("content", "")
    secret_url = request.form.get("secret_url") or None
    public_url = request.form.get("public_url") or None
    partner = request.form.get("partner") or None
    scroll_pos = _safe_int(request.form.get("scroll_pos"))
    caret_pos = _safe_int(request.form.get("caret_pos"))

    site_id = new_site(
        conn,
        content=content,
        ip=request.remote_addr,
        secret_url=secret_url,
        public_url=public_url,
        partner=partner,
        scroll_pos=scroll_pos,
        caret_pos=caret_pos,
    )
    site = get_site(conn, site_id=site_id)
    assert site is not None

    if site.public_url:
        return redirect(
            url_for("page.home", site_slug=site.public_url, _external=True),
            code=303,
        )
    return redirect(url_for("secret.page_home", site_slug=site.secret_url), code=303)


def _safe_int(value: str | None) -> int:
    if not value:
        return 0
    try:
        return int(value)
    except ValueError:
        return 0


def sites() -> ResponseReturnValue:
    if request.method != "POST":
        return render_template("sites.html", sent=False, error=None)

    email = (request.form.get("email") or "").strip()
    if not email:
        return render_template("sites.html", sent=False, error=None)

    conn = get_request_conn()
    if conn is None:
        abort(500)
    rows = get_sites_by_email(conn, email=email)
    if not rows:
        return render_template(
            "sites.html", sent=False, error="Sorry, there are no sites with that email"
        )

    base = f"{request.scheme}://{request.host}"
    lines = ["Here are the Jottit sites claimed with this email:\n"]
    for row in rows:
        title = row.title or "(untitled)"
        if row.public_url:
            url = f"{request.scheme}://{row.public_url}.{request.host}/"
        else:
            url = f"{base}/{row.secret_url}/"
        lines.append(f"- {title}: {url}")
    mail.send(to=email, subject="Your Jottit sites", body="\n".join(lines) + "\n")
    return render_template("sites.html", sent=True, error=None)


def about() -> ResponseReturnValue:
    return render_template("about.html")


def help_page() -> ResponseReturnValue:
    return render_template("help.html")


def feedback() -> str:
    return f"jottit:feedback {request.method} (TODO)"


def healthz() -> tuple[str, int]:
    """Liveness + readiness probe for Fly's http_service.checks.

    Returns 200 only if the DB is reachable; Fly will keep the old machine
    routing traffic while a new one fails its health check, so a broken
    deploy doesn't take production down.
    """
    conn = get_request_conn()
    if conn is None:
        return "no db", 503
    conn.execute(text("SELECT 1"))
    return "ok", 200
