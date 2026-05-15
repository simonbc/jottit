from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Engine,
    ForeignKey,
    Integer,
    MetaData,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
    text,
)

metadata = MetaData()

_UTC_NOW = text("(current_timestamp at time zone 'utc')")

sites = Table(
    "sites",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("secret_url", Text, nullable=False, index=True),
    Column("public_url", Text, index=True),
    Column("title", Text),
    Column("subtitle", Text),
    Column("email", Text),
    Column("password", Text),
    Column("change_pwd_token", Text),
    Column("security", Text),  # private | public | open
    Column("show_primer", Boolean, nullable=False, server_default=text("true")),
    Column("deleted", Boolean, nullable=False, server_default=text("false")),
    Column("created", DateTime, nullable=False, server_default=_UTC_NOW),
    Column("updated", DateTime),
    Column("partner", Text),
)

designs = Table(
    "designs",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("site_id", Integer, ForeignKey("sites.id"), nullable=False, index=True),
    Column("header_color", Text),
    Column("title_color", Text),
    Column("title_font", Text),
    Column("title_size", Integer, server_default=text("100")),
    Column("subtitle_color", Text),
    Column("subtitle_font", Text),
    Column("subtitle_size", Integer, server_default=text("100")),
    Column("content_font", Text),
    Column("content_size", Integer, server_default=text("100")),
    Column("headings_font", Text),
    Column("headings_size", Integer, server_default=text("100")),
    Column("hue", Text),
    Column("brightness", Text),
)

pages = Table(
    "pages",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("site_id", Integer, ForeignKey("sites.id"), nullable=False, index=True),
    Column("name", Text, nullable=False),
    Column("caret_pos", Integer, nullable=False, server_default=text("0")),
    Column("scroll_pos", Integer, nullable=False, server_default=text("0")),
    Column("deleted", Boolean, nullable=False, server_default=text("false")),
    Column("created", DateTime, nullable=False, server_default=_UTC_NOW),
    UniqueConstraint("site_id", "name", name="pages_site_id_name_key"),
)

revisions = Table(
    "revisions",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("page_id", Integer, ForeignKey("pages.id"), nullable=False, index=True),
    Column("revision", Integer, nullable=False),
    Column("content", Text, nullable=False),
    Column("changes", Text),
    Column("ip", Text),
    Column("created", DateTime, nullable=False, server_default=_UTC_NOW),
)

drafts = Table(
    "drafts",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("page_id", Integer, ForeignKey("pages.id"), nullable=False),
    Column("content", Text, nullable=False),
    Column("created", DateTime, nullable=False, server_default=_UTC_NOW),
)


def make_engine(database_url: str) -> Engine:
    return create_engine(_normalize_postgres_url(database_url), pool_pre_ping=True)


def _normalize_postgres_url(url: str) -> str:
    # Fly.io emits `postgres://`; SQLAlchemy + psycopg3 expect `postgresql+psycopg://`.
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and "+psycopg" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url
