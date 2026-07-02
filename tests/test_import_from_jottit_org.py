from __future__ import annotations

import importlib.util
import os

from sqlalchemy import Connection, select

from jottit.db import designs, get_revision, get_revisions, pages, sites

# The importer lives in scripts/, which isn't a package; load it by path.
_SPEC = importlib.util.spec_from_file_location(
    "import_from_jottit_org",
    os.path.join(os.path.dirname(__file__), "..", "scripts", "import_from_jottit_org.py"),
)
importer = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(importer)


def _bundle():
    return {
        "source": "jottit.org",
        "profiles": [
            {
                "username": "alice",
                "email": "alice@example.com",
                "name": "Alice Smith",
                "bio": "# Alice\n\nHi.",
                "created_at": "2026-01-01T10:00:00+00:00",
                "pages": [
                    {
                        "slug": "hello",
                        "created_at": "2026-01-02T10:00:00+00:00",
                        "revisions": [
                            {"revision": 1, "content": "# Hello\n\nOne.", "created_at": "2026-01-02T10:00:00+00:00"},
                            {"revision": 2, "content": "# Hello\n\nTwo.", "created_at": "2026-01-03T11:30:00+00:00"},
                        ],
                    }
                ],
            },
            {
                "username": "new",  # reserved in jottit.pub
                "email": "bob@example.com",
                "name": "Bob",
                "bio": None,
                "created_at": "2026-01-01T10:00:00+00:00",
                "pages": [
                    {
                        "slug": "about",
                        "created_at": "2026-01-04T10:00:00+00:00",
                        "revisions": [
                            {"revision": 1, "content": "# About", "created_at": "2026-01-04T10:00:00+00:00"},
                        ],
                    }
                ],
            },
        ],
        "unclaimed_pages": [
            {
                "slug": "orphan",
                "created_at": "2026-02-01T00:00:00+00:00",
                "revisions": [
                    {"revision": 1, "content": "# Orphan", "created_at": "2026-02-01T00:00:00+00:00"},
                ],
            }
        ],
    }


def _site_by_title(conn: Connection, title: str):
    return conn.execute(select(sites).where(sites.c.title == title)).first()


def _page(conn: Connection, site_id: int, name: str):
    return conn.execute(
        select(pages).where(pages.c.site_id == site_id, pages.c.name == name)
    ).first()


def test_profile_becomes_claimed_site_with_subdomain(db_conn: Connection) -> None:
    importer.import_bundle(db_conn, _bundle())

    site = _site_by_title(db_conn, "Alice Smith")
    assert site is not None
    assert site.public_url == "alice"
    assert site.email == "alice@example.com"
    assert site.password is not None  # claimed
    assert site.security == "public"


def test_bio_becomes_home_page(db_conn: Connection) -> None:
    importer.import_bundle(db_conn, _bundle())

    site = _site_by_title(db_conn, "Alice Smith")
    home = _page(db_conn, site.id, "")
    assert home is not None
    latest = get_revision(db_conn, page_id=home.id)
    assert latest.content == "# Alice\n\nHi."


def test_missing_bio_gives_empty_home(db_conn: Connection) -> None:
    importer.import_bundle(db_conn, _bundle())

    site = _site_by_title(db_conn, "Bob")
    home = _page(db_conn, site.id, "")
    latest = get_revision(db_conn, page_id=home.id)
    assert latest.content == ""


def test_page_slug_becomes_named_page_with_all_revisions(db_conn: Connection) -> None:
    importer.import_bundle(db_conn, _bundle())

    site = _site_by_title(db_conn, "Alice Smith")
    page = _page(db_conn, site.id, "hello")
    assert page is not None

    revs = get_revisions(db_conn, page_id=page.id)
    assert [r.revision for r in revs] == [2, 1]  # newest-first
    latest = get_revision(db_conn, page_id=page.id)
    assert latest.content == "# Hello\n\nTwo."


def test_revision_timestamps_preserved(db_conn: Connection) -> None:
    importer.import_bundle(db_conn, _bundle())

    site = _site_by_title(db_conn, "Alice Smith")
    page = _page(db_conn, site.id, "hello")
    rev2 = get_revision(db_conn, page_id=page.id, revision=2)
    # 2026-01-03T11:30:00+00:00 stored as naive UTC.
    assert rev2.created.isoformat() == "2026-01-03T11:30:00"


def test_reserved_username_falls_back_to_secret_only(db_conn: Connection) -> None:
    owner_rows, _ = importer.import_bundle(db_conn, _bundle())

    site = _site_by_title(db_conn, "Bob")
    assert site.public_url is None
    assert site.secret_url  # still reachable via secret URL

    bob_row = next(row for row in owner_rows if row[0] == "bob@example.com")
    assert "reserved" in bob_row[2]


def test_unclaimed_page_becomes_standalone_unclaimed_site(db_conn: Connection) -> None:
    _, unclaimed = importer.import_bundle(db_conn, _bundle())
    assert unclaimed == 1

    # The orphan site has no title/email and stays unclaimed; its content is the home page.
    site = db_conn.execute(select(sites).where(sites.c.title.is_(None))).first()
    assert site is not None
    assert site.password is None  # unclaimed
    assert site.public_url is None

    home = _page(db_conn, site.id, "")
    latest = get_revision(db_conn, page_id=home.id)
    assert latest.content == "# Orphan"


def test_every_site_gets_a_design_row(db_conn: Connection) -> None:
    importer.import_bundle(db_conn, _bundle())

    site_ids = [r.id for r in db_conn.execute(select(sites.c.id)).all()]
    for site_id in site_ids:
        design = db_conn.execute(
            select(designs).where(designs.c.site_id == site_id)
        ).first()
        assert design is not None
