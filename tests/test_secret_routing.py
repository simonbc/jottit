from __future__ import annotations

from flask.testing import FlaskClient

APEX = "http://jottit.test/"


# /site/claim, /site/signin, /site/signout, /site/forgot-password,
# /site/change-password, /site/changes, /site/changes.rss, /site/changes.json,
# and /site/hide-primer are exercised end-to-end in their respective test files.


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
    assert b"Jottit makes getting a website" in response.data
