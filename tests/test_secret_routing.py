from __future__ import annotations

import pytest
from flask.testing import FlaskClient

APEX = "http://jottit.test/"


@pytest.mark.parametrize(
    ("method", "path", "expected_substring"),
    [
        # /site/claim, /site/signin, /site/signout, /site/forgot-password,
        # and /site/change-password are exercised end-to-end in
        # tests/test_claim.py, tests/test_signin.py, and
        # tests/test_password_recovery.py.
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


# /admin/* routes via the secret blueprint are exercised end-to-end in
# tests/test_admin_*.py. Page routes are in tests/test_page_view.py.
# Handler-parity between subdomain and secret blueprints is implicit in
# those files: each admin test has a "via secret URL" case.


def test_apex_static_routes_still_win_over_secret_prefix(client: FlaskClient) -> None:
    # `/about` on the apex must hit root_bp.about, not secret_bp's
    # `/<site_slug>/` with site_slug="about" (Flask prefers static over
    # converter rules of the same length).
    response = client.get("/about", base_url=APEX)
    assert response.status_code == 200
    assert response.data.decode() == "jottit:about (TODO)"
