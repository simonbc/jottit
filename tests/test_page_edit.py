from __future__ import annotations

from collections.abc import Iterator

import pytest
from flask.testing import FlaskClient
from sqlalchemy import Engine

from jottit.db import get_page, get_revision, metadata, new_page, new_site

APEX = "http://jottit.test/"


@pytest.fixture(autouse=True)
def _truncate_tables(db_engine: Engine) -> Iterator[None]:
    yield
    with db_engine.begin() as conn:
        for table in reversed(metadata.sorted_tables):
            conn.execute(table.delete())


def _seed_site(db_engine: Engine, *, secret_url: str, public_url: str | None = None) -> int:
    with db_engine.begin() as conn:
        return new_site(conn, content="seed", secret_url=secret_url, public_url=public_url)


# ---- GET edit form ----


def test_get_edit_renders_form_with_current_content(
    client: FlaskClient, db_engine: Engine
) -> None:
    _seed_site(db_engine, secret_url="e1", public_url="alpha")

    response = client.get("/?m=edit", base_url="http://alpha.jottit.test/")

    assert response.status_code == 200
    body = response.data.decode()
    assert "<textarea" in body
    assert "seed" in body
    assert 'name="current_revision"' in body
    assert 'value="1"' in body


def test_get_edit_for_missing_page_renders_empty_form(
    client: FlaskClient, db_engine: Engine
) -> None:
    _seed_site(db_engine, secret_url="e2", public_url="beta")

    response = client.get("/new-page?m=edit", base_url="http://beta.jottit.test/")

    assert response.status_code == 200
    body = response.data.decode()
    assert "<textarea" in body
    assert 'value="0"' in body  # current_revision=0 for never-existed page


def test_get_edit_for_existing_page_named_page(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_site(db_engine, secret_url="e3", public_url="gamma")
    with db_engine.begin() as conn:
        new_page(conn, site_id=site_id, name="notes", content="original")

    response = client.get("/notes?m=edit", base_url="http://gamma.jottit.test/")

    assert response.status_code == 200
    body = response.data.decode()
    assert "original" in body


# ---- POST save (existing page) ----


def test_post_save_updates_existing_page_and_redirects(
    client: FlaskClient, db_engine: Engine
) -> None:
    site_id = _seed_site(db_engine, secret_url="e4", public_url="delta")

    response = client.post(
        "/",
        base_url="http://delta.jottit.test/",
        data={"content": "updated body"},
    )

    assert response.status_code == 303
    assert response.headers["Location"].endswith("/")

    with db_engine.connect() as conn:
        page = get_page(conn, site_id=site_id, page_name="")
        assert page is not None
        rev = get_revision(conn, page_id=page.id)
        assert rev is not None
        assert rev.content == "updated body"
        assert rev.revision == 2


def test_post_save_normalizes_crlf_to_lf(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_site(db_engine, secret_url="e5", public_url="epsilon")

    client.post(
        "/",
        base_url="http://epsilon.jottit.test/",
        data={"content": "line1\r\nline2\r\nline3"},
    )

    with db_engine.connect() as conn:
        page = get_page(conn, site_id=site_id, page_name="")
        assert page is not None
        rev = get_revision(conn, page_id=page.id)
        assert rev is not None
        assert "\r" not in rev.content
        assert rev.content == "line1\nline2\nline3"


def test_post_save_records_scroll_and_caret_pos(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_site(db_engine, secret_url="e6", public_url="zeta")

    client.post(
        "/",
        base_url="http://zeta.jottit.test/",
        data={"content": "changed", "scroll_pos": "200", "caret_pos": "12"},
    )

    with db_engine.connect() as conn:
        page = get_page(conn, site_id=site_id, page_name="")
        assert page is not None
        assert page.scroll_pos == 200
        assert page.caret_pos == 12


# ---- POST save (create-on-write) ----


def test_post_create_new_page_on_save(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_site(db_engine, secret_url="e7", public_url="eta")

    response = client.post(
        "/brand-new",
        base_url="http://eta.jottit.test/",
        data={"content": "first version"},
    )

    assert response.status_code == 303
    assert response.headers["Location"].endswith("/brand-new")

    with db_engine.connect() as conn:
        page = get_page(conn, site_id=site_id, page_name="brand-new")
        assert page is not None
        rev = get_revision(conn, page_id=page.id)
        assert rev is not None
        assert rev.content == "first version"
        assert rev.revision == 1


def test_post_create_via_secret_url_redirects_under_prefix(
    client: FlaskClient, db_engine: Engine
) -> None:
    _seed_site(db_engine, secret_url="abc12")

    response = client.post(
        "/abc12/notes",
        base_url=APEX,
        data={"content": "hi"},
    )

    assert response.status_code == 303
    assert response.headers["Location"] == "/abc12/notes"


# ---- POST delete ----


def test_post_delete_marks_page_deleted(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_site(db_engine, secret_url="e8", public_url="theta")
    with db_engine.begin() as conn:
        new_page(conn, site_id=site_id, name="gone", content="bye")

    response = client.post(
        "/gone",
        base_url="http://theta.jottit.test/",
        data={"content": "", "delete": "1"},
    )

    assert response.status_code == 303

    with db_engine.connect() as conn:
        page = get_page(conn, site_id=site_id, page_name="gone")
        assert page is not None
        assert page.deleted is True


def test_post_delete_on_home_is_ignored(client: FlaskClient, db_engine: Engine) -> None:
    """Home page can't be deleted — the original guarded on `if page_name`."""
    site_id = _seed_site(db_engine, secret_url="e9", public_url="iota")

    client.post(
        "/",
        base_url="http://iota.jottit.test/",
        data={"content": "still here", "delete": "1"},
    )

    with db_engine.connect() as conn:
        page = get_page(conn, site_id=site_id, page_name="")
        assert page is not None
        assert page.deleted is False
        # Treated as a normal save: content updated.
        rev = get_revision(conn, page_id=page.id)
        assert rev is not None
        assert rev.content == "still here"


def test_post_save_undeletes_when_deleted_page_is_edited(
    client: FlaskClient, db_engine: Engine
) -> None:
    site_id = _seed_site(db_engine, secret_url="e10", public_url="kappa")
    with db_engine.begin() as conn:
        new_page(conn, site_id=site_id, name="back", content="v1")
        page = get_page(conn, site_id=site_id, page_name="back")
        assert page is not None
        from jottit.db import delete_page

        delete_page(conn, page_id=page.id)

    response = client.post(
        "/back",
        base_url="http://kappa.jottit.test/",
        data={"content": "revived"},
    )

    assert response.status_code == 303

    with db_engine.connect() as conn:
        page = get_page(conn, site_id=site_id, page_name="back")
        assert page is not None
        assert page.deleted is False


# ---- Unresolved site ----


def test_post_to_unresolved_site_returns_404(client: FlaskClient) -> None:
    response = client.post(
        "/",
        base_url="http://nosite.jottit.test/",
        data={"content": "ignored"},
    )

    assert response.status_code == 404
