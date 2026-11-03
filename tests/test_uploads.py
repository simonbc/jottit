from __future__ import annotations

import io
from collections.abc import Iterator
from pathlib import Path

import pytest
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy import Engine, select

from jottit.auth import hash_password
from jottit.db import claim_site, metadata, new_site, uploads
from jottit.storage import LocalStorage
from jottit.views.uploads import sniff_image_type

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
GIF = b"GIF89a" + b"\x00" * 32
WEBP = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 32


@pytest.fixture(autouse=True)
def _truncate(db_engine: Engine) -> Iterator[None]:
    yield
    with db_engine.begin() as conn:
        for table in reversed(metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture
def storage(app: Flask, tmp_path: Path) -> LocalStorage:
    local = LocalStorage(tmp_path)
    app.extensions["storage"] = local
    return local


def _seed_site(
    db_engine: Engine,
    *,
    secret_url: str,
    public_url: str | None = None,
    security: str | None = None,
    claimed: bool = True,
) -> int:
    with db_engine.begin() as conn:
        site_id = new_site(conn, content="hi", secret_url=secret_url, public_url=public_url)
        if claimed:
            claim_site(
                conn,
                site_id=site_id,
                password_hash=hash_password("hunter2"),
                email="owner@example.com",
                security=security or "private",
            )
    return site_id


def _sign_in(client: FlaskClient, *, base_url: str, site_id: int) -> None:
    with client.session_transaction(base_url=base_url) as sess:
        sess["signed_in_sites"] = [*sess.get("signed_in_sites", []), site_id]


def _post(client: FlaskClient, url: str, data: bytes, filename: str = "cat.png", **kw):
    return client.post(
        url, data={"file": (io.BytesIO(data), filename)}, content_type="multipart/form-data", **kw
    )


# ---- sniffing ----


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (PNG, "image/png"),
        (JPEG, "image/jpeg"),
        (GIF, "image/gif"),
        (b"GIF87a" + b"\x00" * 8, "image/gif"),
        (WEBP, "image/webp"),
        (b"<svg xmlns='http://www.w3.org/2000/svg'/>", None),
        (b"RIFF\x00\x00\x00\x00WAVEfmt ", None),
        (b"%PDF-1.7", None),
        (b"", None),
    ],
)
def test_sniff_image_type(data: bytes, expected: str | None) -> None:
    assert sniff_image_type(data) == expected


# ---- upload: happy path ----


def test_upload_on_unclaimed_site_stores_file_and_row(
    client: FlaskClient, db_engine: Engine, storage: LocalStorage
) -> None:
    site_id = _seed_site(db_engine, secret_url="up1", public_url="alpha", claimed=False)

    response = _post(client, "/site/uploads", PNG, base_url="http://alpha.jottit.test/")

    assert response.status_code == 201
    url = response.get_json()["url"]
    assert url.startswith("/site/uploads/")
    assert url.endswith(".png")
    name = url.rsplit("/", 1)[1]
    with db_engine.connect() as conn:
        row = conn.execute(select(uploads)).one()
    assert row.site_id == site_id
    assert row.storage_key == f"sites/{site_id}/{name}"
    assert row.filename == "cat.png"
    assert row.content_type == "image/png"
    assert row.size == len(PNG)
    assert row.ip == "127.0.0.1"
    assert storage.get(row.storage_key) == PNG


def test_upload_trusts_bytes_over_extension(
    client: FlaskClient, db_engine: Engine, storage: LocalStorage
) -> None:
    _seed_site(db_engine, secret_url="up2", public_url="alpha", claimed=False)

    response = _post(
        client, "/site/uploads", JPEG, "photo.png", base_url="http://alpha.jottit.test/"
    )

    assert response.status_code == 201
    assert response.get_json()["url"].endswith(".jpg")


def test_upload_generates_distinct_keys(
    client: FlaskClient, db_engine: Engine, storage: LocalStorage
) -> None:
    _seed_site(db_engine, secret_url="up3", public_url="alpha", claimed=False)
    base = "http://alpha.jottit.test/"

    first = _post(client, "/site/uploads", PNG, base_url=base).get_json()["url"]
    second = _post(client, "/site/uploads", PNG, base_url=base).get_json()["url"]

    assert first != second


def test_upload_via_secret_url(
    client: FlaskClient, db_engine: Engine, storage: LocalStorage
) -> None:
    _seed_site(db_engine, secret_url="up4", claimed=False)

    response = _post(client, "/up4/site/uploads", GIF, "a.gif", base_url="http://jottit.test/")

    assert response.status_code == 201
    url = response.get_json()["url"]
    assert url.startswith("/site/uploads/")
    served = client.get(f"/up4{url}", base_url="http://jottit.test/")
    assert served.status_code == 200
    assert served.data == GIF


