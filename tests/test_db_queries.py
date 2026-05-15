from __future__ import annotations

import pytest
from sqlalchemy import Connection, select

from jottit.db import (
    _AMBIGUOUS_CHARS,
    claim_site,
    delete_draft,
    delete_page,
    designs,
    drafts,
    get_page,
    get_revision,
    get_site,
    new_page,
    new_site,
    pages,
    recover_password,
    revisions,
    set_change_pwd_token,
    set_password,
    undelete_page,
    update_caret_pos,
    update_page,
    update_site,
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


# ---- update_caret_pos ----


def test_update_caret_pos_persists_values(db_conn: Connection) -> None:
    site_id = new_site(db_conn, content="hi", secret_url="uc1")
    page = get_page(db_conn, site_id=site_id, page_name="")
    assert page is not None

    update_caret_pos(db_conn, page_id=page.id, scroll_pos=120, caret_pos=45)

    refreshed = get_page(db_conn, site_id=site_id, page_name="")
    assert refreshed is not None
    assert refreshed.scroll_pos == 120
    assert refreshed.caret_pos == 45


# ---- update_page ----


def test_update_page_creates_new_revision_when_content_changes(db_conn: Connection) -> None:
    site_id = new_site(db_conn, content="<p>hello</p>", secret_url="up1")
    page = get_page(db_conn, site_id=site_id, page_name="")
    assert page is not None

    update_page(db_conn, page_id=page.id, content="<p>hello world</p>")

    latest = get_revision(db_conn, page_id=page.id)
    assert latest is not None
    assert latest.revision == 2
    assert latest.content == "<p>hello world</p>"
    assert latest.changes is not None
    assert "Added" in latest.changes
    assert "world" in latest.changes


def test_update_page_noop_when_content_unchanged(db_conn: Connection) -> None:
    site_id = new_site(db_conn, content="same", secret_url="up2")
    page = get_page(db_conn, site_id=site_id, page_name="")
    assert page is not None

    update_page(db_conn, page_id=page.id, content="same")

    latest = get_revision(db_conn, page_id=page.id)
    assert latest is not None
    assert latest.revision == 1


def test_update_page_replace_summary(db_conn: Connection) -> None:
    site_id = new_site(db_conn, content="<p>hello world</p>", secret_url="up3")
    page = get_page(db_conn, site_id=site_id, page_name="")
    assert page is not None

    update_page(db_conn, page_id=page.id, content="<p>hello there</p>")

    latest = get_revision(db_conn, page_id=page.id)
    assert latest is not None
    assert latest.changes is not None
    assert "Changed" in latest.changes
    assert "world" in latest.changes
    assert "there" in latest.changes


def test_update_page_clears_draft(db_conn: Connection) -> None:
    from sqlalchemy import insert as sa_insert

    site_id = new_site(db_conn, content="hi", secret_url="up4")
    page = get_page(db_conn, site_id=site_id, page_name="")
    assert page is not None

    db_conn.execute(sa_insert(drafts).values(page_id=page.id, content="draft text"))
    assert db_conn.execute(select(drafts).where(drafts.c.page_id == page.id)).first() is not None

    update_page(db_conn, page_id=page.id, content="hi changed")

    assert db_conn.execute(select(drafts).where(drafts.c.page_id == page.id)).first() is None


def test_update_page_updates_caret_and_scroll(db_conn: Connection) -> None:
    site_id = new_site(db_conn, content="hi", secret_url="up5")
    page = get_page(db_conn, site_id=site_id, page_name="")
    assert page is not None

    update_page(db_conn, page_id=page.id, content="hi changed", scroll_pos=80, caret_pos=10)

    refreshed = get_page(db_conn, site_id=site_id, page_name="")
    assert refreshed is not None
    assert refreshed.scroll_pos == 80
    assert refreshed.caret_pos == 10


# ---- delete_page / undelete_page ----


def test_delete_page_marks_deleted_and_records_revision(db_conn: Connection) -> None:
    site_id = new_site(db_conn, content="hi", secret_url="dp1")
    page = get_page(db_conn, site_id=site_id, page_name="")
    assert page is not None

    delete_page(db_conn, page_id=page.id)

    deleted_row = db_conn.execute(select(pages).where(pages.c.id == page.id)).one()
    assert deleted_row.deleted is True

    latest = get_revision(db_conn, page_id=page.id)
    assert latest is not None
    assert latest.revision == 2
    assert latest.content == ""
    assert latest.changes == "<em>Page deleted.</em>"


def test_undelete_page_restores_with_new_name(db_conn: Connection) -> None:
    site_id = new_site(db_conn, content="hi", secret_url="ud1")
    new_page(db_conn, site_id=site_id, name="foo", content="x")
    page = get_page(db_conn, site_id=site_id, page_name="foo")
    assert page is not None

    delete_page(db_conn, page_id=page.id)
    undelete_page(db_conn, page_id=page.id, name="Foo")

    refreshed = db_conn.execute(select(pages).where(pages.c.id == page.id)).one()
    assert refreshed.deleted is False
    assert refreshed.name == "Foo"


# ---- delete_draft ----


def test_delete_draft_removes_row(db_conn: Connection) -> None:
    from sqlalchemy import insert as sa_insert

    site_id = new_site(db_conn, content="hi", secret_url="dd1")
    page = get_page(db_conn, site_id=site_id, page_name="")
    assert page is not None

    db_conn.execute(sa_insert(drafts).values(page_id=page.id, content="wip"))

    delete_draft(db_conn, page_id=page.id)

    assert db_conn.execute(select(drafts).where(drafts.c.page_id == page.id)).first() is None


def test_delete_draft_noop_when_absent(db_conn: Connection) -> None:
    site_id = new_site(db_conn, content="hi", secret_url="dd2")
    page = get_page(db_conn, site_id=site_id, page_name="")
    assert page is not None

    delete_draft(db_conn, page_id=page.id)  # should not raise


# ---- claim_site ----


def test_claim_site_sets_password_email_and_security(db_conn: Connection) -> None:
    site_id = new_site(db_conn, content="hi", secret_url="cl1")

    claim_site(
        db_conn,
        site_id=site_id,
        password_hash="$argon2id$fake-hash",
        email="owner@example.com",
        security="private",
    )

    row = get_site(db_conn, site_id=site_id)
    assert row is not None
    assert row.password == "$argon2id$fake-hash"
    assert row.email == "owner@example.com"
    assert row.security == "private"


# ---- set_password ----


def test_set_password_only_touches_password_column(db_conn: Connection) -> None:
    site_id = new_site(db_conn, content="hi", secret_url="sp1")
    claim_site(
        db_conn,
        site_id=site_id,
        password_hash="$argon2id$old",
        email="owner@example.com",
        security="public",
    )

    set_password(db_conn, site_id=site_id, password_hash="$argon2id$new")

    row = get_site(db_conn, site_id=site_id)
    assert row is not None
    assert row.password == "$argon2id$new"
    assert row.email == "owner@example.com"
    assert row.security == "public"


# ---- change_pwd_token / recover_password ----


def test_set_change_pwd_token_stores_token(db_conn: Connection) -> None:
    site_id = new_site(db_conn, content="hi", secret_url="tk1")

    set_change_pwd_token(db_conn, site_id=site_id, token="abc123token")

    row = get_site(db_conn, site_id=site_id)
    assert row is not None
    assert row.change_pwd_token == "abc123token"


def test_recover_password_sets_password_and_clears_token(db_conn: Connection) -> None:
    site_id = new_site(db_conn, content="hi", secret_url="rp1")
    set_change_pwd_token(db_conn, site_id=site_id, token="one-time-token")

    recover_password(db_conn, site_id=site_id, password_hash="$argon2id$recovered")

    row = get_site(db_conn, site_id=site_id)
    assert row is not None
    assert row.password == "$argon2id$recovered"
    assert row.change_pwd_token is None


# ---- update_site ----


def test_update_site_patches_only_provided_fields(db_conn: Connection) -> None:
    site_id = new_site(db_conn, content="hi", secret_url="us1")
    claim_site(
        db_conn,
        site_id=site_id,
        password_hash="$argon2id$x",
        email="orig@example.com",
        security="public",
    )

    update_site(db_conn, site_id=site_id, title="My Site", subtitle="of jottings")

    row = get_site(db_conn, site_id=site_id)
    assert row is not None
    assert row.title == "My Site"
    assert row.subtitle == "of jottings"
    # Untouched fields are preserved.
    assert row.email == "orig@example.com"
    assert row.security == "public"


def test_update_site_no_args_is_noop(db_conn: Connection) -> None:
    site_id = new_site(db_conn, content="hi", secret_url="us2")

    update_site(db_conn, site_id=site_id)  # should not raise

    row = get_site(db_conn, site_id=site_id)
    assert row is not None


def test_update_site_can_change_security_level(db_conn: Connection) -> None:
    site_id = new_site(db_conn, content="hi", secret_url="us3")
    claim_site(
        db_conn,
        site_id=site_id,
        password_hash="$argon2id$x",
        email="o@example.com",
        security="private",
    )

    update_site(db_conn, site_id=site_id, security="open")

    row = get_site(db_conn, site_id=site_id)
    assert row is not None
    assert row.security == "open"
