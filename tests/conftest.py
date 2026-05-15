from __future__ import annotations

from collections.abc import Iterator

import pytest
from flask import Flask
from flask.testing import FlaskClient

from jottit import create_app


@pytest.fixture
def app() -> Iterator[Flask]:
    app = create_app()
    app.config.update(TESTING=True, SERVER_NAME="jottit.test")
    yield app


@pytest.fixture
def client(app: Flask) -> Iterator[FlaskClient]:
    with app.test_client() as c:
        yield c
