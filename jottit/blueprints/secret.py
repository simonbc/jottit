from __future__ import annotations

from flask import Blueprint

from jottit.views import admin as admin_views
from jottit.views import page as page_views
from jottit.views import site as site_views

secret_bp = Blueprint("secret", __name__, url_prefix="/<site_slug>")

# Page
secret_bp.add_url_rule(
    "/", endpoint="page_home", view_func=page_views.home, methods=["GET", "POST"]
)
secret_bp.add_url_rule(
    "/<page_name>",
    endpoint="page_view",
    view_func=page_views.view,
    methods=["GET", "POST"],
)

# Site
secret_bp.add_url_rule(
    "/site/claim", endpoint="site_claim", view_func=site_views.claim, methods=["GET", "POST"]
)
secret_bp.add_url_rule(
    "/site/signin", endpoint="site_signin", view_func=site_views.signin, methods=["GET", "POST"]
)
secret_bp.add_url_rule(
    "/site/signout", endpoint="site_signout", view_func=site_views.signout, methods=["POST"]
)
secret_bp.add_url_rule(
    "/site/forgot-password",
    endpoint="site_forgot_password",
    view_func=site_views.forgot_password,
    methods=["GET", "POST"],
)
secret_bp.add_url_rule(
    "/site/change-password",
    endpoint="site_change_password",
    view_func=site_views.change_password,
    methods=["GET", "POST"],
)
secret_bp.add_url_rule("/site/changes", endpoint="site_changes", view_func=site_views.changes)
secret_bp.add_url_rule(
    "/site/changes.atom",
    endpoint="site_changes_atom",
    view_func=site_views.changes_atom,
)
secret_bp.add_url_rule(
    "/site/hide-primer",
    endpoint="site_hide_primer",
    view_func=site_views.hide_primer,
    methods=["POST"],
)

# Admin
secret_bp.add_url_rule(
    "/admin/settings",
    endpoint="admin_settings",
    view_func=admin_views.settings,
    methods=["GET", "POST"],
)
secret_bp.add_url_rule(
    "/admin/design",
    endpoint="admin_design",
    view_func=admin_views.design,
    methods=["GET", "POST"],
)
secret_bp.add_url_rule(
    "/admin/url-available",
    endpoint="admin_url_available",
    view_func=admin_views.url_available,
    methods=["POST"],
)
secret_bp.add_url_rule(
    "/admin/delete",
    endpoint="admin_delete",
    view_func=admin_views.delete,
    methods=["GET", "POST"],
)
secret_bp.add_url_rule(
    "/admin/change-site-address",
    endpoint="admin_change_site_address",
    view_func=admin_views.change_site_address,
    methods=["GET", "POST"],
)
secret_bp.add_url_rule(
    "/admin/change-password",
    endpoint="admin_change_password",
    view_func=admin_views.change_password,
    methods=["GET", "POST"],
)
secret_bp.add_url_rule("/admin/export", endpoint="admin_export", view_func=admin_views.export)
