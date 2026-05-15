from __future__ import annotations

from sqlalchemy import Connection, insert, select

from jottit.db import sites


def test_sites_round_trip(db_conn: Connection) -> None:
    """A site row inserts cleanly, server defaults fire, and reads back identically."""
    result = db_conn.execute(insert(sites).values(secret_url="abc-test").returning(sites.c.id))
    site_id = result.scalar_one()

    row = db_conn.execute(select(sites).where(sites.c.id == site_id)).one()
    assert row.secret_url == "abc-test"
    assert row.deleted is False
    assert row.show_primer is True
    assert row.created is not None
