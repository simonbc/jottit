from __future__ import annotations

from flask import Blueprint

from jottit.views import page as views

page_bp = Blueprint("page", __name__, subdomain="<site_slug>")

page_bp.add_url_rule("/", view_func=views.home, methods=["GET", "POST"])
page_bp.add_url_rule("/<page_name>", view_func=views.view, methods=["GET", "POST"])
