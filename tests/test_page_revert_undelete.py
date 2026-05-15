from __future__ import annotations

from collections.abc import Iterator

import pytest
from flask.testing import FlaskClient
from sqlalchemy import Engine

from jottit.auth import hash_password
from jottit.db import (
    claim_site,
    delete_page,
    get_page,
    get_revision,
    metadata,
    new_page,
    new_site,
    update_page,
)

APEX = "http://jottit.test/"


@pytest.fixture(autouse=True)
def _truncate(db_engine: Engine) -> Iterator[None]:
    yield
    with db_engine.begin() as conn:
        for table in reversed(metadata.sorted_tables):
            conn.execute(table.delete())


def _seed_site(
    db_engine: Engine,
    *,
    secret_url: str,
    public_url: str | None = None,
    security: str | None = None,
    password: str | None = None,
) -> int:
    with db_engine.begin() as conn:
        site_id = new_site(conn, content="v1", secret_url=secret_url, public_url=public_url)
        if password is not None:
            claim_site(
                conn,
                site_id=site_id,
                password_hash=hash_password(password),
                email="o@example.com",
                security=security or "private",
            )
    return site_id


def _sign_in(client: FlaskClient, *, base_url: str, site_id: int) -> None:
    with client.session_transaction(base_url=base_url) as sess:
        sess["signed_in_sites"] = [*sess.get("signed_in_sites", []), site_id]


# ---- revert ----


def test_revert_writes_new_revision_with_old_content(
    client: FlaskClient, db_engine: Engine
) -> None:
    site_id = _seed_site(db_engine, secret_url="r1", public_url="alpha")
    with db_engine.begin() as conn:
        page = get_page(conn, site_id=site_id, page_name="")
        assert page is not None
        update_page(conn, page_id=page.id, content="v2")
        update_page(conn, page_id=page.id, content="v3")

    response = client.post("/?m=revert", base_url="http://alpha.jottit.test/", data={"r": "1"})

    assert response.status_code == 303
    with db_engine.connect() as conn:
        page = get_page(conn, site_id=site_id, page_name="")
        assert page is not None
        latest = get_revision(conn, page_id=page.id)
        assert latest is not None
        assert latest.revision == 4
        assert latest.content == "v1"


def test_revert_to_current_content_is_noop(client: FlaskClient, db_engine: Engine) -> None:
    """If the target revision's content already matches latest, no new revision is created."""
    site_id = _seed_site(db_engine, secret_url="r2", public_url="beta")
    with db_engine.begin() as conn:
        page = get_page(conn, site_id=site_id, page_name="")
        assert page is not None
        update_page(conn, page_id=page.id, content="same")

    # Revision 2 has "same"; reverting to it shouldn't create revision 3.
    client.post("/?m=revert", base_url="http://beta.jottit.test/", data={"r": "2"})

    with db_engine.connect() as conn:
        page = get_page(conn, site_id=site_id, page_name="")
        assert page is not None
        latest = get_revision(conn, page_id=page.id)
        assert latest is not None
        assert latest.revision == 2


