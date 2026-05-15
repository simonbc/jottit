from __future__ import annotations

import pytest
from flask.testing import FlaskClient


@pytest.mark.parametrize(
    ("method", "path", "stub_prefix"),
    [
        ("GET", "/", b"jottit:index"),
        ("POST", "/", b"jottit:index"),
        ("GET", "/about", b"jottit:about"),
        ("GET", "/help", b"jottit:help"),
        ("GET", "/sites", b"jottit:sites"),
        ("POST", "/sites", b"jottit:sites"),
        ("GET", "/feedback", b"jottit:feedback"),
        ("POST", "/feedback", b"jottit:feedback"),
    ],
)
def test_root_routes_serve_stubs(
    client: FlaskClient, method: str, path: str, stub_prefix: bytes
) -> None:
    response = client.open(path, method=method)
    assert response.status_code == 200
    assert response.data.startswith(stub_prefix)
