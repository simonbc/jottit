from __future__ import annotations

import pytest
from flask.testing import FlaskClient

SITE_BASE = "http://mysite.jottit.test/"


@pytest.mark.parametrize(
    ("method", "path", "expected_substring"),
    [
        # /site/claim, /site/signin, /site/signout, /site/forgot-password,
        # and /site/change-password are exercised end-to-end in
        # tests/test_claim.py, tests/test_signin.py, and
        # tests/test_password_recovery.py.
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
        # /admin/settings is exercised end-to-end in tests/test_admin_settings.py.
        ("GET", "/admin/design", "admin/design GET"),
        ("POST", "/admin/design", "admin/design POST"),
        # /admin/url-available and /admin/change-site-address are exercised
        # end-to-end in tests/test_admin_change_site_address.py.
        ("GET", "/admin/delete", "admin/delete GET"),
        ("POST", "/admin/delete", "admin/delete POST"),
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


# Page routes are exercised end-to-end in tests/test_page_view.py.


def test_root_blueprint_still_works_alongside_subdomains(client: FlaskClient) -> None:
    response = client.get("/about", base_url="http://jottit.test/")
    assert response.status_code == 200
    assert response.data.decode() == "jottit:about (TODO)"
