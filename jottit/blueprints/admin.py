from __future__ import annotations

from flask import Blueprint

from jottit.views import admin as views

admin_bp = Blueprint("admin", __name__, subdomain="<site_slug>", url_prefix="/admin")

admin_bp.add_url_rule("/settings", view_func=views.settings, methods=["GET", "POST"])
admin_bp.add_url_rule("/design", view_func=views.design, methods=["GET", "POST"])
admin_bp.add_url_rule("/url-available", view_func=views.url_available, methods=["POST"])
admin_bp.add_url_rule("/delete", view_func=views.delete, methods=["GET", "POST"])
admin_bp.add_url_rule(
    "/change-site-address",
    view_func=views.change_site_address,
    methods=["GET", "POST"],
)
admin_bp.add_url_rule("/change-password", view_func=views.change_password, methods=["GET", "POST"])
admin_bp.add_url_rule("/export", view_func=views.export)
