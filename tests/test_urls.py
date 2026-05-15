from __future__ import annotations

from flask import Flask

from jottit.urls import page_slug, site_root

# ---- page_slug ----


def test_page_slug_lowercases_and_underscores_spaces() -> None:
    assert page_slug("About Us") == "about_us"


def test_page_slug_percent_encodes_unsafe_chars() -> None:
    assert page_slug("café") == "caf%C3%A9"


def test_page_slug_empty_returns_empty() -> None:
    assert page_slug("") == ""


# ---- site_root ----


def test_site_root_subdomain_returns_slash() -> None:
    app = Flask(__name__)
    with app.test_request_context("/"):
        # No blueprint set (apex) → still `/`.
        assert site_root() == "/"


def test_site_root_secret_blueprint_returns_slug_prefix(app: Flask) -> None:
    # Use the real app with the secret blueprint registered.
    with app.test_request_context("/abc12/", base_url="http://jottit.test/"):
        # Push the URL through routing so request.blueprint is set.
        app.preprocess_request()
        assert site_root() == "/abc12/"


def test_site_root_subdomain_blueprint_returns_slash(app: Flask) -> None:
    with app.test_request_context("/", base_url="http://alpha.jottit.test/"):
        app.preprocess_request()
        assert site_root() == "/"
