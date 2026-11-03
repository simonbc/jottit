from __future__ import annotations

from sqlalchemy import Connection, insert, select

from jottit.db import metadata, sites, uploads


def test_sites_round_trip(db_conn: Connection) -> None:
    """A site row inserts cleanly, server defaults fire, and reads back identically."""
    result = db_conn.execute(insert(sites).values(secret_url="abc-test").returning(sites.c.id))
    site_id = result.scalar_one()

    row = db_conn.execute(select(sites).where(sites.c.id == site_id)).one()
    assert row.secret_url == "abc-test"
    assert row.deleted is False
    assert row.show_primer is True
    assert row.created is not None


def test_uploads_table_in_metadata() -> None:
    table = metadata.tables["uploads"]
    assert table is uploads
    assert set(table.c.keys()) == {
        "id",
        "site_id",
        "storage_key",
        "filename",
        "content_type",
        "size",
        "ip",
        "created",
    }
    assert {fk.target_fullname for fk in table.c.site_id.foreign_keys} == {"sites.id"}
    assert table.c.storage_key.unique


def test_uploads_round_trip(db_conn: Connection) -> None:
    site_id = db_conn.execute(
        insert(sites).values(secret_url="up-test").returning(sites.c.id)
    ).scalar_one()
    db_conn.execute(
        insert(uploads).values(
            site_id=site_id,
            storage_key=f"sites/{site_id}/a.png",
            filename="a.png",
            content_type="image/png",
            size=3,
            ip="127.0.0.1",
        )
    )

    row = db_conn.execute(select(uploads).where(uploads.c.site_id == site_id)).one()
    assert row.created is not None
