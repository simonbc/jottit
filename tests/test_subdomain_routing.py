from __future__ import annotations

from flask.testing import FlaskClient

# /site/claim, /site/signin, /site/signout, /site/forgot-password,
# /site/change-password, /site/changes, /site/changes.rss, /site/changes.json,
# and /site/hide-primer are exercised end-to-end in their respective test files.


# /admin/* routes are exercised end-to-end in tests/test_admin_*.py.
# Page routes are exercised end-to-end in tests/test_page_view.py.


def test_root_blueprint_still_works_alongside_subdomains(client: FlaskClient) -> None:
    response = client.get("/about", base_url="http://jottit.test/")
    assert response.status_code == 200
    assert response.data.decode() == "jottit:about (TODO)"
