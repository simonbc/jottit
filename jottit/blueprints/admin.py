from __future__ import annotations

from flask import Blueprint, request

admin_bp = Blueprint("admin", __name__, subdomain="<site_slug>", url_prefix="/admin")


@admin_bp.route("/settings", methods=["GET", "POST"])
def settings(site_slug: str) -> str:
    return f"admin:{site_slug} admin/settings {request.method} (TODO)"


@admin_bp.route("/design", methods=["GET", "POST"])
def design(site_slug: str) -> str:
    return f"admin:{site_slug} admin/design {request.method} (TODO)"


@admin_bp.route("/url-available", methods=["POST"])
def url_available(site_slug: str) -> str:
    return f"admin:{site_slug} admin/url-available POST (TODO)"


@admin_bp.route("/delete", methods=["GET", "POST"])
def delete(site_slug: str) -> str:
    return f"admin:{site_slug} admin/delete {request.method} (TODO)"


@admin_bp.route("/change-site-address", methods=["GET", "POST"])
def change_site_address(site_slug: str) -> str:
    return f"admin:{site_slug} admin/change-site-address {request.method} (TODO)"


@admin_bp.route("/change-password", methods=["GET", "POST"])
def change_password(site_slug: str) -> str:
    return f"admin:{site_slug} admin/change-password {request.method} (TODO)"


@admin_bp.route("/export")
def export(site_slug: str) -> str:
    return f"admin:{site_slug} admin/export GET (TODO)"
