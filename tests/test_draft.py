from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from flask.testing import FlaskClient
from sqlalchemy import Connection, Engine, select

from jottit.db import (
    drafts,
    get_draft,
    get_page,
    metadata,
    new_draft,
    new_page,
    new_site,
)

APEX = "http://jottit.test/"


@pytest.fixture(autouse=True)
def _truncate_tables(db_engine: Engine) -> Iterator[None]:
    yield
    with db_engine.begin() as conn:
        for table in reversed(metadata.sorted_tables):
            conn.execute(table.delete())


# ---- db helpers ----


def test_new_draft_inserts_when_absent(db_conn: Connection) -> None:
    site_id = new_site(db_conn, content="hi", secret_url="dr1")
    page = get_page(db_conn, site_id=site_id, page_name="")
    assert page is not None

    new_draft(db_conn, page_id=page.id, content="wip")

    draft = get_draft(db_conn, page_id=page.id)
    assert draft is not None
    assert draft.content == "wip"


def test_new_draft_updates_when_present(db_conn: Connection) -> None:
    site_id = new_site(db_conn, content="hi", secret_url="dr2")
    page = get_page(db_conn, site_id=site_id, page_name="")
    assert page is not None

    new_draft(db_conn, page_id=page.id, content="first")
    new_draft(db_conn, page_id=page.id, content="second")

    rows = db_conn.execute(select(drafts).where(drafts.c.page_id == page.id)).all()
    assert len(rows) == 1
    assert rows[0].content == "second"


def test_get_draft_returns_none_when_absent(db_conn: Connection) -> None:
    site_id = new_site(db_conn, content="hi", secret_url="dr3")
    page = get_page(db_conn, site_id=site_id, page_name="")
    assert page is not None

    assert get_draft(db_conn, page_id=page.id) is None


# ---- /draft/save ----


def test_draft_save_creates_draft(client: FlaskClient, db_engine: Engine) -> None:
    with db_engine.begin() as conn:
        site_id = new_site(conn, content="hi", secret_url="ds1", public_url="alpha")

    response = client.post(
        "/draft/save",
        base_url="http://alpha.jottit.test/",
        data={"page_name": "", "content": "draft body"},
    )

    assert response.status_code == 204
    with db_engine.connect() as conn:
        page = get_page(conn, site_id=site_id, page_name="")
        assert page is not None
        draft = get_draft(conn, page_id=page.id)
        assert draft is not None
        assert draft.content == "draft body"


def test_draft_save_for_missing_page_is_noop(client: FlaskClient, db_engine: Engine) -> None:
    with db_engine.begin() as conn:
        new_site(conn, content="hi", secret_url="ds2", public_url="beta")

    response = client.post(
        "/draft/save",
        base_url="http://beta.jottit.test/",
        data={"page_name": "no-such-page", "content": "lost"},
    )

    assert response.status_code == 204


# ---- /draft/cancel ----


def test_draft_cancel_removes_draft_and_records_caret_pos(
    client: FlaskClient, db_engine: Engine
) -> None:
    with db_engine.begin() as conn:
        site_id = new_site(conn, content="hi", secret_url="dc1", public_url="gamma")
        page = get_page(conn, site_id=site_id, page_name="")
        assert page is not None
        new_draft(conn, page_id=page.id, content="abandon")

    response = client.post(
        "/draft/cancel",
        base_url="http://gamma.jottit.test/",
        data={"page_name": "", "scroll_pos": "300", "caret_pos": "50"},
    )

    assert response.status_code == 204
    with db_engine.connect() as conn:
        page = get_page(conn, site_id=site_id, page_name="")
        assert page is not None
        assert get_draft(conn, page_id=page.id) is None
        assert page.scroll_pos == 300
        assert page.caret_pos == 50


# ---- /draft/recover-live-version ----


def test_draft_recover_returns_latest_revision_and_clears_draft(
    client: FlaskClient, db_engine: Engine
) -> None:
    with db_engine.begin() as conn:
        site_id = new_site(conn, content="live content", secret_url="dr4", public_url="delta")
        page = get_page(conn, site_id=site_id, page_name="")
        assert page is not None
        new_draft(conn, page_id=page.id, content="some draft")

    response = client.post(
        "/draft/recover-live-version",
        base_url="http://delta.jottit.test/",
        data={"page_name": ""},
    )

    assert response.status_code == 200
    payload = json.loads(response.data)
    assert payload["content"] == "live content"

    with db_engine.connect() as conn:
        page = get_page(conn, site_id=site_id, page_name="")
        assert page is not None
        assert get_draft(conn, page_id=page.id) is None


def test_draft_recover_for_missing_page_returns_empty_content(
    client: FlaskClient, db_engine: Engine
) -> None:
    with db_engine.begin() as conn:
        new_site(conn, content="hi", secret_url="dr5", public_url="epsilon")

    response = client.post(
        "/draft/recover-live-version",
        base_url="http://epsilon.jottit.test/",
        data={"page_name": "nope"},
    )

    assert response.status_code == 200
    assert json.loads(response.data) == {"content": ""}


# ---- edit form loads draft ----


def test_edit_form_prefers_draft_over_revision_content(
    client: FlaskClient, db_engine: Engine
) -> None:
    with db_engine.begin() as conn:
        site_id = new_site(
            conn, content="seeded-revision-text", secret_url="ed1", public_url="zeta"
        )
        page = get_page(conn, site_id=site_id, page_name="")
        assert page is not None
        new_draft(conn, page_id=page.id, content="in-flight draft text")

    response = client.get("/?m=edit", base_url="http://zeta.jottit.test/")

    assert response.status_code == 200
    body = response.data.decode()
    assert "in-flight draft text" in body
    assert "seeded-revision-text" not in body


# ---- POST ?m=current_revision ----


def test_current_revision_returns_latest_revision_number(
    client: FlaskClient, db_engine: Engine
) -> None:
    with db_engine.begin() as conn:
        site_id = new_site(conn, content="v1", secret_url="cr1", public_url="eta")
        new_page(conn, site_id=site_id, name="notes", content="notes v1")

    response = client.post(
        "/notes?m=current_revision",
        base_url="http://eta.jottit.test/",
    )

    assert response.status_code == 200
    assert json.loads(response.data) == {"revision": 1}


def test_current_revision_for_missing_page_returns_null(
    client: FlaskClient, db_engine: Engine
) -> None:
    with db_engine.begin() as conn:
        new_site(conn, content="hi", secret_url="cr2", public_url="theta")

    response = client.post(
        "/no-such-page?m=current_revision",
        base_url="http://theta.jottit.test/",
    )

    assert response.status_code == 200
    assert json.loads(response.data) == {"revision": None}


# ---- secret-URL routing ----


def test_draft_save_under_secret_url(client: FlaskClient, db_engine: Engine) -> None:
    with db_engine.begin() as conn:
        site_id = new_site(conn, content="hi", secret_url="abc12")

    response = client.post(
        "/abc12/draft/save",
        base_url=APEX,
        data={"page_name": "", "content": "secret draft"},
    )

    assert response.status_code == 204
    with db_engine.connect() as conn:
        page = get_page(conn, site_id=site_id, page_name="")
        assert page is not None
        draft = get_draft(conn, page_id=page.id)
        assert draft is not None
        assert draft.content == "secret draft"
