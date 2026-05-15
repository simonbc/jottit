from __future__ import annotations

import os

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from jottit.blueprints.admin import admin_bp
from jottit.blueprints.page import page_bp
from jottit.blueprints.root import root_bp
from jottit.blueprints.site import site_bp
from jottit.site_resolver import resolve_site


def create_app() -> Flask:
    app = Flask(__name__, subdomain_matching=True)
    app.config["SERVER_NAME"] = os.environ.get("JOTTIT_DOMAIN", "localhost:5000")
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)  # type: ignore[method-assign]

    app.register_blueprint(root_bp)
    app.register_blueprint(site_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(page_bp)

    app.before_request(resolve_site)

    return app
