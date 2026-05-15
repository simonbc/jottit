from __future__ import annotations

from collections.abc import Iterator

import pytest
from flask.testing import FlaskClient
from sqlalchemy import Engine

from jottit.auth import hash_password
from jottit.db import claim_site, get_page, metadata, new_site, update_page

APEX = "http://jottit.test/"


@pytest.fixture(autouse=True)
def _truncate(db_engine: Engine) -> Iterator[None]:
    yield
    with db_engine.begin() as conn:
        for table in reversed(metadata.sorted_tables):
            conn.execute(table.delete())


def _seed_site_with_revisions(
    db_engine: Engine,
    *,
    secret_url: str,
    public_url: str | None = None,
    revisions_content: list[str] | None = None,
    security: str | None = None,
    password: str | None = None,
) -> int:
    revisions_content = revisions_content or ["v1", "v2", "v3"]
    with db_engine.begin() as conn:
        site_id = new_site(
            conn, content=revisions_content[0], secret_url=secret_url, public_url=public_url
        )
        if password is not None:
            claim_site(
                conn,
                site_id=site_id,
                password_hash=hash_password(password),
                email="o@example.com",
                security=security or "private",
            )
        page = get_page(conn, site_id=site_id, page_name="")
        assert page is not None
        for body in revisions_content[1:]:
            update_page(conn, page_id=page.id, content=body)
    return site_id


def _sign_in(client: FlaskClient, *, base_url: str, site_id: int) -> None:
    with client.session_transaction(base_url=base_url) as sess:
        sess["signed_in_sites"] = [*sess.get("signed_in_sites", []), site_id]


# ---- Happy path ----


def test_diff_with_no_r_compares_latest_vs_previous(client: FlaskClient, db_engine: Engine) -> None:
    _seed_site_with_revisions(
        db_engine,
        secret_url="d1",
        public_url="alpha",
        revisions_content=["hello world", "hello there"],
    )

    response = client.get("/?m=diff", base_url="http://alpha.jottit.test/")

    assert response.status_code == 200
    body = response.data.decode()
    assert "Comparing" in body
    assert "revision 1" in body
    assert "revision 2" in body
    assert "<del>world</del>" in body
    assert "<ins>there</ins>" in body


def test_diff_with_single_r_compares_that_revision_to_previous(
    client: FlaskClient, db_engine: Engine
) -> None:
    _seed_site_with_revisions(
        db_engine,
        secret_url="d2",
        public_url="beta",
        revisions_content=["a", "b", "c"],
    )

    response = client.get("/?m=diff&r=2", base_url="http://beta.jottit.test/")

    body = response.data.decode()
    assert "revision 1" in body
    assert "revision 2" in body
    assert "revision 3" not in body


def test_diff_with_two_r_compares_those_revisions(client: FlaskClient, db_engine: Engine) -> None:
    _seed_site_with_revisions(
        db_engine,
        secret_url="d3",
        public_url="gamma",
        revisions_content=["one", "two", "three", "four"],
    )

    response = client.get("/?m=diff&r=1&r=4", base_url="http://gamma.jottit.test/")

    body = response.data.decode()
    assert "revision 1" in body
    assert "revision 4" in body
    assert "<del>one</del>" in body
    assert "<ins>four</ins>" in body


def test_diff_normalizes_revision_order(client: FlaskClient, db_engine: Engine) -> None:
    """?r=3&r=1 should produce the same diff as ?r=1&r=3."""
    _seed_site_with_revisions(
        db_engine,
        secret_url="d4",
        public_url="delta",
        revisions_content=["one", "two", "three"],
    )

    swapped = client.get("/?m=diff&r=3&r=1", base_url="http://delta.jottit.test/")
    correct = client.get("/?m=diff&r=1&r=3", base_url="http://delta.jottit.test/")

    assert swapped.data == correct.data


def test_diff_for_first_revision_only_shows_self(client: FlaskClient, db_engine: Engine) -> None:
    """`?r=1` clamps the implicit prev-revision to 1 too — both sides become rev 1."""
    _seed_site_with_revisions(
        db_engine, secret_url="d5", public_url="epsilon", revisions_content=["only"]
    )

    response = client.get("/?m=diff&r=1", base_url="http://epsilon.jottit.test/")

    assert response.status_code == 200


# ---- Bad inputs ----


def test_diff_too_many_revisions_returns_400(client: FlaskClient, db_engine: Engine) -> None:
    _seed_site_with_revisions(db_engine, secret_url="d6", public_url="zeta")

    response = client.get("/?m=diff&r=1&r=2&r=3", base_url="http://zeta.jottit.test/")

    assert response.status_code == 400


def test_diff_non_integer_revision_returns_400(client: FlaskClient, db_engine: Engine) -> None:
    _seed_site_with_revisions(db_engine, secret_url="d7", public_url="eta")

    response = client.get("/?m=diff&r=banana", base_url="http://eta.jottit.test/")

    assert response.status_code == 400


def test_diff_unknown_revision_returns_400(client: FlaskClient, db_engine: Engine) -> None:
    _seed_site_with_revisions(db_engine, secret_url="d8", public_url="theta")

    response = client.get("/?m=diff&r=99", base_url="http://theta.jottit.test/")

    assert response.status_code == 400


def test_diff_for_unknown_page_404s(client: FlaskClient, db_engine: Engine) -> None:
    _seed_site_with_revisions(db_engine, secret_url="d9", public_url="iota")

    response = client.get("/no-such-page?m=diff", base_url="http://iota.jottit.test/")

    assert response.status_code == 404


# ---- Auth gating ----


def test_diff_on_public_site_redirects_anonymous_to_signin(
    client: FlaskClient, db_engine: Engine
) -> None:
    _seed_site_with_revisions(
        db_engine,
        secret_url="d10",
        public_url="kappa",
        security="public",
        password="hunter2",
    )

    response = client.get("/?m=diff", base_url="http://kappa.jottit.test/")

    assert response.status_code == 303
    assert "site/signin" in response.headers["Location"]


def test_diff_on_open_site_allowed_anonymously(client: FlaskClient, db_engine: Engine) -> None:
    _seed_site_with_revisions(
        db_engine, secret_url="d11", public_url="lambda", security="open", password="hunter2"
    )

    response = client.get("/?m=diff", base_url="http://lambda.jottit.test/")

    assert response.status_code == 200


# ---- Secret-URL routing ----


def test_diff_via_secret_url(client: FlaskClient, db_engine: Engine) -> None:
    _seed_site_with_revisions(db_engine, secret_url="abc12")

    response = client.get("/abc12/?m=diff", base_url=APEX)

    assert response.status_code == 200
    assert 'href="/abc12/?r=' in response.data.decode()