# ---- upload: auth ----


@pytest.mark.parametrize("security", ["private", "public"])
def test_upload_rejects_anonymous_on_locked_sites(
    client: FlaskClient, db_engine: Engine, storage: LocalStorage, security: str
) -> None:
    _seed_site(db_engine, secret_url="au1", public_url="alpha", security=security)

    response = _post(client, "/site/uploads", PNG, base_url="http://alpha.jottit.test/")

    assert response.status_code == 401
    with db_engine.connect() as conn:
        assert conn.execute(select(uploads)).first() is None


def test_upload_rejects_anonymous_on_private_secret_url_site(
    client: FlaskClient, db_engine: Engine, storage: LocalStorage
) -> None:
    _seed_site(db_engine, secret_url="au2", security="private")

    response = _post(client, "/au2/site/uploads", PNG, base_url="http://jottit.test/")

    assert response.status_code == 401


def test_upload_allows_anonymous_on_open_site(
    client: FlaskClient, db_engine: Engine, storage: LocalStorage
) -> None:
    _seed_site(db_engine, secret_url="au3", public_url="alpha", security="open")

    response = _post(client, "/site/uploads", PNG, base_url="http://alpha.jottit.test/")

    assert response.status_code == 201


def test_upload_allows_signed_in_owner_of_private_site(
    client: FlaskClient, db_engine: Engine, storage: LocalStorage
) -> None:
    base = "http://alpha.jottit.test/"
    site_id = _seed_site(db_engine, secret_url="au4", public_url="alpha", security="private")
    _sign_in(client, base_url=base, site_id=site_id)

    response = _post(client, "/site/uploads", PNG, base_url=base)

    assert response.status_code == 201


def test_upload_signin_does_not_carry_across_sites(
    client: FlaskClient, db_engine: Engine, storage: LocalStorage
) -> None:
    other_id = _seed_site(db_engine, secret_url="au5", public_url="other", security="private")
    _seed_site(db_engine, secret_url="au6", public_url="alpha", security="private")
    _sign_in(client, base_url="http://other.jottit.test/", site_id=other_id)

    response = _post(client, "/site/uploads", PNG, base_url="http://alpha.jottit.test/")

    assert response.status_code == 401


def test_upload_unknown_site_404s(client: FlaskClient, storage: LocalStorage) -> None:
    response = _post(client, "/site/uploads", PNG, base_url="http://nope.jottit.test/")

    assert response.status_code == 404


def test_upload_rejects_get(client: FlaskClient, db_engine: Engine) -> None:
    _seed_site(db_engine, secret_url="au7", public_url="alpha", claimed=False)

    response = client.get("/site/uploads", base_url="http://alpha.jottit.test/")

    assert response.status_code == 405


# ---- upload: validation ----


@pytest.mark.parametrize(
    ("data", "filename"),
    [
        (b"<svg xmlns='http://www.w3.org/2000/svg'><script>x</script></svg>", "x.svg"),
        (b"<html><script>alert(1)</script></html>", "evil.png"),
        (b"%PDF-1.7 not an image", "doc.jpg"),
    ],
)
def test_upload_rejects_non_images(
    client: FlaskClient, db_engine: Engine, storage: LocalStorage, data: bytes, filename: str
) -> None:
    _seed_site(db_engine, secret_url="va1", public_url="alpha", claimed=False)

    response = _post(client, "/site/uploads", data, filename, base_url="http://alpha.jottit.test/")

    assert response.status_code == 415
    assert "PNG, JPEG, GIF, and WebP" in response.get_json()["error"]
    with db_engine.connect() as conn:
        assert conn.execute(select(uploads)).first() is None


def test_upload_requires_a_file(
    client: FlaskClient, db_engine: Engine, storage: LocalStorage
) -> None:
    _seed_site(db_engine, secret_url="va2", public_url="alpha", claimed=False)

    response = client.post("/site/uploads", data={}, base_url="http://alpha.jottit.test/")

    assert response.status_code == 400


def test_upload_rejects_files_over_the_cap(
    app: Flask, client: FlaskClient, db_engine: Engine, storage: LocalStorage
) -> None:
    app.config["MAX_UPLOAD_BYTES"] = 100
    _seed_site(db_engine, secret_url="va3", public_url="alpha", claimed=False)
    base = "http://alpha.jottit.test/"

    at_cap = _post(client, "/site/uploads", PNG + b"\x00" * (100 - len(PNG)), base_url=base)
    over_cap = _post(client, "/site/uploads", PNG + b"\x00" * (101 - len(PNG)), base_url=base)

    assert at_cap.status_code == 201
    assert over_cap.status_code == 413
    assert "MB or smaller" in over_cap.get_json()["error"]


