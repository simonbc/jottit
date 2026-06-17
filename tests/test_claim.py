from __future__ import annotations

from collections.abc import Iterator

import pytest
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy import Engine

from jottit.auth import verify_password
from jottit.db import get_site, metadata, new_site
from jottit.mail import Outbox

APEX = "http://jottit.test/"


@pytest.fixture(autouse=True)
def _truncate_and_reset_outbox(db_engine: Engine, app: Flask) -> Iterator[None]:
    yield
    with db_engine.begin() as conn:
        for table in reversed(metadata.sorted_tables):
            conn.execute(table.delete())
    # Reset the outbox so leaked sends from one test don't bleed into the next.
    app.extensions.pop("outbox", None)


def _seed_site(db_engine: Engine, *, secret_url: str, public_url: str | None = None) -> int:
    with db_engine.begin() as conn:
        return new_site(conn, content="seed", secret_url=secret_url, public_url=public_url)


# ---- GET ----


def test_get_claim_renders_form_when_unclaimed(client: FlaskClient, db_engine: Engine) -> None:
    _seed_site(db_engine, secret_url="cl1", public_url="alpha")

    response = client.get("/site/claim", base_url="http://alpha.jottit.test/")

    assert response.status_code == 200
    body = response.data.decode()
    assert 'name="password"' in body
    assert 'name="email"' in body
    assert 'name="security"' in body


def test_get_claim_redirects_when_already_claimed(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_site(db_engine, secret_url="cl2", public_url="beta")
    with db_engine.begin() as conn:
        from jottit.db import claim_site as db_claim_site

        db_claim_site(
            conn,
            site_id=site_id,
            password_hash="$argon2id$existing",
            email="owner@example.com",
            security="private",
        )

    response = client.get("/site/claim", base_url="http://beta.jottit.test/")

    assert response.status_code == 303
    assert response.headers["Location"] == "/"


# ---- POST ----


def test_post_claim_hashes_password_and_stores_site_fields(
    client: FlaskClient, db_engine: Engine, app: Flask
) -> None:
    site_id = _seed_site(db_engine, secret_url="cl3", public_url="gamma")

    response = client.post(
        "/site/claim",
        base_url="http://gamma.jottit.test/",
        data={"password": "hunter2", "email": "owner@example.com", "security": "public"},
    )

    assert response.status_code == 303
    assert response.headers["Location"] == "/"

    with db_engine.connect() as conn:
        site = get_site(conn, site_id=site_id)
        assert site is not None
        assert site.password is not None
        assert site.password.startswith("$argon2")
        assert verify_password("hunter2", site.password)
        assert site.email == "owner@example.com"
        assert site.security == "public"


def test_post_claim_signs_user_in(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_site(db_engine, secret_url="cl4", public_url="delta")

    client.post(
        "/site/claim",
        base_url="http://delta.jottit.test/",
        data={"password": "hunter2", "email": "o@example.com", "security": "private"},
    )

    with client.session_transaction(base_url="http://delta.jottit.test/") as sess:
        assert site_id in sess["signed_in_sites"]


def test_post_claim_sends_welcome_email(client: FlaskClient, db_engine: Engine, app: Flask) -> None:
    _seed_site(db_engine, secret_url="cl5", public_url="epsilon")

    client.post(
        "/site/claim",
        base_url="http://epsilon.jottit.test/",
        data={"password": "hunter2", "email": "owner@example.com", "security": "private"},
    )

    outbox: Outbox = app.extensions["outbox"]
    assert len(outbox.sent) == 1
    msg = outbox.sent[0]
    assert msg.to == "owner@example.com"
    assert "claimed" in msg.subject.lower()


def test_post_claim_with_banner_password_prefills_full_form_without_error(
    client: FlaskClient, db_engine: Engine
) -> None:
    site_id = _seed_site(db_engine, secret_url="cl10", public_url="lambda")

    response = client.post(
        "/site/claim",
        base_url="http://lambda.jottit.test/",
        data={"from_banner": "1", "password": "hunter2"},
    )

    assert response.status_code == 200
    body = response.data.decode()
    assert 'name="email"' in body
    assert "Please enter a valid email address." not in body
    assert 'value="hunter2"' in body

    with db_engine.connect() as conn:
        site = get_site(conn, site_id=site_id)
        assert site is not None
        assert site.password is None


def test_post_claim_rejects_missing_password(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_site(db_engine, secret_url="cl6", public_url="zeta")

    response = client.post(
        "/site/claim",
        base_url="http://zeta.jottit.test/",
        data={"password": "", "email": "o@example.com", "security": "private"},
    )

    assert response.status_code == 400
    with db_engine.connect() as conn:
        site = get_site(conn, site_id=site_id)
        assert site is not None
        assert site.password is None


def test_post_claim_rejects_invalid_email(client: FlaskClient, db_engine: Engine) -> None:
    _seed_site(db_engine, secret_url="cl7", public_url="eta")

    response = client.post(
        "/site/claim",
        base_url="http://eta.jottit.test/",
        data={"password": "x", "email": "not-an-email", "security": "private"},
    )

    assert response.status_code == 400


def test_post_claim_rejects_invalid_security_level(client: FlaskClient, db_engine: Engine) -> None:
    _seed_site(db_engine, secret_url="cl8", public_url="theta")

    response = client.post(
        "/site/claim",
        base_url="http://theta.jottit.test/",
        data={"password": "x", "email": "o@example.com", "security": "superadmin"},
    )

    assert response.status_code == 400


def test_post_claim_when_already_claimed_redirects(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_site(db_engine, secret_url="cl9", public_url="iota")
    with db_engine.begin() as conn:
        from jottit.db import claim_site as db_claim_site

        db_claim_site(
            conn,
            site_id=site_id,
            password_hash="$argon2id$existing",
            email="orig@example.com",
            security="private",
        )

    response = client.post(
        "/site/claim",
        base_url="http://iota.jottit.test/",
        data={"password": "new-pw", "email": "new@example.com", "security": "open"},
    )

    assert response.status_code == 303
    # And the existing password/email are untouched.
    with db_engine.connect() as conn:
        site = get_site(conn, site_id=site_id)
        assert site is not None
        assert site.email == "orig@example.com"
        assert site.password == "$argon2id$existing"


# ---- secret URL routing ----


def test_claim_via_secret_url(client: FlaskClient, db_engine: Engine, app: Flask) -> None:
    site_id = _seed_site(db_engine, secret_url="abc12")

    response = client.post(
        "/abc12/site/claim",
        base_url=APEX,
        data={"password": "hunter2", "email": "o@example.com", "security": "private"},
    )

    assert response.status_code == 303
    assert response.headers["Location"] == "/abc12/"

    with db_engine.connect() as conn:
        site = get_site(conn, site_id=site_id)
        assert site is not None
        assert site.password is not None
