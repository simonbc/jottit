from __future__ import annotations

from flask import Blueprint, request

page_bp = Blueprint("page", __name__, subdomain="<site_slug>")


@page_bp.route("/")
def home(site_slug: str) -> str:
    return f"page:{site_slug} home GET (TODO)"


@page_bp.route("/<page_name>", methods=["GET", "POST"])
def page(site_slug: str, page_name: str) -> str:
    mode = request.args.get("m", "view")
    return f"page:{site_slug} page={page_name} m={mode} {request.method} (TODO)"