def test_upload_rejects_oversized_request_before_parsing(
    app: Flask, client: FlaskClient, db_engine: Engine, storage: LocalStorage
) -> None:
    app.config["MAX_UPLOAD_BYTES"] = 100
    _seed_site(db_engine, secret_url="va4", public_url="alpha", claimed=False)

    response = _post(
        client, "/site/uploads", PNG + b"\x00" * 200_000, base_url="http://alpha.jottit.test/"
    )

    assert response.status_code == 413


def test_default_cap_is_five_megabytes(app: Flask) -> None:
    assert app.config["MAX_UPLOAD_BYTES"] == 5 * 1024 * 1024


# ---- serving ----


def test_serve_returns_bytes_with_sniffed_type(
    client: FlaskClient, db_engine: Engine, storage: LocalStorage
) -> None:
    _seed_site(db_engine, secret_url="sv1", public_url="alpha", claimed=False)
    base = "http://alpha.jottit.test/"
    url = _post(client, "/site/uploads", WEBP, "x.png", base_url=base).get_json()["url"]

    response = client.get(url, base_url=base)

    assert response.status_code == 200
    assert response.data == WEBP
    assert response.headers["Content-Type"] == "image/webp"
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_serve_private_site_requires_signin(
    client: FlaskClient, db_engine: Engine, storage: LocalStorage
) -> None:
    base = "http://alpha.jottit.test/"
    site_id = _seed_site(db_engine, secret_url="sv2", public_url="alpha", security="private")
    _sign_in(client, base_url=base, site_id=site_id)
    url = _post(client, "/site/uploads", PNG, base_url=base).get_json()["url"]

    with client.session_transaction(base_url=base) as sess:
        sess["signed_in_sites"] = []
    response = client.get(url, base_url=base)

    assert response.status_code == 303
    assert "/site/signin" in response.headers["Location"]


def test_serve_public_site_is_readable_anonymously(
    client: FlaskClient, db_engine: Engine, storage: LocalStorage
) -> None:
    base = "http://alpha.jottit.test/"
    site_id = _seed_site(db_engine, secret_url="sv3", public_url="alpha", security="public")
    _sign_in(client, base_url=base, site_id=site_id)
    url = _post(client, "/site/uploads", PNG, base_url=base).get_json()["url"]

    with client.session_transaction(base_url=base) as sess:
        sess["signed_in_sites"] = []
    response = client.get(url, base_url=base)

    assert response.status_code == 200


def test_serve_does_not_leak_across_sites(
    client: FlaskClient, db_engine: Engine, storage: LocalStorage
) -> None:
    _seed_site(db_engine, secret_url="sv4", public_url="alpha", claimed=False)
    _seed_site(db_engine, secret_url="sv5", public_url="beta", claimed=False)
    url = _post(client, "/site/uploads", PNG, base_url="http://alpha.jottit.test/").get_json()[
        "url"
    ]

    response = client.get(url, base_url="http://beta.jottit.test/")

    assert response.status_code == 404


def test_serve_unknown_name_404s(
    client: FlaskClient, db_engine: Engine, storage: LocalStorage
) -> None:
    _seed_site(db_engine, secret_url="sv6", public_url="alpha", claimed=False)

    response = client.get("/site/uploads/nope.png", base_url="http://alpha.jottit.test/")

    assert response.status_code == 404


def test_uploaded_image_renders_on_page(
    client: FlaskClient, db_engine: Engine, storage: LocalStorage
) -> None:
    _seed_site(db_engine, secret_url="sv7", public_url="alpha", claimed=False)
    base = "http://alpha.jottit.test/"
    url = _post(client, "/site/uploads", PNG, base_url=base).get_json()["url"]
    client.post("/", data={"content": f"![a cat]({url})"}, base_url=base)

    subdomain_page = client.get("/", base_url=base).get_data(as_text=True)
    secret_page = client.get("/sv7/", base_url="http://jottit.test/").get_data(as_text=True)

    assert f'<img src="{url}" alt="a cat">' in subdomain_page
    assert f'<img src="/sv7{url}" alt="a cat">' in secret_page
    assert client.get(f"/sv7{url}", base_url="http://jottit.test/").data == PNG


def test_edit_page_wires_up_uploads(client: FlaskClient, db_engine: Engine) -> None:
    _seed_site(db_engine, secret_url="ed1", claimed=False)

    html = client.get("/ed1/?m=edit", base_url="http://jottit.test/").get_data(as_text=True)

    assert 'data-upload-url="/ed1/site/uploads"' in html
    assert 'data-max-upload-bytes="5242880"' in html
    assert 'id="image_button"' in html
    assert "js/uploads.js" in html
