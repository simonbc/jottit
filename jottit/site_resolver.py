from __future__ import annotations

from flask import g, request


def resolve_site() -> None:
    """Stash site context on `flask.g` for the current request.

    `g.site_slug` is the URL slug captured from a subdomain or path prefix,
    or `None` on apex-domain routes.

    `g.site` is the resolved site row, or `None`. The DB lookup is wired
    once the engine is bound to the app.
    """
    g.site_slug = (request.view_args or {}).get("site_slug")
    g.site = None
