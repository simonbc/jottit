"""Shared template context: site, page list, signin state, and design row.

Wired into the Flask app as a `context_processor` so every render_template
call sees these variables without each view having to pass them.
"""

from __future__ import annotations

from typing import Any

from flask import g, request

from jottit import auth
from jottit.db import get_design, get_request_conn, list_pages
from jottit.urls import page_slug, site_root


def chrome_context() -> dict[str, Any]:
    """Variables every page template can rely on.

    `site` and `pages` are `None` on apex-domain routes (the front page);
    templates should branch on `site` before reading from it.
    """
    site = getattr(g, "site", None)
    if site is None:
        return {
            "site": None,
            "pages": [],
            "design": None,
            "is_signed_in": False,
            "is_unclaimed": False,
            "site_root_path": "/",
            "page_slug": page_slug,
            "current_path": request.path,
        }

    conn = get_request_conn()
    pages = list_pages(conn, site_id=site.id) if conn is not None else []
    design = get_design(conn, site_id=site.id) if conn is not None else None
    return {
        "site": site,
        "pages": pages,
        "design": design,
        "is_signed_in": auth.is_signed_in_to(site.id),
        "is_unclaimed": site.password is None,
        "site_root_path": site_root(),
        "page_slug": page_slug,
        "current_path": request.path,
    }
