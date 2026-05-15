from __future__ import annotations

from flask import request


def home(site_slug: str) -> str:
    return f"page:{site_slug} home GET (TODO)"


def view(site_slug: str, page_name: str) -> str:
    mode = request.args.get("m", "view")
    return f"page:{site_slug} page={page_name} m={mode} {request.method} (TODO)"
