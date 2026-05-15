from __future__ import annotations

from flask import abort, g, jsonify, request
from flask.typing import ResponseReturnValue

from jottit.db import (
    delete_draft,
    get_page,
    get_request_conn,
    get_revision,
    new_draft,
    update_caret_pos,
)


def save(site_slug: str) -> ResponseReturnValue:
    """Autosave the editor's current textarea content as a draft."""
    page = _resolve_page()
    if page is None:
        return "", 204

    content = request.form.get("content", "")
    new_draft(_conn(), page_id=page.id, content=content)
    return "", 204


def cancel(site_slug: str) -> ResponseReturnValue:
    """Discard the current draft and persist the latest caret/scroll position."""
    page = _resolve_page()
    if page is None:
        return "", 204

    conn = _conn()
    scroll_pos = request.form.get("scroll_pos", default=0, type=int)
    caret_pos = request.form.get("caret_pos", default=0, type=int)
    update_caret_pos(conn, page_id=page.id, scroll_pos=scroll_pos, caret_pos=caret_pos)
    delete_draft(conn, page_id=page.id)
    return "", 204


def recover_live_version(site_slug: str) -> ResponseReturnValue:
    """Drop the draft and return the latest saved revision's content as JSON.

    The editor JS uses this when the user clicks "Revert to saved version":
    server clears the draft, sends back the live content, the textarea
    re-populates from it.
    """
    page = _resolve_page()
    if page is None:
        return jsonify(content="")

    conn = _conn()
    revision = get_revision(conn, page_id=page.id)
    delete_draft(conn, page_id=page.id)
    return jsonify(content=revision.content if revision is not None else "")


def _conn():
    conn = get_request_conn()
    if conn is None:
        abort(500)
    return conn


def _resolve_page():
    if g.site is None:
        abort(404)
    page_name = request.form.get("page_name", "")
    return get_page(_conn(), site_id=g.site.id, page_name=page_name)
