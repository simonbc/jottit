from __future__ import annotations

from flask import Blueprint

from jottit.views import site as views

site_bp = Blueprint("site", __name__, subdomain="<site_slug>", url_prefix="/site")

site_bp.add_url_rule("/claim", view_func=views.claim, methods=["GET", "POST"])
site_bp.add_url_rule("/signin", view_func=views.signin, methods=["GET", "POST"])
site_bp.add_url_rule("/signout", view_func=views.signout, methods=["POST"])
site_bp.add_url_rule("/forgot-password", view_func=views.forgot_password, methods=["GET", "POST"])
site_bp.add_url_rule("/change-password", view_func=views.change_password, methods=["GET", "POST"])
site_bp.add_url_rule("/changes", view_func=views.changes)
site_bp.add_url_rule("/changes.rss", view_func=views.changes_rss)
site_bp.add_url_rule("/changes.json", view_func=views.changes_json)
site_bp.add_url_rule("/hide-primer", view_func=views.hide_primer, methods=["POST"])
