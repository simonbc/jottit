from __future__ import annotations

import pytest
from sqlalchemy import Connection, select

from jottit.db import (
    _AMBIGUOUS_CHARS,
    designs,
    get_site,
    new_site,
    pages,
    revisions,
)


def test_get_site_by_secret_url(db_conn: Connection) -> None:
    site_id = new_site(db_conn, content="hello", secret_url="test-secret")

    row = get_site(db_conn, secret_url="test-secret")
    assert row is not None
    assert row.id == site_id


def test_get_site_by_public_url(db_conn: Connection) -> None:
    site_id = new_site(db_conn, content="hi", secret_url="s1", public_url="myblog")

    row = get_site(db_conn, public_url="myblog")
    assert row is not None
    assert row.id == site_id


def test_get_site_by_id(db_conn: Connection) -> None:
    site_id = new_site(db_conn, content="hi", secret_url="s2")

    row = get_site(db_conn, site_id=site_id)
    assert row is not None
    assert row.id == site_id


def test_get_site_missing_returns_none(db_conn: Connection) -> None:
    assert get_site(db_conn, secret_url="nonexistent") is None


def test_get_site_requires_at_least_one_criterion(db_conn: Connection) -> None:
    with pytest.raises(ValueError):
        get_site(db_conn)


def test_new_site_generates_secret_url_when_not_provided(db_conn: Connection) -> None:
    site_id = new_site(db_conn, content="welcome")

    row = get_site(db_conn, site_id=site_id)
    assert row is not None
    assert row.secret_url
    assert 4 <= len(row.secret_url) <= 5
    assert not any(c in _AMBIGUOUS_CHARS for c in row.secret_url)


def test_new_site_creates_design_row_with_random_scheme(db_conn: Connection) -> None:
    site_id = new_site(db_conn, content="hi", secret_url="d1")

    design = db_conn.execute(select(designs).where(designs.c.site_id == site_id)).one()
    assert design.title_font == "Lucida_Grande"
    assert design.header_color.startswith("#")
    assert design.title_color.startswith("#")
    assert design.subtitle_color.startswith("#")
    assert design.hue
    assert design.brightness


def test_new_site_creates_home_page_with_initial_revision(db_conn: Connection) -> None:
    site_id = new_site(db_conn, content="welcome to my site", secret_url="p1")

    page = db_conn.execute(select(pages).where(pages.c.site_id == site_id)).one()
    assert page.name == ""

    rev = db_conn.execute(select(revisions).where(revisions.c.page_id == page.id)).one()
    assert rev.revision == 1
    assert rev.content == "welcome to my site"
    assert rev.changes == "<em>Created page</em>"


def test_new_site_updates_sites_updated_timestamp(db_conn: Connection) -> None:
    site_id = new_site(db_conn, content="hi", secret_url="u1")

    row = get_site(db_conn, site_id=site_id)
    assert row is not None
    assert row.updated is not None
    assert row.updated >= row.created


def test_new_site_stores_partner_when_provided(db_conn: Connection) -> None:
    site_id = new_site(db_conn, content="hi", secret_url="pt1", partner="affiliate-x")

    row = get_site(db_conn, site_id=site_id)
    assert row is not None
    assert row.partner == "affiliate-x"


def test_new_site_passes_ip_to_first_revision(db_conn: Connection) -> None:
    site_id = new_site(db_conn, content="hi", secret_url="ip1", ip="203.0.113.1")

    rev = db_conn.execute(select(revisions).join(pages).where(pages.c.site_id == site_id)).one()
    assert rev.ip == "203.0.113.1"


def test_new_site_empty_partner_stored_as_null(db_conn: Connection) -> None:
    site_id = new_site(db_conn, content="hi", secret_url="np1", partner="")

    row = get_site(db_conn, site_id=site_id)
    assert row is not None
    assert row.partner is None
