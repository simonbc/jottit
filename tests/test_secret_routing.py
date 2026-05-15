from __future__ import annotations

import pytest
from flask.testing import FlaskClient

APEX = "http://jottit.test/"


@pytest.mark.parametrize(
    ("method", "path", "expected_substring"),
    [
        ("GET", "/abc123/site/claim", "site/claim GET"),
        ("POST", "/abc123/site/claim", "site/claim POST"),
        ("GET", "/abc123/site/signin", "site/signin GET"),
        ("POST", "/abc123/site/signin", "site/signin POST"),
        ("POST", "/abc123/site/signout", "site/signout POST"),
        ("GET", "/abc123/site/forgot-password", "site/forgot-password GET"),
        ("POST", "/abc123/site/forgot-password", "site/forgot-password POST"),
        ("GET", "/abc123/site/change-password", "site/change-password GET"),
        ("POST", "/abc123/site/change-password", "site/change-password POST"),
        ("GET", "/abc123/site/changes", "site/changes GET"),
        ("GET", "/abc123/site/changes.atom", "site/changes.atom GET"),
        ("POST", "/abc123/site/hide-primer", "site/hide-primer POST"),
    ],
)
def test_secret_site_routes(
    client: FlaskClient, method: str, path: str, expected_substring: str
) -> None:
    response = client.open(path, method=method, base_url=APEX)
    assert response.status_code == 200
    body = response.data.decode()
    assert body.startswith("site:abc123 ")
    assert expected_substring in body


@pytest.mark.parametrize(
    ("method", "path", "expected_substring"),
    [
        ("GET", "/abc123/admin/settings", "admin/settings GET"),
        ("POST", "/abc123/admin/settings", "admin/settings POST"),
        ("GET", "/abc123/admin/design", "admin/design GET"),
        ("POST", "/abc123/admin/design", "admin/design POST"),
        ("POST", "/abc123/admin/url-available", "admin/url-available POST"),
        ("GET", "/abc123/admin/delete", "admin/delete GET"),
        ("POST", "/abc123/admin/delete", "admin/delete POST"),
        ("GET", "/abc123/admin/change-site-address", "admin/change-site-address GET"),
        ("POST", "/abc123/admin/change-site-address", "admin/change-site-address POST"),
        ("GET", "/abc123/admin/change-password", "admin/change-password GET"),
        ("POST", "/abc123/admin/change-password", "admin/change-password POST"),
        ("GET", "/abc123/admin/export", "admin/export GET"),
    ],
)
def test_secret_admin_routes(
    client: FlaskClient, method: str, path: str, expected_substring: str
) -> None:
    response = client.open(path, method=method, base_url=APEX)
    assert response.status_code == 200
    body = response.data.decode()
    assert body.startswith("admin:abc123 ")
    assert expected_substring in body


def test_secret_page_home(client: FlaskClient) -> None:
    response = client.get("/abc123/", base_url=APEX)
    assert response.status_code == 200
    assert response.data.decode() == "page:abc123 home GET (TODO)"


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_secret_page_named(client: FlaskClient, method: str) -> None:
    response = client.open("/abc123/about", method=method, base_url=APEX)
    assert response.status_code == 200
    body = response.data.decode()
    assert body == f"page:abc123 page=about m=view {method} (TODO)"


def test_secret_page_mode_query_param(client: FlaskClient) -> None:
    response = client.get("/abc123/some-page?m=edit", base_url=APEX)
    assert response.status_code == 200
    assert "m=edit" in response.data.decode()


@pytest.mark.parametrize(
    ("secret_path", "subdomain_path"),
    [
        ("/abc123/", "/"),
        ("/abc123/about", "/about"),
        ("/abc123/site/claim", "/site/claim"),
        ("/abc123/site/signin", "/site/signin"),
        ("/abc123/admin/settings", "/admin/settings"),
        ("/abc123/admin/design", "/admin/design"),
    ],
)
def test_secret_and_subdomain_share_handler(
    client: FlaskClient, secret_path: str, subdomain_path: str
) -> None:
    secret = client.get(secret_path, base_url=APEX)
    subdomain = client.get(subdomain_path, base_url="http://abc123.jottit.test/")
    assert secret.status_code == subdomain.status_code == 200
    assert secret.data == subdomain.data


def test_apex_static_routes_still_win_over_secret_prefix(client: FlaskClient) -> None:
    # `/about` on the apex must hit root_bp.about, not secret_bp's
    # `/<site_slug>/` with site_slug="about" (Flask prefers static over
    # converter rules of the same length).
    response = client.get("/about", base_url=APEX)
    assert response.status_code == 200
    assert response.data.decode() == "jottit:about (TODO)"
