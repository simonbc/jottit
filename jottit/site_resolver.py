from __future__ import annotations

from flask import g, request

from jottit.db import get_request_conn, get_site


def resolve_site() -> None:
    """Stash site context on `flask.g` for the current request.

    `g.site_slug` is the URL slug captured from a subdomain or path prefix,
    or `None` on apex-domain routes.

    `g.site` is the resolved sites row (a SQLAlchemy Row) or `None` —
    looked up by `public_url` for subdomain routes, by `secret_url` for
    secret-path routes. `None` if the slug doesn't match any site, or if
    no DB engine is configured.
    """
    g.site_slug = (request.view_args or {}).get("site_slug")
    g.site = None

    if g.site_slug is None:
        return

    conn = get_request_conn()
    if conn is None:
        return

    if request.blueprint == "secret":
        site = get_site(conn, secret_url=g.site_slug)
    else:
        site = get_site(conn, public_url=g.site_slug)
    # Deleted sites stay in the database (so an admin restore path is
    # possible later) but are invisible to the resolver — every request
    # for one hits the same 404 as a never-existed slug.
    g.site = site if site is not None and not site.deleted else None
