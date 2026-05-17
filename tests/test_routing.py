from __future__ import annotations

import pytest
from flask.testing import FlaskClient


@pytest.mark.parametrize(
    ("method", "path", "needle"),
    [
        ("GET", "/about", b"Jottit makes getting a website"),
        ("GET", "/help", b"feedback@jottit.pub"),
        ("GET", "/sites", b"jottit:sites"),
        ("POST", "/sites", b"jottit:sites"),
        ("GET", "/feedback", b"jottit:feedback"),
        ("POST", "/feedback", b"jottit:feedback"),
    ],
)
def test_root_routes_serve_stubs(
    client: FlaskClient, method: str, path: str, needle: bytes
) -> None:
    response = client.open(path, method=method)
    assert response.status_code == 200
    assert needle in response.data
