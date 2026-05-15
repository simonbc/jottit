from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from flask import Flask, g
from flask.testing import FlaskClient
from sqlalchemy import Connection, Engine
from testcontainers.postgres import PostgresContainer

from jottit import create_app
from jottit.db import make_engine, metadata


@contextmanager
def request_under_test(
    app: Flask, path: str, *, base_url: str, db_conn: Connection
) -> Iterator[None]:
    """Push a request context with `g.db_conn` pre-set so the resolver sees
    the test's transaction-wrapped data, run preprocess hooks, then trigger
    teardown when the block exits."""
    with app.test_request_context(path, base_url=base_url):
        g.db_conn = db_conn
        try:
            app.preprocess_request()
            yield
        finally:
            app.do_teardown_request(None)


@pytest.fixture(scope="session")
def db_engine() -> Iterator[Engine]:
    with PostgresContainer("postgres:16-alpine", driver="psycopg") as container:
        engine = make_engine(container.get_connection_url())
        metadata.create_all(engine)
        yield engine
        engine.dispose()


@pytest.fixture
def db_conn(db_engine: Engine) -> Iterator[Connection]:
    """A connection in a transaction that is rolled back at teardown."""
    connection = db_engine.connect()
    transaction = connection.begin()
    try:
        yield connection
    finally:
        transaction.rollback()
        connection.close()


@pytest.fixture
def app(db_engine: Engine) -> Iterator[Flask]:
    app = create_app()
    app.config.update(TESTING=True, SERVER_NAME="jottit.test")
    app.extensions["db_engine"] = db_engine
    yield app


@pytest.fixture
def client(app: Flask) -> Iterator[FlaskClient]:
    with app.test_client() as c:
        yield c
