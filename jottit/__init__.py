from __future__ import annotations

import os

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from jottit.blueprints.root import root_bp


def create_app() -> Flask:
    app = Flask(__name__, subdomain_matching=True)
    app.config["SERVER_NAME"] = os.environ.get("JOTTIT_DOMAIN", "localhost:5000")
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)  # type: ignore[method-assign]

    app.register_blueprint(root_bp)

    return app
