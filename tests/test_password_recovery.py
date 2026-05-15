from __future__ import annotations

import re
from collections.abc import Iterator

import pytest
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy import Engine

from jottit.auth import hash_password, verify_password
from jottit.db import claim_site, get_site, metadata, new_site, set_change_pwd_token
from jottit.mail import Outbox

APEX = "http://jottit.test/"


@pytest.fixture(autouse=True)
def _truncate_and_reset_outbox(db_engine: Engine, app: Flask) -> Iterator[None]:
    yield
    with db_engine.begin() as conn:
        for table in reversed(metadata.sorted_tables):
            conn.execute(table.delete())
    app.extensions.pop("outbox", None)


def _seed_claimed_site(
    db_engine: Engine,
    *,
    secret_url: str,
    public_url: str | None = None,
    password: str = "hunter2",
    email: str = "owner@example.com",
) -> int:
    with db_engine.begin() as conn:
        site_id = new_site(conn, content="hi", secret_url=secret_url, public_url=public_url)
        claim_site(
            conn,
            site_id=site_id,
            password_hash=hash_password(password),
            email=email,
            security="private",
        )
    return site_id


# ---- GET /site/forgot-password ----


def test_get_forgot_password_renders_form(client: FlaskClient, db_engine: Engine) -> None:
    _seed_claimed_site(db_engine, secret_url="fp1", public_url="alpha")

    response = client.get("/site/forgot-password", base_url="http://alpha.jottit.test/")

    assert response.status_code == 200
    assert "Email me a reset link" in response.data.decode()


def test_get_forgot_password_redirects_when_unclaimed(
    client: FlaskClient, db_engine: Engine
) -> None:
    with db_engine.begin() as conn:
        new_site(conn, content="hi", secret_url="fp2", public_url="beta")

    response = client.get("/site/forgot-password", base_url="http://beta.jottit.test/")

    assert response.status_code == 303
    assert response.headers["Location"] == "/"


# ---- POST /site/forgot-password ----


def test_post_forgot_password_stores_token_and_sends_email(
    client: FlaskClient, db_engine: Engine, app: Flask
) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="fp3", public_url="gamma")

    response = client.post("/site/forgot-password", base_url="http://gamma.jottit.test/")

    assert response.status_code == 200
    body = response.data.decode()
    assert "emailed" in body.lower()

    with db_engine.connect() as conn:
        site = get_site(conn, site_id=site_id)
        assert site is not None
        assert site.change_pwd_token is not None
        assert len(site.change_pwd_token) >= 40

    outbox: Outbox = app.extensions["outbox"]
    assert len(outbox.sent) == 1
    msg = outbox.sent[0]
    assert msg.to == "owner@example.com"
    assert site.change_pwd_token in msg.body
    assert "site/change-password" in msg.body


def test_post_forgot_password_rotates_token_on_each_request(
    client: FlaskClient, db_engine: Engine
) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="fp4", public_url="delta")

    client.post("/site/forgot-password", base_url="http://delta.jottit.test/")
    with db_engine.connect() as conn:
        first = get_site(conn, site_id=site_id)
    assert first is not None
    first_token = first.change_pwd_token

    client.post("/site/forgot-password", base_url="http://delta.jottit.test/")
    with db_engine.connect() as conn:
        second = get_site(conn, site_id=site_id)
    assert second is not None

    assert first_token != second.change_pwd_token


# ---- GET /site/change-password ----


def test_get_change_password_with_valid_token_renders_form(
    client: FlaskClient, db_engine: Engine
) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="cp1", public_url="epsilon")
    with db_engine.begin() as conn:
        set_change_pwd_token(conn, site_id=site_id, token="valid-token")

    response = client.get(
        "/site/change-password?d=valid-token", base_url="http://epsilon.jottit.test/"
    )

    assert response.status_code == 200
    body = response.data.decode()
    assert 'name="new_password"' in body
    assert 'value="valid-token"' in body


def test_get_change_password_with_wrong_token_redirects_home(
    client: FlaskClient, db_engine: Engine
) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="cp2", public_url="zeta")
    with db_engine.begin() as conn:
        set_change_pwd_token(conn, site_id=site_id, token="real-token")

    response = client.get("/site/change-password?d=fake-token", base_url="http://zeta.jottit.test/")

    assert response.status_code == 303
    assert response.headers["Location"] == "/"


