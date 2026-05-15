from __future__ import annotations

from collections.abc import Iterator

import pytest
from flask.testing import FlaskClient
from sqlalchemy import Engine

from jottit.auth import hash_password, verify_password
from jottit.db import claim_site, get_site, metadata, new_site

APEX = "http://jottit.test/"


@pytest.fixture(autouse=True)
def _truncate(db_engine: Engine) -> Iterator[None]:
    yield
    with db_engine.begin() as conn:
        for table in reversed(metadata.sorted_tables):
            conn.execute(table.delete())


def _seed_claimed_site(
    db_engine: Engine,
    *,
    secret_url: str,
    public_url: str | None = None,
    password: str = "current-pw",
) -> int:
    with db_engine.begin() as conn:
        site_id = new_site(conn, content="hi", secret_url=secret_url, public_url=public_url)
        claim_site(
            conn,
            site_id=site_id,
            password_hash=hash_password(password),
            email="owner@example.com",
            security="private",
        )
    return site_id


def _sign_in(client: FlaskClient, *, base_url: str, site_id: int) -> None:
    with client.session_transaction(base_url=base_url) as sess:
        sess["signed_in_sites"] = [*sess.get("signed_in_sites", []), site_id]


# ---- Auth gating ----


def test_get_redirects_when_anonymous(client: FlaskClient, db_engine: Engine) -> None:
    _seed_claimed_site(db_engine, secret_url="c1", public_url="alpha")

    response = client.get("/admin/change-password", base_url="http://alpha.jottit.test/")

    assert response.status_code == 303
    assert "site/signin" in response.headers["Location"]


def test_post_returns_401_when_anonymous(client: FlaskClient, db_engine: Engine) -> None:
    _seed_claimed_site(db_engine, secret_url="c2", public_url="beta")

    response = client.post(
        "/admin/change-password",
        base_url="http://beta.jottit.test/",
        data={"current_password": "current-pw", "new_password": "new-pw"},
    )

    assert response.status_code == 401


# ---- GET ----


def test_get_renders_form(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="c3", public_url="gamma")
    _sign_in(client, base_url="http://gamma.jottit.test/", site_id=site_id)

    response = client.get("/admin/change-password", base_url="http://gamma.jottit.test/")

    assert response.status_code == 200
    body = response.data.decode()
    assert 'name="current_password"' in body
    assert 'name="new_password"' in body


# ---- POST ----


def test_post_changes_password_when_current_correct(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="c4", public_url="delta")
    _sign_in(client, base_url="http://delta.jottit.test/", site_id=site_id)

    response = client.post(
        "/admin/change-password",
        base_url="http://delta.jottit.test/",
        data={"current_password": "current-pw", "new_password": "shiny-new"},
    )

    assert response.status_code == 303
    assert response.headers["Location"] == "/admin/settings"

    with db_engine.connect() as conn:
        row = get_site(conn, site_id=site_id)
        assert row is not None
        assert verify_password("shiny-new", row.password)
        assert not verify_password("current-pw", row.password)


def test_post_rejects_wrong_current_password(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="c5", public_url="epsilon")
    _sign_in(client, base_url="http://epsilon.jottit.test/", site_id=site_id)

    response = client.post(
        "/admin/change-password",
        base_url="http://epsilon.jottit.test/",
        data={"current_password": "WRONG", "new_password": "shiny-new"},
    )

    assert response.status_code == 401
    with db_engine.connect() as conn:
        row = get_site(conn, site_id=site_id)
        assert row is not None
        # Password unchanged.
        assert verify_password("current-pw", row.password)


def test_post_rejects_empty_new_password(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="c6", public_url="zeta")
    _sign_in(client, base_url="http://zeta.jottit.test/", site_id=site_id)

    response = client.post(
        "/admin/change-password",
        base_url="http://zeta.jottit.test/",
        data={"current_password": "current-pw", "new_password": ""},
    )

    assert response.status_code == 400
    with db_engine.connect() as conn:
        row = get_site(conn, site_id=site_id)
        assert row is not None
        assert verify_password("current-pw", row.password)


def test_post_keeps_user_signed_in(client: FlaskClient, db_engine: Engine) -> None:
    """Sessions are keyed by site_id, not password — a password change shouldn't bump the user out."""
    site_id = _seed_claimed_site(db_engine, secret_url="c7", public_url="eta")
    _sign_in(client, base_url="http://eta.jottit.test/", site_id=site_id)

    client.post(
        "/admin/change-password",
        base_url="http://eta.jottit.test/",
        data={"current_password": "current-pw", "new_password": "next-pw"},
    )

    with client.session_transaction(base_url="http://eta.jottit.test/") as sess:
        assert site_id in sess["signed_in_sites"]


# ---- Secret-URL routing ----


def test_change_password_via_secret_url(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="abc12")
    _sign_in(client, base_url=APEX, site_id=site_id)

    response = client.post(
        "/abc12/admin/change-password",
        base_url=APEX,
        data={"current_password": "current-pw", "new_password": "next-pw"},
    )

    assert response.status_code == 303
    assert response.headers["Location"] == "/abc12/admin/settings"
