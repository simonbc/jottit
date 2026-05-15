from __future__ import annotations

from collections.abc import Iterator
from urllib.parse import parse_qs, urlparse

import pytest
from flask.testing import FlaskClient
from sqlalchemy import Engine

from jottit.auth import hash_password
from jottit.db import (
    claim_site,
    drafts,
    get_draft,
    get_page,
    metadata,
    new_page,
    new_site,
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
    password: str | None = "hunter2",
) -> int:
    """Seed a site. When `password` is None the site is unclaimed.

    `security` is meaningless on an unclaimed site (the auth matrix
    short-circuits on `password is None`), so it's only stored when a
    password is set.
    """
    with db_engine.begin() as conn:
        site_id = new_site(conn, content="hi", secret_url=secret_url, public_url=public_url)
        if password is not None:
            claim_site(
                conn,
                site_id=site_id,
                password_hash=hash_password(password),
                email="owner@example.com",
                security=security or "private",
            )
    return site_id


def _sign_in(client: FlaskClient, *, base_url: str, site_id: int) -> None:
    with client.session_transaction(base_url=base_url) as sess:
        sess["signed_in_sites"] = [*sess.get("signed_in_sites", []), site_id]


# ---- Private sites lock everything down ----


def test_private_site_get_view_redirects_anonymous_to_signin(
    client: FlaskClient, db_engine: Engine
) -> None:
    _seed_site(db_engine, secret_url="pr1", public_url="alpha", security="private")

    response = client.get("/", base_url="http://alpha.jottit.test/")

    assert response.status_code == 303
    location = response.headers["Location"]
    assert urlparse(location).path == "/site/signin"


def test_private_site_get_view_with_session_renders_page(
    client: FlaskClient, db_engine: Engine
) -> None:
    site_id = _seed_site(db_engine, secret_url="pr2", public_url="beta", security="private")
    _sign_in(client, base_url="http://beta.jottit.test/", site_id=site_id)

    response = client.get("/", base_url="http://beta.jottit.test/")

    assert response.status_code == 200


def test_private_site_post_save_returns_401_when_anonymous(
    client: FlaskClient, db_engine: Engine
) -> None:
    _seed_site(db_engine, secret_url="pr3", public_url="gamma", security="private")

    response = client.post("/", base_url="http://gamma.jottit.test/", data={"content": "x"})

    assert response.status_code == 401


# ---- Public sites allow read, gate everything else ----


def test_public_site_anonymous_can_view_latest_revision(
    client: FlaskClient, db_engine: Engine
) -> None:
    _seed_site(db_engine, secret_url="pu1", public_url="delta", security="public")

    response = client.get("/", base_url="http://delta.jottit.test/")

    assert response.status_code == 200


def test_public_site_anonymous_revision_view_redirects_to_signin(
    client: FlaskClient, db_engine: Engine
) -> None:
    _seed_site(db_engine, secret_url="pu2", public_url="epsilon", security="public")

    response = client.get("/?r=1", base_url="http://epsilon.jottit.test/")

    assert response.status_code == 303
    assert urlparse(response.headers["Location"]).path == "/site/signin"


def test_public_site_anonymous_edit_form_redirects_to_signin(
    client: FlaskClient, db_engine: Engine
) -> None:
    _seed_site(db_engine, secret_url="pu3", public_url="zeta", security="public")

    response = client.get("/?m=edit", base_url="http://zeta.jottit.test/")

    assert response.status_code == 303
    assert urlparse(response.headers["Location"]).path == "/site/signin"


def test_public_site_anonymous_save_returns_401(client: FlaskClient, db_engine: Engine) -> None:
    _seed_site(db_engine, secret_url="pu4", public_url="eta", security="public")

    response = client.post("/", base_url="http://eta.jottit.test/", data={"content": "x"})

    assert response.status_code == 401


