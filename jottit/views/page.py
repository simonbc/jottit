from __future__ import annotations

from flask import abort, g, jsonify, redirect, render_template, request
from flask.typing import ResponseReturnValue
from sqlalchemy import Connection

from jottit.db import (
    delete_page,
    get_draft,
    get_page,
    get_request_conn,
    get_revision,
    new_page,
    undelete_page,
    update_page,
)
from jottit.render import format_content, page_slug


def home(site_slug: str) -> ResponseReturnValue:
    return view(site_slug, "")


def view(site_slug: str, page_name: str) -> ResponseReturnValue:
    if g.site is None:
        abort(404)

    conn = get_request_conn()
    if conn is None:
        abort(500)

    mode = request.args.get("m", "view")

    if request.method == "POST":
        if mode == "current_revision":
            return _current_revision(conn, page_name)
        return _save_edit(conn, page_name)

    if mode == "edit":
        return _render_edit_form(conn, page_name)

    return _render_view(conn, page_name)


def _render_view(conn: Connection, page_name: str) -> ResponseReturnValue:
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


def _render_edit_form(conn: Connection, page_name: str) -> ResponseReturnValue:
    page = get_page(conn, site_id=g.site.id, page_name=page_name)
    if page is None:
        return render_template(
            "edit_page.html",
            page_name=page_name,
            content="",
            current_revision=0,
        )

    revision = get_revision(conn, page_id=page.id)
    draft = get_draft(conn, page_id=page.id)
    # A draft (autosaved from a prior edit session) takes precedence — that's
    # the user's in-flight work that hasn't been published yet.
    content = draft.content if draft is not None else (revision.content if revision else "")
    return render_template(
        "edit_page.html",
        page_name=page_name,
        content=content,
        current_revision=revision.revision if revision else 0,
    )


def _current_revision(conn: Connection, page_name: str) -> ResponseReturnValue:
    """JSON endpoint used by the editor to poll for concurrent edits."""
    page = get_page(conn, site_id=g.site.id, page_name=page_name)
    if page is None:
        return jsonify(revision=None)
    revision = get_revision(conn, page_id=page.id)
    return jsonify(revision=revision.revision if revision is not None else None)


def _save_edit(conn: Connection, page_name: str) -> ResponseReturnValue:
    content = _normalize_line_endings(request.form.get("content", ""))
    scroll_pos = request.form.get("scroll_pos", default=0, type=int)
    caret_pos = request.form.get("caret_pos", default=0, type=int)
    ip = request.remote_addr

    page = get_page(conn, site_id=g.site.id, page_name=page_name)

    # The Delete button submits the form with `delete=1`. Empty page_name
    # is the home page, which can't be deleted.
    if request.form.get("delete") and page_name:
        if page is not None:
            delete_page(conn, page_id=page.id, ip=ip)
        return _redirect_to(page_name)

    if page is None:
        new_page(
            conn,
            site_id=g.site.id,
            name=page_name,
            content=content,
            ip=ip,
            scroll_pos=scroll_pos,
            caret_pos=caret_pos,
        )
    else:
        update_page(
            conn,
            page_id=page.id,
            content=content,
            scroll_pos=scroll_pos,
            caret_pos=caret_pos,
            ip=ip,
        )
        if page.deleted:
            undelete_page(conn, page_id=page.id, name=page_name)

    return _redirect_to(page_name)


def _normalize_line_endings(text: str) -> str:
    # Mirrors the original `re.sub(r'(\r\n|\r)', '\n', content)`: browsers
    # post `\r\n` from <textarea>, but stored content uses `\n`.
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _redirect_to(page_name: str) -> ResponseReturnValue:
    return redirect(_site_root() + page_slug(page_name), code=303)


def _site_root() -> str:
    if request.blueprint == "secret":
        return f"/{g.site_slug}/"
    return "/"
