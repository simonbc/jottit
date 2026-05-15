from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from flask.testing import FlaskClient
from sqlalchemy import Engine

from jottit.auth import hash_password
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
) -> int:
    with db_engine.begin() as conn:
        site_id = new_site(conn, content="hi", secret_url=secret_url, public_url=public_url)
        claim_site(
            conn,
            site_id=site_id,
            password_hash=hash_password("hunter2"),
            email="owner@example.com",
            security="private",
        )
    return site_id


def _sign_in(client: FlaskClient, *, base_url: str, site_id: int) -> None:
    with client.session_transaction(base_url=base_url) as sess:
        sess["signed_in_sites"] = [*sess.get("signed_in_sites", []), site_id]


# ---- Auth gating ----


def test_get_change_site_address_redirects_anonymous(
    client: FlaskClient, db_engine: Engine
) -> None:
    _seed_claimed_site(db_engine, secret_url="a1", public_url="alpha")

    response = client.get("/admin/change-site-address", base_url="http://alpha.jottit.test/")

    assert response.status_code == 303
    assert "site/signin" in response.headers["Location"]


def test_post_change_site_address_returns_401_anonymous(
    client: FlaskClient, db_engine: Engine
) -> None:
    _seed_claimed_site(db_engine, secret_url="a2", public_url="beta")

    response = client.post(
        "/admin/change-site-address",
        base_url="http://beta.jottit.test/",
        data={"public_url": "newbeta"},
    )

    assert response.status_code == 401


# ---- GET ----


def test_get_change_site_address_prefills_current_value(
    client: FlaskClient, db_engine: Engine
) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="a3", public_url="gamma")
    _sign_in(client, base_url="http://gamma.jottit.test/", site_id=site_id)

    response = client.get("/admin/change-site-address", base_url="http://gamma.jottit.test/")

    assert response.status_code == 200
    assert 'value="gamma"' in response.data.decode()


# ---- POST: change ----


def test_post_change_site_address_updates_and_redirects_to_new_subdomain(
    client: FlaskClient, db_engine: Engine
) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="a4", public_url="delta")
    _sign_in(client, base_url="http://delta.jottit.test/", site_id=site_id)

    response = client.post(
        "/admin/change-site-address",
        base_url="http://delta.jottit.test/",
        data={"public_url": "deltatwo"},
    )

    assert response.status_code == 303
    assert response.headers["Location"] == "http://deltatwo.jottit.test/admin/settings"

    with db_engine.connect() as conn:
        row = get_site(conn, site_id=site_id)
        assert row is not None
        assert row.public_url == "deltatwo"


def test_post_change_site_address_clearing_redirects_to_secret_url(
    client: FlaskClient, db_engine: Engine
) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="a5", public_url="epsilon")
    _sign_in(client, base_url="http://epsilon.jottit.test/", site_id=site_id)

    response = client.post(
        "/admin/change-site-address",
        base_url="http://epsilon.jottit.test/",
        data={"public_url": ""},
    )

    assert response.status_code == 303
    assert response.headers["Location"] == "http://jottit.test/a5/admin/settings"

    with db_engine.connect() as conn:
        row = get_site(conn, site_id=site_id)
        assert row is not None
        assert row.public_url is None


def test_post_change_site_address_same_value_is_noop_redirect(
    client: FlaskClient, db_engine: Engine
) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="a6", public_url="zeta")
    _sign_in(client, base_url="http://zeta.jottit.test/", site_id=site_id)

    response = client.post(
        "/admin/change-site-address",
        base_url="http://zeta.jottit.test/",
        data={"public_url": "zeta"},
    )

    assert response.status_code == 303
    assert response.headers["Location"] == "http://zeta.jottit.test/admin/settings"


def test_post_change_site_address_lowercases_and_trims(
    client: FlaskClient, db_engine: Engine
) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="a7", public_url="eta")
    _sign_in(client, base_url="http://eta.jottit.test/", site_id=site_id)

    response = client.post(
        "/admin/change-site-address",
        base_url="http://eta.jottit.test/",
        data={"public_url": "  ETA-TWO  "},
    )

    assert response.status_code == 303
    with db_engine.connect() as conn:
        row = get_site(conn, site_id=site_id)
        assert row is not None
        assert row.public_url == "eta-two"


# ---- POST: rejection ----


