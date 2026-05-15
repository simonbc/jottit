from __future__ import annotations

from flask import abort, g, render_template, request
from flask.typing import ResponseReturnValue

from jottit.db import get_page, get_request_conn, get_revision
from jottit.render import format_content


def home(site_slug: str) -> ResponseReturnValue:
    return view(site_slug, "")


def view(site_slug: str, page_name: str) -> ResponseReturnValue:
    if g.site is None:
        abort(404)

    conn = get_request_conn()
    if conn is None:
        abort(500)

    page = get_page(conn, site_id=g.site.id, page_name=page_name)
    if page is None:
        return render_template("notfound.html", page_name=page_name), 404

    requested_revision = request.args.get("r", type=int)
    if page.deleted and requested_revision is None:
        return render_template("deleted.html", page_name=page_name), 410

    revision = get_revision(conn, page_id=page.id, revision=requested_revision)
    if revision is None:
        abort(404)

    rendered = format_content(revision.content, site_root=_site_root())
    return render_template(
        "view_page.html",
        page_name=page_name,
        revision=revision,
        content_html=rendered,
    )


def _site_root() -> str:
    if request.blueprint == "secret":
        return f"/{g.site_slug}/"
    return "/"
