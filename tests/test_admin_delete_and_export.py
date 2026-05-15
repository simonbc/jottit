from __future__ import annotations

import io
import zipfile
from collections.abc import Iterator

import pytest
from flask.testing import FlaskClient
from sqlalchemy import Engine

from jottit.auth import hash_password
from jottit.db import (
    claim_site,
    get_site,
    is_public_url_available,
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


def _seed_claimed_site(
    db_engine: Engine,
    *,
    secret_url: str,
    public_url: str | None = None,
    content: str = "home page",
) -> int:
    with db_engine.begin() as conn:
        site_id = new_site(conn, content=content, secret_url=secret_url, public_url=public_url)
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


# ---- /admin/delete: auth ----


def test_delete_get_redirects_anonymous(client: FlaskClient, db_engine: Engine) -> None:
    _seed_claimed_site(db_engine, secret_url="dl1", public_url="alpha")

    response = client.get("/admin/delete", base_url="http://alpha.jottit.test/")

    assert response.status_code == 303
    assert "site/signin" in response.headers["Location"]


def test_delete_post_returns_401_anonymous(client: FlaskClient, db_engine: Engine) -> None:
    _seed_claimed_site(db_engine, secret_url="dl2", public_url="beta")

    response = client.post("/admin/delete", base_url="http://beta.jottit.test/")

    assert response.status_code == 401


# ---- /admin/delete: GET ----


def test_delete_get_renders_confirmation(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="dl3", public_url="gamma")
    _sign_in(client, base_url="http://gamma.jottit.test/", site_id=site_id)

    response = client.get("/admin/delete", base_url="http://gamma.jottit.test/")

    assert response.status_code == 200
    body = response.data.decode()
    assert "Delete this site" in body


# ---- /admin/delete: POST ----


def test_delete_post_marks_site_deleted_and_frees_slug(
    client: FlaskClient, db_engine: Engine
) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="dl4", public_url="delta")
    _sign_in(client, base_url="http://delta.jottit.test/", site_id=site_id)

    response = client.post("/admin/delete", base_url="http://delta.jottit.test/")

    assert response.status_code == 303
    assert response.headers["Location"] == "http://jottit.test/"

    with db_engine.connect() as conn:
        row = get_site(conn, site_id=site_id)
        assert row is not None
        assert row.deleted is True
        assert row.public_url is None
        assert is_public_url_available(conn, public_url="delta") is True


def test_delete_post_signs_user_out_of_that_site(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="dl5", public_url="epsilon")
    _sign_in(client, base_url="http://epsilon.jottit.test/", site_id=site_id)

    client.post("/admin/delete", base_url="http://epsilon.jottit.test/")

    with client.session_transaction(base_url="http://epsilon.jottit.test/") as sess:
        assert site_id not in sess.get("signed_in_sites", [])


def test_deleted_site_no_longer_resolves_for_subsequent_requests(
    client: FlaskClient, db_engine: Engine
) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="dl6", public_url="zeta")
    _sign_in(client, base_url="http://zeta.jottit.test/", site_id=site_id)

    client.post("/admin/delete", base_url="http://zeta.jottit.test/")

    # The site row still exists, but the resolver hides it now.
    response = client.get("/", base_url="http://zeta.jottit.test/")
    assert response.status_code == 404


def test_deleted_site_secret_url_also_404s(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="dl7")
    _sign_in(client, base_url=APEX, site_id=site_id)

    client.post("/dl7/admin/delete", base_url=APEX)

    response = client.get("/dl7/", base_url=APEX)
    assert response.status_code == 404


# ---- /admin/export ----


def test_export_redirects_anonymous(client: FlaskClient, db_engine: Engine) -> None:
    _seed_claimed_site(db_engine, secret_url="ex1", public_url="eta")

    response = client.get("/admin/export", base_url="http://eta.jottit.test/")

    assert response.status_code == 303
    assert "site/signin" in response.headers["Location"]


def test_export_returns_zip_with_pages(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="ex2", public_url="theta", content="welcome")
    with db_engine.begin() as conn:
        new_page(conn, site_id=site_id, name="notes", content="my notes")
        new_page(conn, site_id=site_id, name="about", content="about me")
    _sign_in(client, base_url="http://theta.jottit.test/", site_id=site_id)

    response = client.get("/admin/export", base_url="http://theta.jottit.test/")

    assert response.status_code == 200
    assert response.mimetype == "application/zip"
    assert "theta-export.zip" in response.headers["Content-Disposition"]

    with zipfile.ZipFile(io.BytesIO(response.data)) as zf:
        names = sorted(zf.namelist())
        assert names == ["about.md", "home.md", "notes.md"]
        assert zf.read("home.md").decode() == "welcome"
        assert zf.read("notes.md").decode() == "my notes"
        assert zf.read("about.md").decode() == "about me"


def test_export_uses_latest_revision_for_each_page(client: FlaskClient, db_engine: Engine) -> None:
    from jottit.db import get_page

    site_id = _seed_claimed_site(db_engine, secret_url="ex3", public_url="iota", content="v1")
    with db_engine.begin() as conn:
        home = get_page(conn, site_id=site_id, page_name="")
        assert home is not None
        update_page(conn, page_id=home.id, content="v2")
    _sign_in(client, base_url="http://iota.jottit.test/", site_id=site_id)

    response = client.get("/admin/export", base_url="http://iota.jottit.test/")

    with zipfile.ZipFile(io.BytesIO(response.data)) as zf:
        assert zf.read("home.md").decode() == "v2"


def test_export_filename_falls_back_to_secret_url_when_no_public_url(
    client: FlaskClient, db_engine: Engine
) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="abc12")
    _sign_in(client, base_url=APEX, site_id=site_id)

    response = client.get("/abc12/admin/export", base_url=APEX)

    assert "abc12-export.zip" in response.headers["Content-Disposition"]


def test_export_skips_deleted_pages(client: FlaskClient, db_engine: Engine) -> None:
    from jottit.db import delete_page, get_page

    site_id = _seed_claimed_site(db_engine, secret_url="ex4", public_url="kappa")
    with db_engine.begin() as conn:
        new_page(conn, site_id=site_id, name="gone", content="bye")
        page = get_page(conn, site_id=site_id, page_name="gone")
        assert page is not None
        delete_page(conn, page_id=page.id)
    _sign_in(client, base_url="http://kappa.jottit.test/", site_id=site_id)

    response = client.get("/admin/export", base_url="http://kappa.jottit.test/")

    with zipfile.ZipFile(io.BytesIO(response.data)) as zf:
        assert "gone.md" not in zf.namelist()


def test_export_export_filename_strips_slashes(client: FlaskClient, db_engine: Engine) -> None:
    """Path separators in page names mustn't survive into the zip — that's the
    actual zip-slip vector. Leading dots are cosmetic and stay as-is."""
    site_id = _seed_claimed_site(db_engine, secret_url="ex5", public_url="lambda")
    with db_engine.begin() as conn:
        new_page(conn, site_id=site_id, name="../oops", content="x")
    _sign_in(client, base_url="http://lambda.jottit.test/", site_id=site_id)

    response = client.get("/admin/export", base_url="http://lambda.jottit.test/")

    with zipfile.ZipFile(io.BytesIO(response.data)) as zf:
        for name in zf.namelist():
            assert "/" not in name
            assert "\\" not in name
