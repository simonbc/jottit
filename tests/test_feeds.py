from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from flask.testing import FlaskClient
from sqlalchemy import Engine

from jottit.auth import hash_password
from jottit.db import claim_site, get_page, metadata, new_page, new_site, update_page

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
        site_id = new_site(conn, content="hi", secret_url=secret_url, public_url=public_url)
        if password is not None:
            claim_site(
                conn,
                site_id=site_id,
                password_hash=hash_password(password),
                email="o@example.com",
                security=security or "private",
            )
    return site_id


# ---- /<page>?m=history_rss ----


def test_history_rss_returns_rss(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_site(db_engine, secret_url="hf1", public_url="alpha")
    with db_engine.begin() as conn:
        page = get_page(conn, site_id=site_id, page_name="")
        assert page is not None
        update_page(conn, page_id=page.id, content="v2")

    response = client.get("/?m=history_rss", base_url="http://alpha.jottit.test/")

    assert response.status_code == 200
    assert response.mimetype == "application/rss+xml"
    body = response.data.decode()
    assert "<rss" in body
    assert "<title>Revision 2</title>" in body
    assert "<title>Revision 1</title>" in body
    # Self-link uses an absolute URL pointing at this feed.
    assert "?m=history_rss" in body


# ---- /<page>?m=history_json ----


def test_history_json_returns_jsonfeed(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_site(db_engine, secret_url="hf2", public_url="beta")
    with db_engine.begin() as conn:
        page = get_page(conn, site_id=site_id, page_name="")
        assert page is not None
        update_page(conn, page_id=page.id, content="v2")

    response = client.get("/?m=history_json", base_url="http://beta.jottit.test/")

    assert response.status_code == 200
    assert response.mimetype == "application/feed+json"
    payload = json.loads(response.data)
    assert payload["version"].startswith("https://jsonfeed.org/version/")
    assert len(payload["items"]) == 2
    assert payload["items"][0]["title"] == "Revision 2"
    assert payload["items"][1]["title"] == "Revision 1"
    assert payload["items"][0]["url"].endswith("?r=2")


# ---- /site/changes.rss ----


def test_site_changes_rss(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_site(db_engine, secret_url="cf1", public_url="gamma")
    with db_engine.begin() as conn:
        new_page(conn, site_id=site_id, name="notes", content="notes body")

    response = client.get("/site/changes.rss", base_url="http://gamma.jottit.test/")

    assert response.status_code == 200
    assert response.mimetype == "application/rss+xml"
    body = response.data.decode()
    assert "<rss" in body
    assert "notes" in body


# ---- /site/changes.json ----


def test_site_changes_json(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_site(db_engine, secret_url="cf2", public_url="delta")
    with db_engine.begin() as conn:
        new_page(conn, site_id=site_id, name="notes", content="notes body")

    response = client.get("/site/changes.json", base_url="http://delta.jottit.test/")

    assert response.status_code == 200
    assert response.mimetype == "application/feed+json"
    payload = json.loads(response.data)
    assert payload["version"].startswith("https://jsonfeed.org/version/")
    item_urls = [item["url"] for item in payload["items"]]
    assert any("notes" in url for url in item_urls)


# ---- Auth: private gates feeds; public/open allow them ----


def test_feeds_on_private_site_redirect_to_signin(client: FlaskClient, db_engine: Engine) -> None:
    _seed_site(
        db_engine, secret_url="cf3", public_url="epsilon", security="private", password="hunter2"
    )

    response = client.get("/site/changes.rss", base_url="http://epsilon.jottit.test/")

    assert response.status_code == 303
    assert "site/signin" in response.headers["Location"]


def test_feeds_on_public_site_allowed_anonymously(client: FlaskClient, db_engine: Engine) -> None:
    _seed_site(
        db_engine, secret_url="cf4", public_url="zeta", security="public", password="hunter2"
    )

    rss = client.get("/site/changes.rss", base_url="http://zeta.jottit.test/")
    js = client.get("/site/changes.json", base_url="http://zeta.jottit.test/")

    assert rss.status_code == 200
    assert js.status_code == 200


def test_history_feeds_on_public_site_allowed_anonymously(
    client: FlaskClient, db_engine: Engine
) -> None:
    _seed_site(db_engine, secret_url="cf5", public_url="eta", security="public", password="hunter2")

    rss = client.get("/?m=history_rss", base_url="http://eta.jottit.test/")
    js = client.get("/?m=history_json", base_url="http://eta.jottit.test/")

    assert rss.status_code == 200
    assert js.status_code == 200


# ---- Secret-URL routing ----


def test_changes_rss_via_secret_url(client: FlaskClient, db_engine: Engine) -> None:
    _seed_site(db_engine, secret_url="abc12")

    response = client.get("/abc12/site/changes.rss", base_url=APEX)

    assert response.status_code == 200
    body = response.data.decode()
    # Self-link points at the secret URL.
    assert "/abc12/site/changes.rss" in body


def test_history_json_via_secret_url(client: FlaskClient, db_engine: Engine) -> None:
    _seed_site(db_engine, secret_url="abc34")

    response = client.get("/abc34/?m=history_json", base_url=APEX)

    assert response.status_code == 200
    payload = json.loads(response.data)
    assert payload["home_page_url"].endswith("/abc34/")
