from __future__ import annotations

from urllib.parse import quote

from flask import g, request


def page_slug(name: str) -> str:
    """URL slug for a page name: lowercased, spaces → underscores, percent-encoded."""
    return quote(name.lower().replace(" ", "_"))


def site_root() -> str:
    """URL path prefix that page names hang off for the current request.

    `/` for a subdomain site, `/<slug>/` for one accessed via its secret URL.
    Wikilinks and post-save redirects both want this.
    """
    if request.blueprint == "secret":
        return f"/{g.site_slug}/"
    return "/"
