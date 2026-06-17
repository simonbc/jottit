from __future__ import annotations

from collections.abc import Iterator

import pytest
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy import Engine

from jottit.auth import hash_password
from jottit.db import claim_site, get_site, metadata, new_site, update_site
from jottit.mail import Outbox

APEX = "http://jottit.test/"


@pytest.fixture(autouse=True)
def _truncate(db_engine: Engine, app: Flask) -> Iterator[None]:
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


def _seed_email_only_site(
    db_engine: Engine,
    *,
    secret_url: str,
    public_url: str | None = None,
    email: str = "owner@example.com",
    security: str = "private",
) -> int:
    with db_engine.begin() as conn:
        site_id = new_site(conn, content="hi", secret_url=secret_url, public_url=public_url)
        update_site(conn, site_id=site_id, email=email, security=security)
    return site_id


# ---- GET /site/signin ----


def test_get_signin_renders_form(client: FlaskClient, db_engine: Engine) -> None:
    _seed_claimed_site(db_engine, secret_url="s1", public_url="alpha")

    response = client.get("/site/signin", base_url="http://alpha.jottit.test/")

    assert response.status_code == 200
    body = response.data.decode()
    assert 'name="password"' in body
    assert 'name="return_to"' in body
    assert "/site/signin/email" in body


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


def test_post_signin_email_stores_code_and_sends_email(
    client: FlaskClient, db_engine: Engine, app: Flask
) -> None:
    site_id = _seed_claimed_site(
        db_engine,
        secret_url="em1",
        public_url="mu",
        email="owner@example.com",
    )

    response = client.post(
        "/site/signin/email",
        base_url="http://mu.jottit.test/",
        data={"email": "owner@example.com", "return_to": "notes"},
    )

    assert response.status_code == 200
    body = response.data.decode()
    assert "emailed a sign-in code" in body
    assert "/site/signin/verify" in body

    with db_engine.connect() as conn:
        site = get_site(conn, site_id=site_id)
        assert site is not None
        assert site.signin_code is not None
        assert len(site.signin_code) == 6
        assert site.signin_code_expires is not None

    outbox: Outbox = app.extensions["outbox"]
    assert len(outbox.sent) == 1
    msg = outbox.sent[0]
    assert msg.to == "owner@example.com"
    assert site.signin_code in msg.body
    assert "site/signin/verify" in msg.body


def test_post_signin_email_does_not_send_for_wrong_email(
    client: FlaskClient, db_engine: Engine, app: Flask
) -> None:
    site_id = _seed_claimed_site(
        db_engine,
        secret_url="em2",
        public_url="nu",
        email="owner@example.com",
    )

    response = client.post(
        "/site/signin/email",
        base_url="http://nu.jottit.test/",
        data={"email": "wrong@example.com", "return_to": ""},
    )

    assert response.status_code == 200
    assert "emailed a sign-in code" in response.data.decode()
    assert "outbox" not in app.extensions
    with db_engine.connect() as conn:
        site = get_site(conn, site_id=site_id)
        assert site is not None
        assert site.signin_code is None


def test_post_signin_email_requires_email(client: FlaskClient, db_engine: Engine) -> None:
    _seed_claimed_site(db_engine, secret_url="em3", public_url="xi")

    response = client.post(
        "/site/signin/email",
        base_url="http://xi.jottit.test/",
        data={"email": "", "return_to": ""},
    )

    assert response.status_code == 400
    assert "Please enter the email" in response.data.decode()


def test_email_only_site_signin_redirects_to_email_form(
    client: FlaskClient, db_engine: Engine
) -> None:
    _seed_email_only_site(db_engine, secret_url="eo1", public_url="sigma")

    response = client.get("/site/signin", base_url="http://sigma.jottit.test/")

    assert response.status_code == 303
    assert response.headers["Location"] == "/site/signin/email?return_to="

    response = client.get("/site/signin/email", base_url="http://sigma.jottit.test/")

    assert response.status_code == 200
    body = response.data.decode()
    assert 'name="email"' in body
    assert 'name="password"' not in body


def test_email_only_site_can_sign_in_with_code(
    client: FlaskClient, db_engine: Engine
) -> None:
    site_id = _seed_email_only_site(
        db_engine,
        secret_url="eo2",
        public_url="tau",
        email="owner@example.com",
    )

    client.post(
        "/site/signin/email",
        base_url="http://tau.jottit.test/",
        data={"email": "owner@example.com", "return_to": ""},
    )
    with db_engine.connect() as conn:
        site = get_site(conn, site_id=site_id)
        assert site is not None
        code = site.signin_code

    response = client.post(
        "/site/signin/verify",
        base_url="http://tau.jottit.test/",
        data={"code": code, "return_to": ""},
    )

    assert response.status_code == 303
    assert response.headers["Location"] == "/"
    with client.session_transaction(base_url="http://tau.jottit.test/") as sess:
        assert site_id in sess["signed_in_sites"]


def test_get_signin_verify_renders_form(client: FlaskClient, db_engine: Engine) -> None:
    _seed_claimed_site(db_engine, secret_url="em4", public_url="omicron")

    response = client.get(
        "/site/signin/verify?return_to=notes&email=o%40example.com",
        base_url="http://omicron.jottit.test/",
    )

    assert response.status_code == 200
    body = response.data.decode()
    assert 'name="code"' in body
    assert 'value="notes"' in body
    assert 'value="o@example.com"' in body


def test_post_signin_verify_with_valid_code_signs_in_and_consumes_code(
    client: FlaskClient, db_engine: Engine
) -> None:
    site_id = _seed_claimed_site(
        db_engine,
        secret_url="em5",
        public_url="pi",
        email="owner@example.com",
    )
    client.post(
        "/site/signin/email",
        base_url="http://pi.jottit.test/",
        data={"email": "owner@example.com", "return_to": "notes"},
    )
    with db_engine.connect() as conn:
        site = get_site(conn, site_id=site_id)
        assert site is not None
        code = site.signin_code

    response = client.post(
        "/site/signin/verify",
        base_url="http://pi.jottit.test/",
        data={"code": code, "return_to": "notes"},
    )

    assert response.status_code == 303
    assert response.headers["Location"] == "/notes"
    with client.session_transaction(base_url="http://pi.jottit.test/") as sess:
        assert site_id in sess["signed_in_sites"]
    with db_engine.connect() as conn:
        site = get_site(conn, site_id=site_id)
        assert site is not None
        assert site.signin_code is None
        assert site.signin_code_expires is None


def test_post_signin_verify_with_wrong_code_returns_401(
    client: FlaskClient, db_engine: Engine
) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="em6", public_url="rho")

    response = client.post(
        "/site/signin/verify",
        base_url="http://rho.jottit.test/",
        data={"code": "000000", "return_to": ""},
    )

    assert response.status_code == 401
    assert "invalid or expired" in response.data.decode()
    with client.session_transaction(base_url="http://rho.jottit.test/") as sess:
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


def test_signin_verify_via_secret_url(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_claimed_site(
        db_engine,
        secret_url="abc56",
        email="owner@example.com",
    )
    client.post(
        "/abc56/site/signin/email",
        base_url=APEX,
        data={"email": "owner@example.com", "return_to": "notes"},
    )
    with db_engine.connect() as conn:
        site = get_site(conn, site_id=site_id)
        assert site is not None
        code = site.signin_code

    response = client.post(
        "/abc56/site/signin/verify",
        base_url=APEX,
        data={"code": code, "return_to": "notes"},
    )

    assert response.status_code == 303
    assert response.headers["Location"] == "/abc56/notes"
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
