from __future__ import annotations

from collections.abc import Iterator

import pytest
from flask.testing import FlaskClient
from sqlalchemy import Engine

from jottit.auth import hash_password
from jottit.db import claim_site, get_site, metadata, new_site, update_site

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
    security: str = "private",
) -> int:
    with db_engine.begin() as conn:
        site_id = new_site(conn, content="hi", secret_url=secret_url, public_url=public_url)
        claim_site(
            conn,
            site_id=site_id,
            password_hash=hash_password("hunter2"),
            email="owner@example.com",
            security=security,
        )
    return site_id


def _sign_in(client: FlaskClient, *, base_url: str, site_id: int) -> None:
    with client.session_transaction(base_url=base_url) as sess:
        sess["signed_in_sites"] = [*sess.get("signed_in_sites", []), site_id]


# ---- Auth gating ----


def test_get_settings_redirects_when_anonymous(client: FlaskClient, db_engine: Engine) -> None:
    _seed_claimed_site(db_engine, secret_url="s1", public_url="alpha")

    response = client.get("/admin/settings", base_url="http://alpha.jottit.test/")

    assert response.status_code == 303
    assert "site/signin" in response.headers["Location"]


def test_post_settings_returns_401_when_anonymous(client: FlaskClient, db_engine: Engine) -> None:
    _seed_claimed_site(db_engine, secret_url="s2", public_url="beta")

    response = client.post(
        "/admin/settings",
        base_url="http://beta.jottit.test/",
        data={"title": "X", "subtitle": "Y", "email": "o@example.com", "security": "private"},
    )

    assert response.status_code == 401


# ---- GET ----


def test_get_settings_renders_form_with_current_values(
    client: FlaskClient, db_engine: Engine
) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="s3", public_url="gamma")
    with db_engine.begin() as conn:
        update_site(conn, site_id=site_id, title="My Site", subtitle="Of jottings", email="o@x.com")
    _sign_in(client, base_url="http://gamma.jottit.test/", site_id=site_id)

    response = client.get("/admin/settings", base_url="http://gamma.jottit.test/")

    assert response.status_code == 200
    body = response.data.decode()
    assert 'value="My Site"' in body
    assert 'value="Of jottings"' in body
    assert 'value="o@x.com"' in body


# ---- POST ----


def test_post_settings_updates_fields_and_redirects(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="s4", public_url="delta")
    _sign_in(client, base_url="http://delta.jottit.test/", site_id=site_id)

    response = client.post(
        "/admin/settings",
        base_url="http://delta.jottit.test/",
        data={
            "title": "New Title",
            "subtitle": "New Subtitle",
            "email": "new@example.com",
            "security": "public",
            "home_layout": "feed",
        },
    )

    assert response.status_code == 303
    assert response.headers["Location"] == "/"

    with db_engine.connect() as conn:
        row = get_site(conn, site_id=site_id)
        assert row is not None
        assert row.title == "New Title"
        assert row.subtitle == "New Subtitle"
        assert row.email == "new@example.com"
        assert row.security == "public"
        assert row.home_layout == "feed"


def test_post_settings_rejects_invalid_home_layout(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="s_hl", public_url="kappa")
    _sign_in(client, base_url="http://kappa.jottit.test/", site_id=site_id)

    response = client.post(
        "/admin/settings",
        base_url="http://kappa.jottit.test/",
        data={
            "title": "x",
            "subtitle": "y",
            "email": "",
            "security": "private",
            "home_layout": "wiki",
        },
    )

    assert response.status_code == 400
    with db_engine.connect() as conn:
        row = get_site(conn, site_id=site_id)
        assert row is not None
        assert row.home_layout == "page"


def test_get_settings_renders_home_layout_radios(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="s_hl2", public_url="lambda")
    _sign_in(client, base_url="http://lambda.jottit.test/", site_id=site_id)

    response = client.get("/admin/settings", base_url="http://lambda.jottit.test/")

    assert response.status_code == 200
    body = response.data.decode()
    assert 'name="home_layout"' in body
    assert 'value="page"' in body
    assert 'value="feed"' in body
    # Default is 'page' for a fresh site.
    assert 'value="page" checked' in body


def test_post_settings_rejects_invalid_email(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="s5", public_url="epsilon")
    _sign_in(client, base_url="http://epsilon.jottit.test/", site_id=site_id)

    response = client.post(
        "/admin/settings",
        base_url="http://epsilon.jottit.test/",
        data={
            "title": "x",
            "subtitle": "y",
            "email": "not-an-email",
            "security": "private",
        },
    )

    assert response.status_code == 400
    with db_engine.connect() as conn:
        row = get_site(conn, site_id=site_id)
        assert row is not None
        # Original values untouched.
        assert row.email == "owner@example.com"


def test_post_settings_rejects_invalid_security_level(
    client: FlaskClient, db_engine: Engine
) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="s6", public_url="zeta")
    _sign_in(client, base_url="http://zeta.jottit.test/", site_id=site_id)

    response = client.post(
        "/admin/settings",
        base_url="http://zeta.jottit.test/",
        data={"title": "x", "subtitle": "y", "email": "", "security": "superadmin"},
    )

    assert response.status_code == 400


def test_post_settings_allows_empty_email(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="s7", public_url="eta")
    _sign_in(client, base_url="http://eta.jottit.test/", site_id=site_id)

    response = client.post(
        "/admin/settings",
        base_url="http://eta.jottit.test/",
        data={"title": "x", "subtitle": "y", "email": "", "security": "private"},
    )

    assert response.status_code == 303
    with db_engine.connect() as conn:
        row = get_site(conn, site_id=site_id)
        assert row is not None
        assert row.email == ""


def test_post_settings_preserves_unrelated_fields(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="s8", public_url="theta")
    _sign_in(client, base_url="http://theta.jottit.test/", site_id=site_id)

    client.post(
        "/admin/settings",
        base_url="http://theta.jottit.test/",
        data={"title": "T", "subtitle": "S", "email": "n@example.com", "security": "public"},
    )

    with db_engine.connect() as conn:
        row = get_site(conn, site_id=site_id)
        assert row is not None
        # public_url is managed by /admin/change-site-address, not here.
        assert row.public_url == "theta"
        # Password is untouched.
        assert row.password is not None


# ---- Secret-URL routing ----


def test_admin_settings_via_secret_url(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="abc12")
    _sign_in(client, base_url=APEX, site_id=site_id)

    response = client.post(
        "/abc12/admin/settings",
        base_url=APEX,
        data={"title": "T", "subtitle": "S", "email": "o@example.com", "security": "open"},
    )

    assert response.status_code == 303
    assert response.headers["Location"] == "/abc12/"
    with db_engine.connect() as conn:
        row = get_site(conn, site_id=site_id)
        assert row is not None
        assert row.security == "open"
