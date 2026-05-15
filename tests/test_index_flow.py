from __future__ import annotations

from collections.abc import Iterator

import pytest
from flask.testing import FlaskClient
from sqlalchemy import Engine, select

from jottit.db import get_site, metadata, pages, revisions

APEX = "http://jottit.test/"


@pytest.fixture(autouse=True)
def _truncate_tables(db_engine: Engine) -> Iterator[None]:
    """Index POSTs commit; wipe tables between tests so each starts clean."""
    yield
    with db_engine.begin() as conn:
        for table in reversed(metadata.sorted_tables):
            conn.execute(table.delete())


def test_get_index_renders_html_form(client: FlaskClient) -> None:
    response = client.get("/", base_url=APEX)
    assert response.status_code == 200
    body = response.data.decode()
    assert "Jottit" in body
    assert "<form" in body
    assert 'name="content"' in body


def test_post_index_creates_site_and_redirects_to_secret_path(
    client: FlaskClient, db_engine: Engine
) -> None:
    response = client.post("/", base_url=APEX, data={"content": "hello world"})
    assert response.status_code == 303

    location = response.headers["Location"]
    assert location.startswith("/")
    assert location.endswith("/")

    slug = location.strip("/")
    assert slug

    with db_engine.connect() as conn:
        site = get_site(conn, secret_url=slug)
        assert site is not None
        page = conn.execute(select(pages).where(pages.c.site_id == site.id)).one()
        rev = conn.execute(select(revisions).where(revisions.c.page_id == page.id)).one()
        assert rev.content == "hello world"
        assert rev.revision == 1


def test_post_index_with_public_url_redirects_to_subdomain(
    client: FlaskClient, db_engine: Engine
) -> None:
    response = client.post("/", base_url=APEX, data={"content": "hi", "public_url": "myblog"})
    assert response.status_code == 303
    assert "myblog.jottit.test" in response.headers["Location"]

    with db_engine.connect() as conn:
        site = get_site(conn, public_url="myblog")
        assert site is not None


def test_post_index_uses_provided_secret_url(client: FlaskClient, db_engine: Engine) -> None:
    response = client.post("/", base_url=APEX, data={"content": "hi", "secret_url": "myslug"})
    assert response.status_code == 303
    assert response.headers["Location"] == "/myslug/"

    with db_engine.connect() as conn:
        site = get_site(conn, secret_url="myslug")
        assert site is not None


def test_post_index_stores_partner(client: FlaskClient, db_engine: Engine) -> None:
    response = client.post("/", base_url=APEX, data={"content": "hi", "partner": "aff-x"})
    slug = response.headers["Location"].strip("/")

    with db_engine.connect() as conn:
        site = get_site(conn, secret_url=slug)
        assert site is not None
        assert site.partner == "aff-x"


def test_post_index_with_empty_content_still_creates_site(
    client: FlaskClient, db_engine: Engine
) -> None:
    response = client.post("/", base_url=APEX, data={"content": ""})
    assert response.status_code == 303

    slug = response.headers["Location"].strip("/")
    with db_engine.connect() as conn:
        site = get_site(conn, secret_url=slug)
        assert site is not None
