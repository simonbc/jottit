from __future__ import annotations

import pytest
from sqlalchemy import Connection, select

from jottit.db import (
    _AMBIGUOUS_CHARS,
    designs,
    get_page,
    get_revision,
    get_site,
    new_page,
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


# ---- get_page ----


def test_get_page_finds_home_after_new_site(db_conn: Connection) -> None:
    site_id = new_site(db_conn, content="hi", secret_url="gp1")

    page = get_page(db_conn, site_id=site_id, page_name="")
    assert page is not None
    assert page.site_id == site_id
    assert page.name == ""


def test_get_page_is_case_insensitive(db_conn: Connection) -> None:
    site_id = new_site(db_conn, content="hi", secret_url="gp2")
    new_page(db_conn, site_id=site_id, name="MyPage", content="x")

    assert get_page(db_conn, site_id=site_id, page_name="MyPage") is not None
    assert get_page(db_conn, site_id=site_id, page_name="mypage") is not None
    assert get_page(db_conn, site_id=site_id, page_name="MYPAGE") is not None


def test_get_page_missing_returns_none(db_conn: Connection) -> None:
    site_id = new_site(db_conn, content="hi", secret_url="gp3")

    assert get_page(db_conn, site_id=site_id, page_name="nonexistent") is None


def test_get_page_scoped_to_site(db_conn: Connection) -> None:
    site_a = new_site(db_conn, content="a", secret_url="gp4a")
    site_b = new_site(db_conn, content="b", secret_url="gp4b")
    new_page(db_conn, site_id=site_a, name="shared", content="x")

    assert get_page(db_conn, site_id=site_a, page_name="shared") is not None
    assert get_page(db_conn, site_id=site_b, page_name="shared") is None


# ---- get_revision ----


def test_get_revision_returns_latest_by_default(db_conn: Connection) -> None:
    site_id = new_site(db_conn, content="hi", secret_url="gr1")
    page = get_page(db_conn, site_id=site_id, page_name="")
    assert page is not None

    rev = get_revision(db_conn, page_id=page.id)
    assert rev is not None
    assert rev.revision == 1
    assert rev.content == "hi"


def test_get_revision_returns_specific_revision(db_conn: Connection) -> None:
    site_id = new_site(db_conn, content="hi", secret_url="gr2")
    page = get_page(db_conn, site_id=site_id, page_name="")
    assert page is not None

    rev = get_revision(db_conn, page_id=page.id, revision=1)
    assert rev is not None
    assert rev.revision == 1


def test_get_revision_missing_returns_none(db_conn: Connection) -> None:
    site_id = new_site(db_conn, content="hi", secret_url="gr3")
    page = get_page(db_conn, site_id=site_id, page_name="")
    assert page is not None

    assert get_revision(db_conn, page_id=page.id, revision=999) is None


def test_get_revision_no_revisions_returns_none(db_conn: Connection) -> None:
    # Page rows can exist without revisions if someone bypasses new_page;
    # the revision-only function should handle that cleanly.
    from sqlalchemy import insert as sa_insert

    site_id = new_site(db_conn, content="hi", secret_url="gr4")
    page_id = db_conn.execute(
        sa_insert(pages).values(site_id=site_id, name="orphan").returning(pages.c.id)
    ).scalar_one()

    assert get_revision(db_conn, page_id=page_id) is None