def test_public_site_signed_in_user_can_edit(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_site(db_engine, secret_url="pu5", public_url="theta", security="public")
    _sign_in(client, base_url="http://theta.jottit.test/", site_id=site_id)

    response = client.post("/", base_url="http://theta.jottit.test/", data={"content": "edited"})

    assert response.status_code == 303
    with db_engine.connect() as conn:
        page = get_page(conn, site_id=site_id, page_name="")
        assert page is not None


# ---- Open sites allow everything except admin ----


def test_open_site_anonymous_can_save(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_site(db_engine, secret_url="op1", public_url="iota", security="open")

    response = client.post(
        "/notes", base_url="http://iota.jottit.test/", data={"content": "wiki-style"}
    )

    assert response.status_code == 303
    with db_engine.connect() as conn:
        page = get_page(conn, site_id=site_id, page_name="notes")
        assert page is not None


# ---- Draft endpoints ----


def test_private_site_draft_save_returns_401_anonymously(
    client: FlaskClient, db_engine: Engine
) -> None:
    site_id = _seed_site(db_engine, secret_url="dr1", public_url="kappa", security="private")
    with db_engine.begin() as conn:
        new_page(conn, site_id=site_id, name="notes", content="x")

    response = client.post(
        "/draft/save",
        base_url="http://kappa.jottit.test/",
        data={"page_name": "notes", "content": "draft"},
    )

    assert response.status_code == 401


def test_public_site_draft_save_returns_401_anonymously(
    client: FlaskClient, db_engine: Engine
) -> None:
    _seed_site(db_engine, secret_url="dr2", public_url="lambda", security="public")

    response = client.post(
        "/draft/save",
        base_url="http://lambda.jottit.test/",
        data={"page_name": "", "content": "x"},
    )

    assert response.status_code == 401


def test_public_site_draft_save_succeeds_when_signed_in(
    client: FlaskClient, db_engine: Engine
) -> None:
    site_id = _seed_site(db_engine, secret_url="dr3", public_url="mu", security="public")
    _sign_in(client, base_url="http://mu.jottit.test/", site_id=site_id)

    response = client.post(
        "/draft/save",
        base_url="http://mu.jottit.test/",
        data={"page_name": "", "content": "draft body"},
    )

    assert response.status_code == 204
    with db_engine.connect() as conn:
        page = get_page(conn, site_id=site_id, page_name="")
        assert page is not None
        assert get_draft(conn, page_id=page.id) is not None


def test_open_site_draft_save_allowed_anonymously(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_site(db_engine, secret_url="dr4", public_url="nu", security="open")

    response = client.post(
        "/draft/save",
        base_url="http://nu.jottit.test/",
        data={"page_name": "", "content": "anon draft"},
    )

    assert response.status_code == 204
    with db_engine.connect() as conn:
        page = get_page(conn, site_id=site_id, page_name="")
        assert page is not None
        rows = conn.execute(drafts.select().where(drafts.c.page_id == page.id)).all()
        assert len(rows) == 1


# ---- return_to wiring ----


def test_signin_redirect_carries_return_to_for_subdomain(
    client: FlaskClient, db_engine: Engine
) -> None:
    _seed_site(db_engine, secret_url="rt1", public_url="xi", security="private")

    response = client.get("/notes?m=edit", base_url="http://xi.jottit.test/")

    assert response.status_code == 303
    qs = parse_qs(urlparse(response.headers["Location"]).query)
    assert qs["return_to"] == ["notes?m=edit"]


def test_signin_redirect_carries_return_to_for_secret_url(
    client: FlaskClient, db_engine: Engine
) -> None:
    _seed_site(db_engine, secret_url="abc12", security="private")

    response = client.get("/abc12/notes?m=edit", base_url=APEX)

    assert response.status_code == 303
    parsed = urlparse(response.headers["Location"])
    assert parsed.path == "/abc12/site/signin"
    assert parse_qs(parsed.query)["return_to"] == ["notes?m=edit"]


def test_end_to_end_signin_returns_to_original_url(client: FlaskClient, db_engine: Engine) -> None:
    """Full loop: hit a gated URL → follow the redirect to signin → submit → end up where we started."""
    _seed_site(db_engine, secret_url="e2e", public_url="omicron", security="private")

    initial = client.get("/notes?m=edit", base_url="http://omicron.jottit.test/")
    signin_url = initial.headers["Location"]
    return_to = parse_qs(urlparse(signin_url).query)["return_to"][0]

    final = client.post(
        urlparse(signin_url).path,
        base_url="http://omicron.jottit.test/",
        data={"password": "hunter2", "return_to": return_to},
    )

    assert final.status_code == 303
    # The signin handler concatenates site_root + lstripped return_to, so
    # we should land back at /notes?m=edit (modulo encoding).
    assert final.headers["Location"] == "/notes?m=edit"


# ---- Unclaimed sites stay open ----


def test_unclaimed_site_does_not_require_signin(client: FlaskClient, db_engine: Engine) -> None:
    _seed_site(db_engine, secret_url="un1", public_url="pi", password=None)

    response = client.post("/", base_url="http://pi.jottit.test/", data={"content": "fresh"})

    assert response.status_code == 303
