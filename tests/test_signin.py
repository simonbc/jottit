from __future__ import annotations

from collections.abc import Iterator

import pytest
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy import Engine

from jottit.auth import hash_password
from jottit.db import claim_site, metadata, new_site

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
    password: str = "hunter2",
    email: str = "o@example.com",
    security: str = "private",
) -> int:
    with db_engine.begin() as conn:
        site_id = new_site(conn, content="hi", secret_url=secret_url, public_url=public_url)
        claim_site(
            conn,
            site_id=site_id,
            password_hash=hash_password(password),
            email=email,
            security=security,
        )
    return site_id


# ---- GET /site/signin ----


def test_get_signin_renders_form(client: FlaskClient, db_engine: Engine) -> None:
    _seed_claimed_site(db_engine, secret_url="s1", public_url="alpha")

    response = client.get("/site/signin", base_url="http://alpha.jottit.test/")

    assert response.status_code == 200
    body = response.data.decode()
    assert 'name="password"' in body
    assert 'name="return_to"' in body


def test_get_signin_redirects_when_site_unclaimed(client: FlaskClient, db_engine: Engine) -> None:
    with db_engine.begin() as conn:
        new_site(conn, content="hi", secret_url="s2", public_url="beta")

    response = client.get("/site/signin", base_url="http://beta.jottit.test/")

    assert response.status_code == 303
    assert response.headers["Location"] == "/"


def test_get_signin_preserves_return_to_in_hidden_field(
    client: FlaskClient, db_engine: Engine
) -> None:
    _seed_claimed_site(db_engine, secret_url="s3", public_url="gamma")

    response = client.get("/site/signin?return_to=/notes", base_url="http://gamma.jottit.test/")

    assert response.status_code == 200
    assert 'value="notes"' in response.data.decode()


# ---- POST /site/signin ----


def test_post_signin_with_correct_password_signs_in_and_redirects(
    client: FlaskClient, db_engine: Engine
) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="s4", public_url="delta")

    response = client.post(
        "/site/signin",
        base_url="http://delta.jottit.test/",
        data={"password": "hunter2", "return_to": ""},
    )

    assert response.status_code == 303
    assert response.headers["Location"] == "/"

    with client.session_transaction(base_url="http://delta.jottit.test/") as sess:
        assert site_id in sess["signed_in_sites"]


def test_post_signin_redirects_to_return_to(client: FlaskClient, db_engine: Engine) -> None:
    _seed_claimed_site(db_engine, secret_url="s5", public_url="epsilon")

    response = client.post(
        "/site/signin",
        base_url="http://epsilon.jottit.test/",
        data={"password": "hunter2", "return_to": "notes"},
    )

    assert response.status_code == 303
    assert response.headers["Location"] == "/notes"


def test_post_signin_wrong_password_returns_401(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="s6", public_url="zeta")

    response = client.post(
        "/site/signin",
        base_url="http://zeta.jottit.test/",
        data={"password": "wrong", "return_to": ""},
    )

    assert response.status_code == 401
    body = response.data.decode()
    # Jinja escapes the apostrophe; match the rendered form.
    assert "doesn" in body and "match" in body

    with client.session_transaction(base_url="http://zeta.jottit.test/") as sess:
        assert site_id not in sess.get("signed_in_sites", [])


def test_post_signin_rejects_open_redirect_via_return_to(
    client: FlaskClient, db_engine: Engine
) -> None:
    _seed_claimed_site(db_engine, secret_url="s7", public_url="eta")

    response = client.post(
        "/site/signin",
        base_url="http://eta.jottit.test/",
        data={"password": "hunter2", "return_to": "//evil.com/"},
    )

    assert response.status_code == 303
    assert response.headers["Location"] == "/"


def test_post_signin_rejects_absolute_url_in_return_to(
    client: FlaskClient, db_engine: Engine
) -> None:
    _seed_claimed_site(db_engine, secret_url="s8", public_url="theta")

    response = client.post(
        "/site/signin",
        base_url="http://theta.jottit.test/",
        data={"password": "hunter2", "return_to": "https://evil.com/"},
    )

    assert response.status_code == 303
    assert response.headers["Location"] == "/"


# ---- POST /site/signout ----


def test_post_signout_clears_session_and_redirects(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="so1", public_url="iota")
    with client.session_transaction(base_url="http://iota.jottit.test/") as sess:
        sess["signed_in_sites"] = [site_id]

    response = client.post(
        "/site/signout",
        base_url="http://iota.jottit.test/",
        data={"return_to": ""},
    )

    assert response.status_code == 303
    assert response.headers["Location"] == "/"
    with client.session_transaction(base_url="http://iota.jottit.test/") as sess:
        assert site_id not in sess.get("signed_in_sites", [])


def test_post_signout_only_removes_current_site(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="so2", public_url="kappa")
    other_site_id = 999  # unrelated, simulates a second signed-in site
    with client.session_transaction(base_url="http://kappa.jottit.test/") as sess:
        sess["signed_in_sites"] = [site_id, other_site_id]

    client.post(
        "/site/signout",
        base_url="http://kappa.jottit.test/",
        data={"return_to": ""},
    )

    with client.session_transaction(base_url="http://kappa.jottit.test/") as sess:
        assert sess["signed_in_sites"] == [other_site_id]


def test_post_signout_honors_return_to(client: FlaskClient, db_engine: Engine) -> None:
    _seed_claimed_site(db_engine, secret_url="so3", public_url="lambda")

    response = client.post(
        "/site/signout",
        base_url="http://lambda.jottit.test/",
        data={"return_to": "about"},
    )

    assert response.status_code == 303
    assert response.headers["Location"] == "/about"


# ---- secret-URL routing ----


def test_signin_via_secret_url(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="abc12")

    response = client.post(
        "/abc12/site/signin",
        base_url=APEX,
        data={"password": "hunter2", "return_to": ""},
    )

    assert response.status_code == 303
    assert response.headers["Location"] == "/abc12/"

    with client.session_transaction(base_url=APEX) as sess:
        assert site_id in sess["signed_in_sites"]


def test_signout_via_secret_url_returns_to_secret_root(
    client: FlaskClient, db_engine: Engine, app: Flask
) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="abc34")
    with client.session_transaction(base_url=APEX) as sess:
        sess["signed_in_sites"] = [site_id]

    response = client.post(
        "/abc34/site/signout",
        base_url=APEX,
        data={"return_to": ""},
    )

    assert response.status_code == 303
    assert response.headers["Location"] == "/abc34/"
