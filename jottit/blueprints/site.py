from __future__ import annotations

from flask import Blueprint, request

site_bp = Blueprint("site", __name__, subdomain="<site_slug>", url_prefix="/site")


@site_bp.route("/claim", methods=["GET", "POST"])
def claim(site_slug: str) -> str:
    return f"site:{site_slug} site/claim {request.method} (TODO)"


@site_bp.route("/signin", methods=["GET", "POST"])
def signin(site_slug: str) -> str:
    return f"site:{site_slug} site/signin {request.method} (TODO)"


@site_bp.route("/signout", methods=["POST"])
def signout(site_slug: str) -> str:
    return f"site:{site_slug} site/signout POST (TODO)"


@site_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password(site_slug: str) -> str:
    return f"site:{site_slug} site/forgot-password {request.method} (TODO)"


@site_bp.route("/change-password", methods=["GET", "POST"])
def change_password(site_slug: str) -> str:
    return f"site:{site_slug} site/change-password {request.method} (TODO)"


@site_bp.route("/changes")
def changes(site_slug: str) -> str:
    return f"site:{site_slug} site/changes GET (TODO)"


@site_bp.route("/changes.atom")
def changes_atom(site_slug: str) -> str:
    return f"site:{site_slug} site/changes.atom GET (TODO)"


@site_bp.route("/hide-primer", methods=["POST"])
def hide_primer(site_slug: str) -> str:
    return f"site:{site_slug} site/hide-primer POST (TODO)"
