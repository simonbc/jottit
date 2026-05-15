from __future__ import annotations

import pytest
from flask.testing import FlaskClient

SITE_BASE = "http://mysite.jottit.test/"


@pytest.mark.parametrize(
    ("method", "path", "expected_substring"),
    [
        ("GET", "/site/claim", "site/claim GET"),
        ("POST", "/site/claim", "site/claim POST"),
        ("GET", "/site/signin", "site/signin GET"),
        ("POST", "/site/signin", "site/signin POST"),
        ("POST", "/site/signout", "site/signout POST"),
        ("GET", "/site/forgot-password", "site/forgot-password GET"),
        ("POST", "/site/forgot-password", "site/forgot-password POST"),
        ("GET", "/site/change-password", "site/change-password GET"),
        ("POST", "/site/change-password", "site/change-password POST"),
        ("GET", "/site/changes", "site/changes GET"),
        ("GET", "/site/changes.atom", "site/changes.atom GET"),
        ("POST", "/site/hide-primer", "site/hide-primer POST"),
    ],
)
def test_site_blueprint(
    client: FlaskClient, method: str, path: str, expected_substring: str
) -> None:
    response = client.open(path, method=method, base_url=SITE_BASE)
    assert response.status_code == 200
    body = response.data.decode()
    assert body.startswith("site:mysite ")
    assert expected_substring in body


@pytest.mark.parametrize(
    ("method", "path", "expected_substring"),
    [
        ("GET", "/admin/settings", "admin/settings GET"),
        ("POST", "/admin/settings", "admin/settings POST"),
        ("GET", "/admin/design", "admin/design GET"),
        ("POST", "/admin/design", "admin/design POST"),
        ("POST", "/admin/url-available", "admin/url-available POST"),
        ("GET", "/admin/delete", "admin/delete GET"),
        ("POST", "/admin/delete", "admin/delete POST"),
        ("GET", "/admin/change-site-address", "admin/change-site-address GET"),
        ("POST", "/admin/change-site-address", "admin/change-site-address POST"),
        ("GET", "/admin/change-password", "admin/change-password GET"),
        ("POST", "/admin/change-password", "admin/change-password POST"),
        ("GET", "/admin/export", "admin/export GET"),
    ],
)
def test_admin_blueprint(
    client: FlaskClient, method: str, path: str, expected_substring: str
) -> None:
    response = client.open(path, method=method, base_url=SITE_BASE)
    assert response.status_code == 200
    body = response.data.decode()
    assert body.startswith("admin:mysite ")
    assert expected_substring in body


def test_page_blueprint_home(client: FlaskClient) -> None:
    response = client.get("/", base_url=SITE_BASE)
    assert response.status_code == 200
    assert response.data.decode() == "page:mysite home GET (TODO)"


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_page_blueprint_named_page(client: FlaskClient, method: str) -> None:
    response = client.open("/about", method=method, base_url=SITE_BASE)
    assert response.status_code == 200
    body = response.data.decode()
    assert body == f"page:mysite page=about m=view {method} (TODO)"


def test_page_blueprint_mode_query_param(client: FlaskClient) -> None:
    response = client.get("/some-page?m=edit", base_url=SITE_BASE)
    assert response.status_code == 200
    assert "m=edit" in response.data.decode()


def test_subdomain_slug_captured_per_request(client: FlaskClient) -> None:
    r1 = client.get("/", base_url="http://alice.jottit.test/")
    r2 = client.get("/", base_url="http://bob.jottit.test/")
    assert "alice" in r1.data.decode()
    assert "bob" in r2.data.decode()


def test_root_blueprint_still_works_alongside_subdomains(client: FlaskClient) -> None:
    response = client.get("/about", base_url="http://jottit.test/")
    assert response.status_code == 200
    assert response.data.decode() == "jottit:about (TODO)"
