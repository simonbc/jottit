from __future__ import annotations

from flask import Blueprint

from jottit.views import root as views

root_bp = Blueprint("root", __name__)

root_bp.add_url_rule("/", view_func=views.index, methods=["GET", "POST"])
root_bp.add_url_rule("/sites", view_func=views.sites, methods=["GET", "POST"])
root_bp.add_url_rule("/about", view_func=views.about)
root_bp.add_url_rule("/help", view_func=views.help_page)
root_bp.add_url_rule("/feedback", view_func=views.feedback, methods=["GET", "POST"])
root_bp.add_url_rule("/healthz", view_func=views.healthz)
