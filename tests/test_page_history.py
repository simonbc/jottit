from __future__ import annotations

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
        site_id = new_site(conn, content="v1", secret_url=secret_url, public_url=public_url)
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


def _make_revisions(db_engine: Engine, site_id: int, page_name: str, count: int) -> None:
    """Land `count` revisions on the named page (including the seed)."""
    with db_engine.begin() as conn:
        if page_name:
            new_page(conn, site_id=site_id, name=page_name, content="v1")
        page = get_page(conn, site_id=site_id, page_name=page_name)
        assert page is not None
        for n in range(2, count + 1):
            update_page(conn, page_id=page.id, content=f"v{n}")


# ---- Happy path ----


def test_history_lists_revisions_newest_first(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_site(db_engine, secret_url="h1", public_url="alpha")
    _make_revisions(db_engine, site_id, "", count=3)

    response = client.get("/?m=history", base_url="http://alpha.jottit.test/")

    assert response.status_code == 200
    body = response.data.decode()
    # Newest revision number appears before older ones.
    assert body.index("Revision 3") < body.index("Revision 2") < body.index("Revision 1")


def test_history_renders_total_count(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_site(db_engine, secret_url="h2", public_url="beta")
    _make_revisions(db_engine, site_id, "", count=4)

    response = client.get("/?m=history", base_url="http://beta.jottit.test/")

    assert "4 revisions" in response.data.decode()


def test_history_singular_count_for_one_revision(client: FlaskClient, db_engine: Engine) -> None:
    _seed_site(db_engine, secret_url="h3", public_url="gamma")

    response = client.get("/?m=history", base_url="http://gamma.jottit.test/")

    assert "1 revision." in response.data.decode()


def test_history_for_named_page(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_site(db_engine, secret_url="h4", public_url="delta")
    _make_revisions(db_engine, site_id, "notes", count=2)

    response = client.get("/notes?m=history", base_url="http://delta.jottit.test/")

    assert response.status_code == 200
    body = response.data.decode()
    assert "History: notes" in body
    assert "Revision 2" in body


# ---- Pagination ----


def test_history_first_page_capped_at_twenty(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_site(db_engine, secret_url="h5", public_url="epsilon")
    _make_revisions(db_engine, site_id, "", count=25)

    response = client.get("/?m=history", base_url="http://epsilon.jottit.test/")

    body = response.data.decode()
    # Latest 20 shown (revisions 25..6), older link points back further.
    assert "Revision 25" in body
    assert "Revision 6" in body
    assert "Revision 5" not in body
    assert "Older" in body
    assert "before=6" in body


def test_history_older_link_pages_back(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_site(db_engine, secret_url="h6", public_url="zeta")
    _make_revisions(db_engine, site_id, "", count=25)

    response = client.get("/?m=history&before=6", base_url="http://zeta.jottit.test/")

    body = response.data.decode()
    # Revisions 5..1 shown; no more "Older" link because that's the tail.
    assert "Revision 5" in body
    assert "Revision 1" in body
    assert "Revision 6" not in body
    assert "Older" not in body


def test_history_no_older_link_when_results_fit_in_one_page(
    client: FlaskClient, db_engine: Engine
) -> None:
    site_id = _seed_site(db_engine, secret_url="h7", public_url="eta")
    _make_revisions(db_engine, site_id, "", count=10)

    response = client.get("/?m=history", base_url="http://eta.jottit.test/")

    assert "Older" not in response.data.decode()


# ---- Missing / empty cases ----


def test_history_for_unknown_page_returns_404(client: FlaskClient, db_engine: Engine) -> None:
    _seed_site(db_engine, secret_url="h8", public_url="theta")

    response = client.get("/no-such-page?m=history", base_url="http://theta.jottit.test/")

    assert response.status_code == 404


# ---- Auth gating ----


def test_history_on_private_site_redirects_to_signin(
    client: FlaskClient, db_engine: Engine
) -> None:
    _seed_site(
        db_engine, secret_url="h9", public_url="iota", security="private", password="hunter2"
    )

    response = client.get("/?m=history", base_url="http://iota.jottit.test/")

    assert response.status_code == 303
    assert "site/signin" in response.headers["Location"]


def test_history_on_public_site_redirects_anonymous_to_signin(
    client: FlaskClient, db_engine: Engine
) -> None:
    _seed_site(
        db_engine, secret_url="h10", public_url="kappa", security="public", password="hunter2"
    )

    response = client.get("/?m=history", base_url="http://kappa.jottit.test/")

    # Public sites gate everything except plain `view` — history is
    # under view_revision.
    assert response.status_code == 303
    assert "site/signin" in response.headers["Location"]


def test_history_on_open_site_allowed_anonymously(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_site(
        db_engine, secret_url="h11", public_url="lambda", security="open", password="hunter2"
    )
    _make_revisions(db_engine, site_id, "", count=2)

    response = client.get("/?m=history", base_url="http://lambda.jottit.test/")

    assert response.status_code == 200


def test_history_on_private_site_with_signin_allowed(
    client: FlaskClient, db_engine: Engine
) -> None:
    site_id = _seed_site(
        db_engine,
        secret_url="h12",
        public_url="mu",
        security="private",
        password="hunter2",
    )
    _make_revisions(db_engine, site_id, "", count=2)
    _sign_in(client, base_url="http://mu.jottit.test/", site_id=site_id)

    response = client.get("/?m=history", base_url="http://mu.jottit.test/")

    assert response.status_code == 200


# ---- Secret-URL routing ----


def test_history_via_secret_url(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_site(db_engine, secret_url="abc12")
    _make_revisions(db_engine, site_id, "", count=2)

    response = client.get("/abc12/?m=history", base_url=APEX)

    assert response.status_code == 200
    body = response.data.decode()
    # Revision links should be rooted at the secret URL prefix.
    assert 'href="/abc12/?r=1"' in body
    assert 'href="/abc12/?r=2"' in body
