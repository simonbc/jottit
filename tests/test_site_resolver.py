from __future__ import annotations

from flask import Flask, g, request

from jottit.site_resolver import resolve_site


def test_resolver_populates_site_slug_from_view_args(app: Flask) -> None:
    with app.test_request_context("/"):
        request.view_args = {"site_slug": "myblog"}
        resolve_site()
        assert g.site_slug == "myblog"
        assert g.site is None


def test_resolver_handles_none_view_args(app: Flask) -> None:
    with app.test_request_context("/"):
        request.view_args = None
        resolve_site()
        assert g.site_slug is None
        assert g.site is None


def test_resolver_handles_empty_view_args(app: Flask) -> None:
    with app.test_request_context("/"):
        request.view_args = {}
        resolve_site()
        assert g.site_slug is None
        assert g.site is None


def test_hook_runs_on_subdomain_request(app: Flask) -> None:
    with app.test_request_context("/", base_url="http://blog.jottit.test/"):
        app.preprocess_request()
        assert g.site_slug == "blog"
        assert g.site is None


def test_hook_runs_on_apex_request(app: Flask) -> None:
    with app.test_request_context("/about", base_url="http://jottit.test/"):
        app.preprocess_request()
        assert g.site_slug is None
        assert g.site is None


def test_hook_runs_on_admin_subdomain_route(app: Flask) -> None:
    with app.test_request_context("/admin/settings", base_url="http://myblog.jottit.test/"):
        app.preprocess_request()
        assert g.site_slug == "myblog"
