from __future__ import annotations

from collections.abc import Iterator

import pytest
from flask.testing import FlaskClient
from sqlalchemy import Engine

from jottit.db import delete_page, get_page, metadata, new_page, new_site, update_page

APEX = "http://jottit.test/"


@pytest.fixture(autouse=True)
def _truncate_tables(db_engine: Engine) -> Iterator[None]:
    """Each test starts against a clean DB; page-view tests commit through the engine."""
    yield
    with db_engine.begin() as conn:
        for table in reversed(metadata.sorted_tables):
            conn.execute(table.delete())


def _seed_site(
    db_engine: Engine, *, secret_url: str, public_url: str | None = None, content: str = "hello"
) -> int:
    with db_engine.begin() as conn:
        return new_site(conn, content=content, secret_url=secret_url, public_url=public_url)


# ---- subdomain routes ----


def test_home_on_public_subdomain_renders_latest_revision(
    client: FlaskClient, db_engine: Engine
) -> None:
    _seed_site(db_engine, secret_url="s1", public_url="alpha", content="**hi there**")

    response = client.get("/", base_url="http://alpha.jottit.test/")

    assert response.status_code == 200
    body = response.data.decode()
    assert "<strong>hi there</strong>" in body
    assert "Revision 1" in body


def test_named_page_renders_content(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_site(db_engine, secret_url="s2", public_url="beta")
    with db_engine.begin() as conn:
        new_page(conn, site_id=site_id, name="notes", content="# Notebook")

    response = client.get("/notes", base_url="http://beta.jottit.test/")

    assert response.status_code == 200
    assert "<h1>Notebook</h1>" in response.data.decode()


def test_missing_page_returns_404_with_template(client: FlaskClient, db_engine: Engine) -> None:
    _seed_site(db_engine, secret_url="s3", public_url="gamma")

    response = client.get("/no-such-page", base_url="http://gamma.jottit.test/")

    assert response.status_code == 404
    assert "no-such-page" in response.data.decode()


def test_deleted_page_returns_410_without_revision_param(
    client: FlaskClient, db_engine: Engine
) -> None:
    site_id = _seed_site(db_engine, secret_url="s4", public_url="delta")
    with db_engine.begin() as conn:
        new_page(conn, site_id=site_id, name="gone", content="bye")
        page = get_page(conn, site_id=site_id, page_name="gone")
        assert page is not None
        delete_page(conn, page_id=page.id)

    response = client.get("/gone", base_url="http://delta.jottit.test/")

    assert response.status_code == 410
    assert "deleted" in response.data.decode().lower()


def test_deleted_page_serves_specific_revision_when_requested(
    client: FlaskClient, db_engine: Engine
) -> None:
    site_id = _seed_site(db_engine, secret_url="s5", public_url="epsilon")
    with db_engine.begin() as conn:
        new_page(conn, site_id=site_id, name="ghost", content="original content")
        page = get_page(conn, site_id=site_id, page_name="ghost")
        assert page is not None
        delete_page(conn, page_id=page.id)

    response = client.get("/ghost?r=1", base_url="http://epsilon.jottit.test/")

    assert response.status_code == 200
    assert "original content" in response.data.decode()


def test_specific_revision_returns_that_revision(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_site(db_engine, secret_url="s6", public_url="zeta", content="v1")
    with db_engine.begin() as conn:
        page = get_page(conn, site_id=site_id, page_name="")
        assert page is not None
        update_page(conn, page_id=page.id, content="v2")

    r1 = client.get("/?r=1", base_url="http://zeta.jottit.test/")
    r2 = client.get("/?r=2", base_url="http://zeta.jottit.test/")

    assert "v1" in r1.data.decode()
    assert "v2" in r2.data.decode()


def test_unknown_revision_returns_404(client: FlaskClient, db_engine: Engine) -> None:
    _seed_site(db_engine, secret_url="s7", public_url="eta")

    response = client.get("/?r=99", base_url="http://eta.jottit.test/")

    assert response.status_code == 404


def test_request_for_unresolved_subdomain_returns_404(client: FlaskClient) -> None:
    # No site seeded — resolver leaves g.site=None, view aborts 404.
    response = client.get("/", base_url="http://nosite.jottit.test/")

    assert response.status_code == 404


# ---- secret-URL routes ----


def test_home_via_secret_url_renders(client: FlaskClient, db_engine: Engine) -> None:
    _seed_site(db_engine, secret_url="abc12", content="secret hello")

    response = client.get("/abc12/", base_url=APEX)

    assert response.status_code == 200
    assert "secret hello" in response.data.decode()


def test_wikilinks_resolve_against_secret_site_root(client: FlaskClient, db_engine: Engine) -> None:
    _seed_site(db_engine, secret_url="abc34", content="see [[Notes]]")

    response = client.get("/abc34/", base_url=APEX)

    assert response.status_code == 200
    assert 'href="/abc34/notes"' in response.data.decode()


def test_wikilinks_resolve_against_subdomain_root(client: FlaskClient, db_engine: Engine) -> None:
    _seed_site(db_engine, secret_url="s8", public_url="omega", content="see [[Notes]]")

    response = client.get("/", base_url="http://omega.jottit.test/")

    assert response.status_code == 200
    assert 'href="/notes"' in response.data.decode()
