from __future__ import annotations

from flask import Blueprint

from jottit.views import draft as draft_views
from jottit.views import page as views

page_bp = Blueprint("page", __name__, subdomain="<site_slug>")

page_bp.add_url_rule("/", view_func=views.home, methods=["GET", "POST"])
page_bp.add_url_rule(
    "/draft/save",
    endpoint="draft_save",
    view_func=draft_views.save,
    methods=["POST"],
)
page_bp.add_url_rule(
    "/draft/cancel",
    endpoint="draft_cancel",
    view_func=draft_views.cancel,
    methods=["POST"],
)
page_bp.add_url_rule(
    "/draft/recover-live-version",
    endpoint="draft_recover_live_version",
    view_func=draft_views.recover_live_version,
    methods=["POST"],
)
page_bp.add_url_rule("/<page_name>", view_func=views.view, methods=["GET", "POST"])
