from __future__ import annotations

from flask import abort, g, jsonify, make_response, redirect, render_template, request
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
    new_revision,
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

    # No-JS fallback for the sidebar's "Create a new page" form: a GET
    # of `/<slug>/?m=edit&name=Foo` lands here on the home page; redirect
    # to `/<slug>/Foo?m=edit` so the user actually edits the new page.
    if mode == "edit" and not page_name and (new_name := request.args.get("name", "").strip()):
        return redirect(f"{site_root()}{page_slug(new_name)}?m=edit", code=303)

    action = _action_for(mode)
    if (response := auth.gate(action)) is not None:
        return response

    if request.method == "POST":
        if mode == "current_revision":
            return _current_revision(conn, page_name)
        if mode == "revert":
            return _revert(conn, page_name)
        if mode == "undelete":
            return _undelete(conn, page_name)
        return _save_edit(conn, page_name)

    if mode == "edit":
        return _render_edit_form(conn, page_name)

    if mode == "history":
        return _render_history(conn, page_name)

    if mode == "history_rss":
        return _render_history_rss(conn, page_name)

    if mode == "history_json":
        return _render_history_json(conn, page_name)

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
    # RSS / JSON Feed readers don't typically auth, so feeds use the same
    # loose "view" check public sites use for the latest revision.
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

    latest = get_revision(conn, page_id=page.id)
    rendered = format_content(revision.content, site_root=site_root())
    is_revision_view = requested_revision is not None
    revisions_list = (
        get_revisions(conn, page_id=page.id, limit=100) if is_revision_view else []
    )
    return render_template(
        "view_page.html",
        page_name=page_name,
        revision=revision,
        latest_revision_number=latest.revision if latest is not None else revision.revision,
        is_revision_view=is_revision_view,
        revisions=revisions_list,
        content_html=rendered,
    )


def _render_history_rss(conn: Connection, page_name: str) -> ResponseReturnValue:
    page = get_page(conn, site_id=g.site.id, page_name=page_name)
    if page is None:
        abort(404)
    revisions_page = get_revisions(conn, page_id=page.id, limit=20)
    items = [_feed_item(r, page_name=page_name) for r in revisions_page]
    body = render_template(
        "feeds/history.rss.xml",
        items=items,
        page_url=_page_absolute_url(page_name),
        feed_url=_page_absolute_url(page_name, "m=history_rss"),
        site_title=(g.site.title or g.site.public_url or g.site.secret_url),
        page_label=page_name or "Home",
    )
    response = make_response(body)
    response.headers["Content-Type"] = "application/rss+xml; charset=utf-8"
    return response


def _render_history_json(conn: Connection, page_name: str) -> ResponseReturnValue:
    page = get_page(conn, site_id=g.site.id, page_name=page_name)
    if page is None:
        abort(404)
    revisions_page = get_revisions(conn, page_id=page.id, limit=20)
    items = [_feed_item(r, page_name=page_name) for r in revisions_page]
    payload = {
        "version": "https://jsonfeed.org/version/1.1",
        "title": (g.site.title or g.site.public_url or g.site.secret_url)
        + f" — {page_name or 'Home'} history",
        "home_page_url": _page_absolute_url(page_name),
        "feed_url": _page_absolute_url(page_name, "m=history_json"),
        "items": [
            {
                "id": item["url"],
                "url": item["url"],
                "title": f"Revision {item['revision']}",
                "content_html": item["content_html"],
                "content_text": item["content_markdown"],
                "date_published": item["created_iso"],
            }
            for item in items
        ],
    }
    response = jsonify(payload)
    response.headers["Content-Type"] = "application/feed+json"
    return response


def _feed_item(revision_row: Row, *, page_name: str) -> dict[str, object]:
    """Render a revision into the shape both the RSS template and JSON Feed want.

    `content_html` is the page content rendered to HTML (what feed readers
    display); `content_markdown` is the raw markdown source carried in
    source:markdown for the RSS extension. Wikilinks are resolved against
    an absolute site root so links survive being read outside the browser
    context.
    """
    absolute_root = f"{request.scheme}://{request.host}{site_root()}"
    return {
        "revision": revision_row.revision,
        "created": revision_row.created,
        "created_iso": revision_row.created.isoformat() + "Z",
        "created_rfc822": revision_row.created.strftime("%a, %d %b %Y %H:%M:%S GMT"),
        "url": _page_absolute_url(page_name, f"r={revision_row.revision}"),
        "content_markdown": revision_row.content,
        "content_html": format_content(revision_row.content, site_root=absolute_root),
    }


def _page_absolute_url(page_name: str, query: str = "") -> str:
    base = f"{request.scheme}://{request.host}{site_root()}{page_slug(page_name)}"
    return f"{base}?{query}" if query else base


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


def _resolve_diff_revisions(conn: Connection, *, page_id: int) -> tuple[Row | None, Row | None]:
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
        # Brand-new page: prefill with an h1 of the page name so the user
        # doesn't have to type the title themselves. Home (empty name)
        # stays blank — there's no name to use.
        prefill = f"# {page_name}\n\n" if page_name else ""
        return render_template(
            "edit_page.html",
            page_name=page_name,
            content=prefill,
            current_revision=0,
            caret_pos=len(prefill),
            scroll_pos=0,
            is_new=True,
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
        caret_pos=page.caret_pos,
        scroll_pos=page.scroll_pos,
        is_new=False,
    )


def _revert(conn: Connection, page_name: str) -> ResponseReturnValue:
    """Restore a page's content to an earlier revision (recorded as a new revision)."""
    page = get_page(conn, site_id=g.site.id, page_name=page_name)
    if page is None:
        abort(400)

    target_revision = request.form.get("r", type=int)
    if target_revision is None:
        abort(400)
    target = get_revision(conn, page_id=page.id, revision=target_revision)
    if target is None:
        abort(400)

    # Undelete first so update_page sees a live page; update_page then
    # records the revert as a normal revision with its own diff summary.
    if page.deleted:
        undelete_page(conn, page_id=page.id, name=page_name)
    latest = get_revision(conn, page_id=page.id)
    if latest is not None and latest.content != target.content:
        update_page(conn, page_id=page.id, content=target.content, ip=request.remote_addr)

    return _redirect_to(page_name)


def _undelete(conn: Connection, page_name: str) -> ResponseReturnValue:
    """Restore a deleted page and append an "undeleted" revision.

    The previous revision (before the delete sentinel) had the real
    content; we re-record it so the page's latest revision shows the
    live body again.
    """
    page = get_page(conn, site_id=g.site.id, page_name=page_name)
    if page is None:
        abort(400)

    undelete_page(conn, page_id=page.id, name=page_name)
    latest = get_revision(conn, page_id=page.id)
    if latest is None:
        return _redirect_to(page_name)

    # The "deleted" sentinel is the latest revision; the one before holds
    # the last real content. Restore that.
    pre_delete = get_revision(conn, page_id=page.id, revision=max(latest.revision - 1, 1))
    if pre_delete is not None:
        new_revision(
            conn,
            page_id=page.id,
            revision=latest.revision + 1,
            content=pre_delete.content,
            changes="<em>Delete undone.</em>",
            ip=request.remote_addr,
        )

    return _redirect_to(page_name)


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