def test_get_change_password_with_no_token_stored_redirects_home(
    client: FlaskClient, db_engine: Engine
) -> None:
    _seed_claimed_site(db_engine, secret_url="cp3", public_url="eta")

    response = client.get("/site/change-password?d=anything", base_url="http://eta.jottit.test/")

    assert response.status_code == 303


# ---- POST /site/change-password ----


def test_post_change_password_sets_password_clears_token_signs_in(
    client: FlaskClient, db_engine: Engine
) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="cp4", public_url="theta")
    with db_engine.begin() as conn:
        set_change_pwd_token(conn, site_id=site_id, token="one-shot")

    response = client.post(
        "/site/change-password",
        base_url="http://theta.jottit.test/",
        data={"d": "one-shot", "new_password": "new-strong-pw"},
    )

    assert response.status_code == 303
    assert response.headers["Location"] == "/"

    with db_engine.connect() as conn:
        site = get_site(conn, site_id=site_id)
        assert site is not None
        assert site.change_pwd_token is None
        assert verify_password("new-strong-pw", site.password)

    with client.session_transaction(base_url="http://theta.jottit.test/") as sess:
        assert site_id in sess["signed_in_sites"]


def test_post_change_password_is_one_shot(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="cp5", public_url="iota")
    with db_engine.begin() as conn:
        set_change_pwd_token(conn, site_id=site_id, token="burn-after")

    # First use succeeds.
    client.post(
        "/site/change-password",
        base_url="http://iota.jottit.test/",
        data={"d": "burn-after", "new_password": "first-pw"},
    )
    # Reusing the same token now hits a "no stored token" path and redirects.
    response = client.post(
        "/site/change-password",
        base_url="http://iota.jottit.test/",
        data={"d": "burn-after", "new_password": "second-pw"},
    )

    assert response.status_code == 303
    with db_engine.connect() as conn:
        site = get_site(conn, site_id=site_id)
        assert site is not None
        # Password still reflects the first reset; second attempt didn't take.
        assert verify_password("first-pw", site.password)


def test_post_change_password_with_wrong_token_redirects(
    client: FlaskClient, db_engine: Engine
) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="cp6", public_url="kappa")
    with db_engine.begin() as conn:
        set_change_pwd_token(conn, site_id=site_id, token="real-token")

    response = client.post(
        "/site/change-password",
        base_url="http://kappa.jottit.test/",
        data={"d": "wrong-token", "new_password": "nope"},
    )

    assert response.status_code == 303
    with db_engine.connect() as conn:
        site = get_site(conn, site_id=site_id)
        assert site is not None
        # Original password and token untouched.
        assert verify_password("hunter2", site.password)
        assert site.change_pwd_token == "real-token"


def test_post_change_password_rejects_empty_password(
    client: FlaskClient, db_engine: Engine
) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="cp7", public_url="lambda")
    with db_engine.begin() as conn:
        set_change_pwd_token(conn, site_id=site_id, token="t")

    response = client.post(
        "/site/change-password",
        base_url="http://lambda.jottit.test/",
        data={"d": "t", "new_password": ""},
    )

    assert response.status_code == 400
    with db_engine.connect() as conn:
        site = get_site(conn, site_id=site_id)
        assert site is not None
        # Token is preserved so the user can retry.
        assert site.change_pwd_token == "t"


# ---- End-to-end recovery flow ----


def test_end_to_end_recovery_via_emailed_link(
    client: FlaskClient, db_engine: Engine, app: Flask
) -> None:
    """Walk through the full recovery: request reset, follow the emailed URL, set new password."""
    site_id = _seed_claimed_site(db_engine, secret_url="e2e", public_url="omega", password="old-pw")

    client.post("/site/forgot-password", base_url="http://omega.jottit.test/")
    body = app.extensions["outbox"].sent[0].body

    match = re.search(r"site/change-password\?d=(\S+)", body)
    assert match is not None
    token = match.group(1)

    response = client.post(
        "/site/change-password",
        base_url="http://omega.jottit.test/",
        data={"d": token, "new_password": "new-pw"},
    )

    assert response.status_code == 303
    with db_engine.connect() as conn:
        site = get_site(conn, site_id=site_id)
        assert site is not None
        assert verify_password("new-pw", site.password)
        assert not verify_password("old-pw", site.password)
