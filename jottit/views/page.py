from __future__ import annotations

from flask import abort, g, jsonify, redirect, render_template, request
from flask.typing import ResponseReturnValue
from sqlalchemy import Connection, Row

from jottit import auth
from jottit.db import (
    delete_page,
    get_draft,
    get_page,
    get_request_conn,
    get_revision,
    get_revisions,
    get_revisions_count,
    new_page,
    undelete_page,
    update_page,
)
from jottit.diff import better_diff
from jottit.render import format_content
from jottit.urls import page_slug, site_root


def home(site_slug: str) -> ResponseReturnValue:
    return view(site_slug, "")


def view(site_slug: str, page_name: str) -> ResponseReturnValue:
    if g.site is None:
        abort(404)

    conn = get_request_conn()
    if conn is None:
        abort(500)

    mode = request.args.get("m", "view")
    action = _action_for(mode)
    if (response := auth.gate(action)) is not None:
        return response

    if request.method == "POST":
        if mode == "current_revision":
            return _current_revision(conn, page_name)
        return _save_edit(conn, page_name)

    if mode == "edit":
        return _render_edit_form(conn, page_name)

    if mode == "history":
        return _render_history(conn, page_name)

    if mode == "diff":
        return _render_diff(conn, page_name)

    return _render_view(conn, page_name)


def _action_for(mode: str) -> str:
    """Map a (method, mode) pair onto the auth-matrix action label."""
    if request.method == "POST":
        # current_revision is a JSON probe used by the editor JS, so it
        # logically requires the same permission as the edit it's about
        # to perform.
        return "edit"
    if mode == "edit":
        return "edit"
    # Old revisions, history listings, and diffs all expose pre-current
    # content; on public sites that's gated more tightly than the latest
    # revision. See is_action_allowed.
    if mode in ("history", "diff") or request.args.get("r") is not None:
        return "view_revision"
    return "view"


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

    rendered = format_content(revision.content, site_root=site_root())
    return render_template(
        "view_page.html",
        page_name=page_name,
        revision=revision,
        content_html=rendered,
    )


def _render_diff(conn: Connection, page_name: str) -> ResponseReturnValue:
    """Render the diff between two revisions.

    URL shapes (matches the original):
    - `?m=diff` → latest vs previous
    - `?m=diff&r=N` → revision N vs N-1
    - `?m=diff&r=A&r=B` → between A and B (ordering normalized)
    """
    page = get_page(conn, site_id=g.site.id, page_name=page_name)
    if page is None:
        return render_template("notfound.html", page_name=page_name), 404

    a_rev, b_rev = _resolve_diff_revisions(conn, page_id=page.id)
    if a_rev is None or b_rev is None:
        abort(400)

    return render_template(
        "diff.html",
        page_name=page_name,
        a=a_rev,
        b=b_rev,
        diff_html=better_diff(a_rev.content, b_rev.content),
        site_root_path=site_root(),
    )


def _resolve_diff_revisions(
    conn: Connection, *, page_id: int
) -> tuple[Row | None, Row | None]:
    """Pick the (older, newer) revisions to diff based on the `r` query params."""
    rs = request.args.getlist("r")
    if len(rs) > 2:
        return None, None
    try:
        ints = sorted({int(r) for r in rs})
    except ValueError:
        return None, None

    if not ints:
        # No params: latest vs previous.
        latest = get_revision(conn, page_id=page_id)
        if latest is None:
            return None, None
        prev = get_revision(conn, page_id=page_id, revision=max(latest.revision - 1, 1))
        return prev, latest

    if len(ints) == 1:
        n = ints[0]
        b = get_revision(conn, page_id=page_id, revision=n)
        a = get_revision(conn, page_id=page_id, revision=max(n - 1, 1))
        return a, b

    a = get_revision(conn, page_id=page_id, revision=ints[0])
    b = get_revision(conn, page_id=page_id, revision=ints[1])
    return a, b


def _render_history(conn: Connection, page_name: str) -> ResponseReturnValue:
    page = get_page(conn, site_id=g.site.id, page_name=page_name)
    if page is None:
        return render_template("notfound.html", page_name=page_name), 404

    total = get_revisions_count(conn, page_id=page.id)
    if total == 0:
        # Nothing to show — drop the user back at the page itself.
        return redirect(site_root() + page_slug(page_name), code=303)

    before = request.args.get("before", type=int)
    revisions_page = get_revisions(conn, page_id=page.id, before=before, limit=20)
    older_before = revisions_page[-1].revision if len(revisions_page) == 20 else None

    return render_template(
        "history.html",
        page_name=page_name,
        revisions=revisions_page,
        total=total,
        older_before=older_before,
        site_root_path=site_root(),
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
    return redirect(site_root() + page_slug(page_name), code=303)
