from __future__ import annotations

from collections.abc import Iterator

import pytest
from flask.testing import FlaskClient
from sqlalchemy import Engine

from jottit.auth import hash_password
from jottit.db import claim_site, get_design, metadata, new_site

APEX = "http://jottit.test/"

GOOD_DESIGN = {
    "title_font": "Georgia",
    "subtitle_font": "Georgia",
    "headings_font": "Georgia",
    "content_font": "Verdana",
    "header_color": "#003452",
    "title_color": "#ffffff",
    "subtitle_color": "#bfe8ff",
    "title_size": "120",
    "subtitle_size": "110",
    "headings_size": "130",
    "content_size": "100",
    "hue": "143",
    "brightness": "214",
}


@pytest.fixture(autouse=True)
def _truncate(db_engine: Engine) -> Iterator[None]:
    yield
    with db_engine.begin() as conn:
        for table in reversed(metadata.sorted_tables):
            conn.execute(table.delete())


def _seed_claimed_site(db_engine: Engine, *, secret_url: str, public_url: str | None = None) -> int:
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


def test_get_design_redirects_anonymous(client: FlaskClient, db_engine: Engine) -> None:
    _seed_claimed_site(db_engine, secret_url="d1", public_url="alpha")

    response = client.get("/admin/design", base_url="http://alpha.jottit.test/")

    assert response.status_code == 303
    assert "site/signin" in response.headers["Location"]


def test_post_design_returns_401_anonymous(client: FlaskClient, db_engine: Engine) -> None:
    _seed_claimed_site(db_engine, secret_url="d2", public_url="beta")

    response = client.post("/admin/design", base_url="http://beta.jottit.test/", data=GOOD_DESIGN)

    assert response.status_code == 401


# ---- GET ----


def test_get_renders_form_with_current_design(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="d3", public_url="gamma")
    _sign_in(client, base_url="http://gamma.jottit.test/", site_id=site_id)

    response = client.get("/admin/design", base_url="http://gamma.jottit.test/")

    assert response.status_code == 200
    body = response.data.decode()
    # new_site seeds the design row with "system-ui, sans-serif" so the
    # site resolves to the visitor's OS font without shipping a webfont.
    assert "system-ui, sans-serif" in body


# ---- POST: happy path ----


def test_post_design_saves_all_thirteen_fields(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="d4", public_url="delta")
    _sign_in(client, base_url="http://delta.jottit.test/", site_id=site_id)

    response = client.post("/admin/design", base_url="http://delta.jottit.test/", data=GOOD_DESIGN)

    assert response.status_code == 303
    assert response.headers["Location"] == "/admin/design"

    with db_engine.connect() as conn:
        d = get_design(conn, site_id=site_id)
        assert d is not None
        assert d.title_font == "Georgia"
        assert d.content_font == "Verdana"
        assert d.header_color == "#003452"
        assert d.title_color == "#ffffff"
        assert d.subtitle_color == "#bfe8ff"
        assert d.title_size == 120
        assert d.subtitle_size == 110
        assert d.headings_size == 130
        assert d.content_size == 100
        assert d.hue == "143"
        assert d.brightness == "214"


def test_post_design_accepts_short_hex_colors(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="d5", public_url="epsilon")
    _sign_in(client, base_url="http://epsilon.jottit.test/", site_id=site_id)
    data = {**GOOD_DESIGN, "header_color": "#fff", "title_color": "#000"}

    response = client.post("/admin/design", base_url="http://epsilon.jottit.test/", data=data)

    assert response.status_code == 303
    with db_engine.connect() as conn:
        d = get_design(conn, site_id=site_id)
        assert d is not None
        assert d.header_color == "#fff"


def test_post_design_empty_string_leaves_existing_value(
    client: FlaskClient, db_engine: Engine
) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="d6", public_url="zeta")
    _sign_in(client, base_url="http://zeta.jottit.test/", site_id=site_id)
    with db_engine.connect() as conn:
        before = get_design(conn, site_id=site_id)
    assert before is not None
    original_subtitle_font = before.subtitle_font

    data = {**GOOD_DESIGN, "subtitle_font": ""}
    client.post("/admin/design", base_url="http://zeta.jottit.test/", data=data)

    with db_engine.connect() as conn:
        after = get_design(conn, site_id=site_id)
        assert after is not None
        assert after.subtitle_font == original_subtitle_font


# ---- POST: validation ----


def test_post_design_rejects_invalid_hex_color(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="d7", public_url="eta")
    _sign_in(client, base_url="http://eta.jottit.test/", site_id=site_id)

    response = client.post(
        "/admin/design",
        base_url="http://eta.jottit.test/",
        data={**GOOD_DESIGN, "header_color": "red; evil"},
    )

    assert response.status_code == 400
    with db_engine.connect() as conn:
        d = get_design(conn, site_id=site_id)
        assert d is not None
        # Color unchanged from the new_site default.
        assert d.header_color != "red; evil"


def test_post_design_rejects_size_out_of_range(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="d8", public_url="theta")
    _sign_in(client, base_url="http://theta.jottit.test/", site_id=site_id)

    response = client.post(
        "/admin/design",
        base_url="http://theta.jottit.test/",
        data={**GOOD_DESIGN, "title_size": "99999"},
    )

    assert response.status_code == 400


def test_post_design_rejects_non_numeric_size(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="d9", public_url="iota")
    _sign_in(client, base_url="http://iota.jottit.test/", site_id=site_id)

    response = client.post(
        "/admin/design",
        base_url="http://iota.jottit.test/",
        data={**GOOD_DESIGN, "content_size": "huge"},
    )

    assert response.status_code == 400


def test_post_design_rejects_font_with_html_chars(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="d10", public_url="kappa")
    _sign_in(client, base_url="http://kappa.jottit.test/", site_id=site_id)

    response = client.post(
        "/admin/design",
        base_url="http://kappa.jottit.test/",
        data={**GOOD_DESIGN, "title_font": "<script>xss</script>"},
    )

    assert response.status_code == 400


def test_post_design_rejects_hue_out_of_range(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="d11", public_url="lambda")
    _sign_in(client, base_url="http://lambda.jottit.test/", site_id=site_id)

    response = client.post(
        "/admin/design",
        base_url="http://lambda.jottit.test/",
        data={**GOOD_DESIGN, "hue": "9999"},
    )

    assert response.status_code == 400


# ---- Secret-URL routing ----


def test_design_via_secret_url(client: FlaskClient, db_engine: Engine) -> None:
    site_id = _seed_claimed_site(db_engine, secret_url="abc12")
    _sign_in(client, base_url=APEX, site_id=site_id)

    response = client.post("/abc12/admin/design", base_url=APEX, data=GOOD_DESIGN)

    assert response.status_code == 303
    assert response.headers["Location"] == "/abc12/admin/design"
