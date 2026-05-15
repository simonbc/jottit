from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
import pytest
from flask import Flask, g
from flask.testing import FlaskClient
from sqlalchemy import Connection, Engine

from jottit import create_app
from jottit.db import make_engine, metadata

TEST_DB = "jottit_test"


@pytest.fixture(scope="session")
def db_engine() -> Iterator[Engine]:
    """SQLAlchemy engine backed by a fresh `jottit_test` database.

    Connects to the maintenance `postgres` DB with peer auth, drops any
    leftover test DB, creates a clean one, runs `metadata.create_all` once,
    and drops the test DB at session end.
    """
    _admin_sql(f"DROP DATABASE IF EXISTS {TEST_DB}")
    _admin_sql(f"CREATE DATABASE {TEST_DB}")

    engine = make_engine(f"postgresql+psycopg:///{TEST_DB}")
    metadata.create_all(engine)

    yield engine

    engine.dispose()
    _admin_sql(f"DROP DATABASE IF EXISTS {TEST_DB}")


def _admin_sql(statement: str) -> None:
    """Run a DDL statement against the maintenance `postgres` database."""
    with psycopg.connect("dbname=postgres", autocommit=True) as conn:
        conn.execute(statement)  # type: ignore[arg-type]


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
    os.environ.setdefault("SECRET_KEY", "test-secret-key")
    app = create_app()
    app.config.update(TESTING=True, SERVER_NAME="jottit.test")
    app.extensions["db_engine"] = db_engine
    yield app


@pytest.fixture
def client(app: Flask) -> Iterator[FlaskClient]:
    with app.test_client() as c:
        yield c


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