def test_post_change_site_address_rejects_invalid_chars(
    client: FlaskClient, db_engine: Engine
) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="a8", public_url="theta")
    _sign_in(client, base_url="http://theta.jottit.test/", site_id=site_id)

    response = client.post(
        "/admin/change-site-address",
        base_url="http://theta.jottit.test/",
        data={"public_url": "has spaces"},
    )

    assert response.status_code == 400
    with db_engine.connect() as conn:
        row = get_site(conn, site_id=site_id)
        assert row is not None
        assert row.public_url == "theta"


def test_post_change_site_address_rejects_taken_slug(
    client: FlaskClient, db_engine: Engine
) -> None:
    # Pre-seed another site that already owns "claimed".
    with db_engine.begin() as conn:
        new_site(conn, content="x", secret_url="other", public_url="claimed")
    site_id = _seed_claimed_site(db_engine, secret_url="a9", public_url="iota")
    _sign_in(client, base_url="http://iota.jottit.test/", site_id=site_id)

    response = client.post(
        "/admin/change-site-address",
        base_url="http://iota.jottit.test/",
        data={"public_url": "claimed"},
    )

    assert response.status_code == 400
    with db_engine.connect() as conn:
        row = get_site(conn, site_id=site_id)
        assert row is not None
        assert row.public_url == "iota"


def test_post_change_site_address_rejects_reserved_slug(
    client: FlaskClient, db_engine: Engine
) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="a10", public_url="kappa")
    _sign_in(client, base_url="http://kappa.jottit.test/", site_id=site_id)

    response = client.post(
        "/admin/change-site-address",
        base_url="http://kappa.jottit.test/",
        data={"public_url": "www"},
    )

    assert response.status_code == 400


# ---- /admin/url-available ----


def test_url_available_true_for_free_slug(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="ua1", public_url="lambda")
    _sign_in(client, base_url="http://lambda.jottit.test/", site_id=site_id)

    response = client.post(
        "/admin/url-available",
        base_url="http://lambda.jottit.test/",
        data={"url": "fresh-slug"},
    )

    assert response.status_code == 200
    assert json.loads(response.data) == {"available": True}


def test_url_available_false_for_taken_slug(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="ua2", public_url="mu")
    with db_engine.begin() as conn:
        new_site(conn, content="x", secret_url="ua2other", public_url="grabbed")
    _sign_in(client, base_url="http://mu.jottit.test/", site_id=site_id)

    response = client.post(
        "/admin/url-available",
        base_url="http://mu.jottit.test/",
        data={"url": "grabbed"},
    )

    assert json.loads(response.data) == {"available": False}


def test_url_available_false_for_reserved(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="ua3", public_url="nu")
    _sign_in(client, base_url="http://nu.jottit.test/", site_id=site_id)

    response = client.post(
        "/admin/url-available",
        base_url="http://nu.jottit.test/",
        data={"url": "www"},
    )

    assert json.loads(response.data) == {"available": False}


def test_url_available_false_for_invalid_chars(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="ua4", public_url="xi")
    _sign_in(client, base_url="http://xi.jottit.test/", site_id=site_id)

    response = client.post(
        "/admin/url-available",
        base_url="http://xi.jottit.test/",
        data={"url": "has spaces"},
    )

    assert json.loads(response.data) == {"available": False}


def test_url_available_false_for_empty(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="ua5", public_url="omicron")
    _sign_in(client, base_url="http://omicron.jottit.test/", site_id=site_id)

    response = client.post(
        "/admin/url-available",
        base_url="http://omicron.jottit.test/",
        data={"url": ""},
    )

    assert json.loads(response.data) == {"available": False}


def test_url_available_requires_auth(client: FlaskClient, db_engine: Engine) -> None:
    _seed_claimed_site(db_engine, secret_url="ua6", public_url="pi")

    response = client.post(
        "/admin/url-available",
        base_url="http://pi.jottit.test/",
        data={"url": "anything"},
    )

    assert response.status_code == 401


# ---- Secret-URL routing ----


def test_change_site_address_via_secret_url(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="abc12")
    _sign_in(client, base_url=APEX, site_id=site_id)

    response = client.post(
        "/abc12/admin/change-site-address",
        base_url=APEX,
        data={"public_url": "newpub"},
    )

    assert response.status_code == 303
    assert response.headers["Location"] == "http://newpub.jottit.test/admin/settings"
