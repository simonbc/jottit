from __future__ import annotations

import random
from dataclasses import dataclass

from flask import current_app, g
from sqlalchemy import (
    Boolean,
    Column,
    Connection,
    DateTime,
    Engine,
    ForeignKey,
    Integer,
    MetaData,
    Row,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
    func,
    insert,
    or_,
    select,
    text,
    update,
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


# ---- Color schemes for new-site design defaults ----

_AMBIGUOUS_CHARS = "0o1li"  # characters omitted from generated secret URLs


@dataclass(frozen=True)
class ColorScheme:
    header_color: str
    title_color: str
    subtitle_color: str
    hue: str
    brightness: str


COLOR_SCHEMES: list[ColorScheme] = [
    ColorScheme("#520000", "#fff", "#ffbfbf", "0", "214"),
    ColorScheme("#523000", "#fff", "#ffe5bf", "25", "214"),
    ColorScheme("#515200", "#fff", "#feffbf", "43", "214"),
    ColorScheme("#2c5200", "#fff", "#e2ffbf", "62", "214"),
    ColorScheme("#003452", "#fff", "#bfe8ff", "143", "214"),
    ColorScheme("#001152", "#fff", "#bfcdff", "161", "214"),
    ColorScheme("#4d0052", "#fff", "#fbbfff", "210", "214"),
    ColorScheme("#520036", "#fff", "#ffbfe9", "227", "214"),
    ColorScheme("#760000", "#fff", "#ffbfbf", "0", "196"),
    ColorScheme("#764000", "#fff", "#ffe2bf", "23", "196"),
    ColorScheme("#087600", "#fff", "#c4ffbf", "82", "196"),
    ColorScheme("#004876", "#fff", "#bfe6ff", "144", "196"),
    ColorScheme("#760043", "#fff", "#ffbfe3", "231", "196"),
    ColorScheme("#92e600", "#000", "#3a5c00", "58", "140"),
    ColorScheme("#d7ecff", "#000", "#003566", "148", "20"),
    ColorScheme("#d8ffd7", "#000", "#026600", "84", "20"),
    ColorScheme("#fcd7ff", "#000", "#5e0066", "209", "20"),
    ColorScheme("#ffffd7", "#000", "#656600", "43", "20"),
    ColorScheme("#ffd7d7", "#000", "#660000", "0", "20"),
    ColorScheme("#d7fff9", "#000", "#006656", "121", "20"),
    ColorScheme("#d7d7ff", "#000", "#000066", "170", "20"),
]


def _to_base36(n: int) -> str:
    if n == 0:
        return "0"
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
    out: list[str] = []
    while n:
        n, r = divmod(n, 36)
        out.append(alphabet[r])
    return "".join(reversed(out))


def _generate_secret_url_candidate() -> str:
    """Random base36 slug, retrying until none of `_AMBIGUOUS_CHARS` appears."""
    while True:
        s = _to_base36(random.randrange(50000, 60000000))
        if not any(c in _AMBIGUOUS_CHARS for c in s):
            return s


def _generate_unique_secret_url(conn: Connection) -> str:
    while True:
        candidate = _generate_secret_url_candidate()
        existing = conn.execute(
            select(sites.c.id).where(
                or_(sites.c.secret_url == candidate, sites.c.public_url == candidate)
            )
        ).first()
        if existing is None:
            return candidate


# ---- Query helpers ----


def get_site(
    conn: Connection,
    *,
    secret_url: str | None = None,
    public_url: str | None = None,
    site_id: int | None = None,
) -> Row | None:
    """Look up a site by one or more of the provided criteria (AND'd)."""
    conditions = []
    if secret_url is not None:
        conditions.append(sites.c.secret_url == secret_url)
    if public_url is not None:
        conditions.append(sites.c.public_url == public_url)
    if site_id is not None:
        conditions.append(sites.c.id == site_id)

    if not conditions:
        raise ValueError("get_site requires at least one of secret_url, public_url, site_id")

    return conn.execute(select(sites).where(*conditions)).first()


def get_page(
    conn: Connection,
    *,
    site_id: int,
    page_name: str,
) -> Row | None:
    """Look up a page within a site by name (case-insensitive)."""
    stmt = (
        select(pages)
        .where(
            pages.c.site_id == site_id,
            func.lower(pages.c.name) == page_name.lower(),
        )
        .limit(1)
    )
    return conn.execute(stmt).first()


def get_revision(
    conn: Connection,
    *,
    page_id: int,
    revision: int | None = None,
) -> Row | None:
    """Return a specific revision (when `revision` is given) or the latest one.

    Always filters to `revision > 0` for the latest case (mirrors the original;
    revision 0 was reserved as a sentinel that's never actually inserted, but
    the filter is kept for fidelity).
    """
    stmt = select(revisions).where(revisions.c.page_id == page_id)
    if revision is not None:
        stmt = stmt.where(revisions.c.revision == revision)
    else:
        stmt = stmt.where(revisions.c.revision > 0).order_by(revisions.c.revision.desc())
    return conn.execute(stmt.limit(1)).first()


def new_page(
    conn: Connection,
    *,
    site_id: int,
    name: str,
    content: str,
    ip: str | None = None,
    scroll_pos: int = 0,
    caret_pos: int = 0,
) -> int:
    """Insert a page row plus its first revision (revision=1). Returns page_id.

    Also updates `sites.updated` to the revision's created timestamp — Jottit
    denormalizes "last activity" onto the site row to avoid joining to revisions
    when listing sites by recency.
    """
    page_id = conn.execute(
        insert(pages)
        .values(site_id=site_id, name=name, scroll_pos=scroll_pos, caret_pos=caret_pos)
        .returning(pages.c.id)
    ).scalar_one()

    revision_row = conn.execute(
        insert(revisions)
        .values(
            page_id=page_id,
            revision=1,
            content=content,
            changes="<em>Created page</em>",
            ip=ip,
        )
        .returning(revisions.c.created)
    ).one()

    conn.execute(update(sites).where(sites.c.id == site_id).values(updated=revision_row.created))

    return page_id


def new_site(
    conn: Connection,
    *,
    content: str,
    ip: str | None = None,
    secret_url: str | None = None,
    public_url: str | None = None,
    partner: str | None = None,
    scroll_pos: int = 0,
    caret_pos: int = 0,
) -> int:
    """Create a site with one home page. Returns site_id.

    Picks a random `ColorScheme` for the design defaults; generates a unique
    `secret_url` if one isn't supplied. Caller manages the transaction boundary.
    """
    if not secret_url:
        secret_url = _generate_unique_secret_url(conn)

    scheme = random.choice(COLOR_SCHEMES)

    site_id = conn.execute(
        insert(sites)
        .values(
            secret_url=secret_url,
            public_url=public_url or None,
            partner=partner or None,
        )
        .returning(sites.c.id)
    ).scalar_one()

    conn.execute(
        insert(designs).values(
            site_id=site_id,
            title_font="Lucida_Grande",
            subtitle_font="Lucida_Grande",
            headings_font="Lucida_Grande",
            content_font="Lucida_Grande",
            header_color=scheme.header_color,
            title_color=scheme.title_color,
            subtitle_color=scheme.subtitle_color,
            hue=scheme.hue,
            brightness=scheme.brightness,
        )
    )

    new_page(
        conn,
        site_id=site_id,
        name="",
        content=content,
        ip=ip,
        scroll_pos=scroll_pos,
        caret_pos=caret_pos,
    )

    return site_id


# ---- Request-scoped connection management ----


def get_request_conn() -> Connection | None:
    """Return the connection scoped to the current request, opening one if needed.

    Reuses `g.db_conn` if already present (e.g. set by a test fixture);
    otherwise opens a fresh connection from the app's engine, begins a
    transaction, and marks it for closing at teardown. Returns `None` if
    no engine is configured.
    """
    if "db_conn" in g:
        return g.db_conn

    engine = current_app.extensions.get("db_engine")
    if engine is None:
        return None

    g.db_conn = engine.connect()
    g._db_txn = g.db_conn.begin()
    g._db_conn_owned = True
    return g.db_conn


def close_request_conn(exc: BaseException | None) -> None:
    """teardown_request hook: commit or roll back the connection we opened."""
    if not g.get("_db_conn_owned", False):
        return

    txn = g._db_txn
    try:
        if txn.is_active:
            if exc is None:
                txn.commit()
            else:
                txn.rollback()
    finally:
        g.db_conn.close()
