from __future__ import annotations

from flask import Flask, g, request
from sqlalchemy import Connection

from jottit.db import new_site
from jottit.site_resolver import resolve_site
from tests.conftest import request_under_test

# ---- Unit tests: call resolve_site() directly with synthetic view_args ----


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


def test_hook_runs_on_apex_request(app: Flask, db_conn: Connection) -> None:
    with request_under_test(app, "/about", base_url="http://jottit.test/", db_conn=db_conn):
        assert g.site_slug is None
        assert g.site is None


# ---- Integration tests: DB lookup via preprocess_request ----


def test_resolver_populates_site_for_public_url_on_subdomain(
    app: Flask, db_conn: Connection
) -> None:
    site_id = new_site(db_conn, content="hi", secret_url="s1", public_url="myblog")

    with request_under_test(app, "/", base_url="http://myblog.jottit.test/", db_conn=db_conn):
        assert g.site_slug == "myblog"
        assert g.site is not None
        assert g.site.id == site_id
        assert g.site.public_url == "myblog"


def test_resolver_populates_site_for_secret_url_on_secret_path(
    app: Flask, db_conn: Connection
) -> None:
    site_id = new_site(db_conn, content="hi", secret_url="abc123")

    with request_under_test(app, "/abc123/", base_url="http://jottit.test/", db_conn=db_conn):
        assert g.site_slug == "abc123"
        assert g.site is not None
        assert g.site.id == site_id
        assert g.site.secret_url == "abc123"


def test_resolver_returns_none_for_unknown_subdomain(app: Flask, db_conn: Connection) -> None:
    with request_under_test(app, "/", base_url="http://nosuchblog.jottit.test/", db_conn=db_conn):
        assert g.site_slug == "nosuchblog"
        assert g.site is None


def test_resolver_returns_none_for_unknown_secret_url(app: Flask, db_conn: Connection) -> None:
    with request_under_test(app, "/nosuchurl/", base_url="http://jottit.test/", db_conn=db_conn):
        assert g.site_slug == "nosuchurl"
        assert g.site is None


def test_resolver_finds_site_on_admin_subdomain_route(app: Flask, db_conn: Connection) -> None:
    site_id = new_site(db_conn, content="hi", secret_url="s2", public_url="myblog")

    with request_under_test(
        app,
        "/admin/settings",
        base_url="http://myblog.jottit.test/",
        db_conn=db_conn,
    ):
        assert g.site_slug == "myblog"
        assert g.site is not None
        assert g.site.id == site_id


def test_resolver_subdomain_lookup_ignores_secret_url_with_same_value(
    app: Flask, db_conn: Connection
) -> None:
    # A site exists with secret_url="abc123" but no public_url. Visiting it
    # via subdomain (abc123.jottit.test) should NOT match — subdomain access
    # is by public_url only.
    new_site(db_conn, content="hi", secret_url="abc123")

    with request_under_test(app, "/", base_url="http://abc123.jottit.test/", db_conn=db_conn):
        assert g.site_slug == "abc123"
        assert g.site is None
