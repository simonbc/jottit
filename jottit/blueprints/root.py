from __future__ import annotations

from flask import Blueprint, request

root_bp = Blueprint("root", __name__)


@root_bp.route("/", methods=["GET", "POST"])
def index() -> str:
    return f"jottit:index {request.method} (TODO)"


@root_bp.route("/sites", methods=["GET", "POST"])
def sites() -> str:
    return f"jottit:sites {request.method} (TODO)"


@root_bp.route("/about")
def about() -> str:
    return "jottit:about (TODO)"


@root_bp.route("/help")
def help_page() -> str:
    return "jottit:help (TODO)"


@root_bp.route("/feedback", methods=["GET", "POST"])
def feedback() -> str:
    return f"jottit:feedback {request.method} (TODO)"
