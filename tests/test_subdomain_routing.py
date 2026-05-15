from __future__ import annotations

import pytest
from flask.testing import FlaskClient

SITE_BASE = "http://mysite.jottit.test/"


@pytest.mark.parametrize(
    ("method", "path", "expected_substring"),
    [
        # /site/claim, /site/signin, /site/signout, /site/forgot-password,
        # /site/change-password, and /site/changes are exercised end-to-end
        # in their respective test files.
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


# /admin/* routes are exercised end-to-end in tests/test_admin_*.py.
# Page routes are exercised end-to-end in tests/test_page_view.py.


def test_root_blueprint_still_works_alongside_subdomains(client: FlaskClient) -> None:
    response = client.get("/about", base_url="http://jottit.test/")
    assert response.status_code == 200
    assert response.data.decode() == "jottit:about (TODO)"
