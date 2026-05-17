from __future__ import annotations

import os
from datetime import timedelta

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from jottit.blueprints.admin import admin_bp
from jottit.blueprints.page import page_bp
from jottit.blueprints.root import root_bp
from jottit.blueprints.secret import secret_bp
from jottit.blueprints.site import site_bp
from jottit.chrome import chrome_context
from jottit.db import close_request_conn, make_engine
from jottit.site_resolver import resolve_site


def create_app() -> Flask:
    app = Flask(__name__, subdomain_matching=True)
    app.config["SERVER_NAME"] = os.environ.get("JOTTIT_DOMAIN", "localhost:5000")
    app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
    # "Remember me" on the signin form marks the session permanent; this is
    # how long it lives once that flag is set.
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)  # type: ignore[method-assign]

    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        app.extensions["db_engine"] = make_engine(database_url)

    app.register_blueprint(root_bp)
    app.register_blueprint(site_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(page_bp)
    app.register_blueprint(secret_bp)

    app.before_request(resolve_site)
    app.teardown_request(close_request_conn)
    app.context_processor(chrome_context)

    return app
