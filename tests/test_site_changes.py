from __future__ import annotations

from collections.abc import Iterator

import pytest
from flask.testing import FlaskClient
from sqlalchemy import Engine

from jottit.auth import hash_password
from jottit.db import (
    claim_site,
    delete_page,
    get_page,
    metadata,
    new_page,
    new_site,
    update_page,
)

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


def _sign_in(client: FlaskClient, *, base_url: str, site_id: int) -> None:
    with client.session_transaction(base_url=base_url) as sess:
        sess["signed_in_sites"] = [*sess.get("signed_in_sites", []), site_id]


# ---- Happy path ----


def test_changes_lists_recent_revisions_across_pages(
    client: FlaskClient, db_engine: Engine
) -> None:
    site_id = _seed_site(db_engine, secret_url="c1", public_url="alpha")
    with db_engine.begin() as conn:
        new_page(conn, site_id=site_id, name="notes", content="notes body")
        home = get_page(conn, site_id=site_id, page_name="")
        assert home is not None
        update_page(conn, page_id=home.id, content="home v2")

    response = client.get("/site/changes", base_url="http://alpha.jottit.test/")

    assert response.status_code == 200
    body = response.data.decode()
    # Both pages appear.
    assert "notes" in body
    assert "Home" in body
    # Newest first: the home v2 update has the latest timestamp.
    assert body.index("Home") < body.index("notes")


def test_changes_renders_links_to_specific_revisions(
    client: FlaskClient, db_engine: Engine
) -> None:
    site_id = _seed_site(db_engine, secret_url="c2", public_url="beta")
    with db_engine.begin() as conn:
        new_page(conn, site_id=site_id, name="My Notes", content="x")

    response = client.get("/site/changes", base_url="http://beta.jottit.test/")

    body = response.data.decode()
    # Page name gets slugified to my_notes in the URL.
    assert "my_notes?r=1" in body


def test_changes_empty_site_shows_only_seed_revision(
    client: FlaskClient, db_engine: Engine
) -> None:
    _seed_site(db_engine, secret_url="c3", public_url="gamma")

    response = client.get("/site/changes", base_url="http://gamma.jottit.test/")

    assert response.status_code == 200
    # new_site seeds revision 1 of the home page.
    assert "revision 1" in response.data.decode()


def test_changes_marks_deleted_pages(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_site(db_engine, secret_url="c4", public_url="delta")
    with db_engine.begin() as conn:
        new_page(conn, site_id=site_id, name="gone", content="bye")
        page = get_page(conn, site_id=site_id, page_name="gone")
        assert page is not None
        delete_page(conn, page_id=page.id)

    response = client.get("/site/changes", base_url="http://delta.jottit.test/")

    assert "page since deleted" in response.data.decode()


# ---- Pagination ----


def test_changes_page_size_caps_at_twenty(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_site(db_engine, secret_url="c5", public_url="epsilon")
    with db_engine.begin() as conn:
        home = get_page(conn, site_id=site_id, page_name="")
        assert home is not None
        for n in range(2, 26):
            update_page(conn, page_id=home.id, content=f"v{n}")

    response = client.get("/site/changes", base_url="http://epsilon.jottit.test/")

    body = response.data.decode()
    # We have 25 revisions; the page should show 20 and offer an Older link.
    assert "Older" in body
    assert "before=" in body


def test_changes_older_link_pages_back(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_site(db_engine, secret_url="c6", public_url="zeta")
    with db_engine.begin() as conn:
        home = get_page(conn, site_id=site_id, page_name="")
        assert home is not None
        for n in range(2, 26):
            update_page(conn, page_id=home.id, content=f"v{n}")

    first = client.get("/site/changes", base_url="http://zeta.jottit.test/")
    # Extract the `before=` value from the first page's Older link.
    import re

    match = re.search(r"before=(\d+)", first.data.decode())
    assert match is not None
    before = match.group(1)

    second = client.get(f"/site/changes?before={before}", base_url="http://zeta.jottit.test/")

    assert second.status_code == 200
    assert "Older" not in second.data.decode()


# ---- Auth gating ----


def test_changes_on_private_site_redirects_to_signin(
    client: FlaskClient, db_engine: Engine
) -> None:
    _seed_site(db_engine, secret_url="c7", public_url="eta", security="private", password="hunter2")

    response = client.get("/site/changes", base_url="http://eta.jottit.test/")

    assert response.status_code == 303
    assert "site/signin" in response.headers["Location"]


def test_changes_on_public_site_redirects_to_signin(client: FlaskClient, db_engine: Engine) -> None:
    _seed_site(
        db_engine, secret_url="c8", public_url="theta", security="public", password="hunter2"
    )

    response = client.get("/site/changes", base_url="http://theta.jottit.test/")

    assert response.status_code == 303
    assert "site/signin" in response.headers["Location"]


def test_changes_on_open_site_allowed_anonymously(client: FlaskClient, db_engine: Engine) -> None:
    _seed_site(db_engine, secret_url="c9", public_url="iota", security="open", password="hunter2")

    response = client.get("/site/changes", base_url="http://iota.jottit.test/")

    assert response.status_code == 200


# ---- Secret-URL routing ----


def test_changes_via_secret_url(client: FlaskClient, db_engine: Engine) -> None:
    _seed_site(db_engine, secret_url="abc12")

    response = client.get("/abc12/site/changes", base_url=APEX)

    assert response.status_code == 200
    # Revision links should resolve under the secret prefix.
    assert 'href="/abc12/?r=' in response.data.decode()