def test_revert_undeletes_a_deleted_page(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_site(db_engine, secret_url="r3", public_url="gamma")
    with db_engine.begin() as conn:
        new_page(conn, site_id=site_id, name="notes", content="kept")
        page = get_page(conn, site_id=site_id, page_name="notes")
        assert page is not None
        delete_page(conn, page_id=page.id)

    client.post("/notes?m=revert", base_url="http://gamma.jottit.test/", data={"r": "1"})

    with db_engine.connect() as conn:
        page = get_page(conn, site_id=site_id, page_name="notes")
        assert page is not None
        assert page.deleted is False


def test_revert_missing_r_returns_400(client: FlaskClient, db_engine: Engine) -> None:
    _seed_site(db_engine, secret_url="r4", public_url="delta")

    response = client.post("/?m=revert", base_url="http://delta.jottit.test/", data={})

    assert response.status_code == 400


def test_revert_unknown_revision_returns_400(client: FlaskClient, db_engine: Engine) -> None:
    _seed_site(db_engine, secret_url="r5", public_url="epsilon")

    response = client.post("/?m=revert", base_url="http://epsilon.jottit.test/", data={"r": "99"})

    assert response.status_code == 400


def test_revert_unknown_page_returns_400(client: FlaskClient, db_engine: Engine) -> None:
    _seed_site(db_engine, secret_url="r6", public_url="zeta")

    response = client.post(
        "/no-such-page?m=revert", base_url="http://zeta.jottit.test/", data={"r": "1"}
    )

    assert response.status_code == 400


def test_revert_redirects_to_page(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_site(db_engine, secret_url="r7", public_url="eta")
    with db_engine.begin() as conn:
        new_page(conn, site_id=site_id, name="notes", content="x")
        page = get_page(conn, site_id=site_id, page_name="notes")
        assert page is not None
        update_page(conn, page_id=page.id, content="y")

    response = client.post("/notes?m=revert", base_url="http://eta.jottit.test/", data={"r": "1"})

    assert response.status_code == 303
    assert response.headers["Location"] == "/notes"


# ---- undelete ----


def test_undelete_restores_deleted_page_content(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_site(db_engine, secret_url="u1", public_url="theta")
    with db_engine.begin() as conn:
        new_page(conn, site_id=site_id, name="notes", content="alive")
        page = get_page(conn, site_id=site_id, page_name="notes")
        assert page is not None
        delete_page(conn, page_id=page.id)

    response = client.post("/notes?m=undelete", base_url="http://theta.jottit.test/")

    assert response.status_code == 303
    with db_engine.connect() as conn:
        page = get_page(conn, site_id=site_id, page_name="notes")
        assert page is not None
        assert page.deleted is False
        latest = get_revision(conn, page_id=page.id)
        assert latest is not None
        assert latest.content == "alive"
        assert latest.changes == "<em>Delete undone.</em>"


def test_undelete_unknown_page_returns_400(client: FlaskClient, db_engine: Engine) -> None:
    _seed_site(db_engine, secret_url="u2", public_url="iota")

    response = client.post("/no-such-page?m=undelete", base_url="http://iota.jottit.test/")

    assert response.status_code == 400


# ---- Auth gating ----


def test_revert_returns_401_anonymous_on_private(client: FlaskClient, db_engine: Engine) -> None:
    _seed_site(
        db_engine, secret_url="u3", public_url="kappa", security="private", password="hunter2"
    )

    response = client.post("/?m=revert", base_url="http://kappa.jottit.test/", data={"r": "1"})

    assert response.status_code == 401


def test_revert_succeeds_anonymously_on_open_site(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_site(
        db_engine, secret_url="u4", public_url="lambda", security="open", password="hunter2"
    )
    with db_engine.begin() as conn:
        page = get_page(conn, site_id=site_id, page_name="")
        assert page is not None
        update_page(conn, page_id=page.id, content="v2")

    response = client.post("/?m=revert", base_url="http://lambda.jottit.test/", data={"r": "1"})

    assert response.status_code == 303


def test_undelete_returns_401_anonymous_on_public(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_site(
        db_engine, secret_url="u5", public_url="mu", security="public", password="hunter2"
    )
    with db_engine.begin() as conn:
        new_page(conn, site_id=site_id, name="notes", content="x")
        page = get_page(conn, site_id=site_id, page_name="notes")
        assert page is not None
        delete_page(conn, page_id=page.id)

    response = client.post("/notes?m=undelete", base_url="http://mu.jottit.test/")

    assert response.status_code == 401


# ---- Secret-URL routing ----


def test_revert_via_secret_url(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_site(db_engine, secret_url="abc12")
    with db_engine.begin() as conn:
        page = get_page(conn, site_id=site_id, page_name="")
        assert page is not None
        update_page(conn, page_id=page.id, content="v2")

    response = client.post("/abc12/?m=revert", base_url=APEX, data={"r": "1"})

    assert response.status_code == 303
    assert response.headers["Location"] == "/abc12/"
