"""Import a jottit.org export bundle (see jottit.org's export_to_jottit_pub.py)
into a jottit.pub database.

Mapping:
  * each jottit.org profile      -> one site (public_url = username when usable)
      - home page (name="")      <- the profile bio (empty when no bio)
      - each profile page        -> a named page (name = slug)
      - site is *claimed* with a random password + the user's email so the
        owner can regain access via jottit.pub's "Forgot password" form.
  * each unclaimed jottit.org page -> its own standalone site (secret_url only,
        password NULL -> stays unclaimed); the page content becomes the home page.

Full revision history and original timestamps are preserved (direct inserts,
not the new_site/new_page helpers, which force revision=1 and default times).

jottit.pub renders [[...]] as wikilinks; jottit.org content shouldn't contain
them, but any literal "[[" would now be interpreted as a wikilink. No transform
is applied.

Usage:
    DATABASE_URL="dbname=jottit_pub_dev" python scripts/import_from_jottit_org.py bundle.json
"""

from __future__ import annotations

import json
import os
import secrets
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import random

from sqlalchemy import insert, select

from jottit import auth
from jottit.db import (
    COLOR_SCHEMES,
    RESERVED_PUBLIC_URLS,
    _generate_unique_secret_url,
    designs,
    make_engine,
    pages,
    revisions,
    sites,
)

_DEFAULT_FONT = "system-ui, sans-serif"


def _parse_dt(value: str | None) -> datetime | None:
    """Parse an ISO timestamp to a naive UTC datetime (jottit.pub's convention)."""
    if value is None:
        return None
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _insert_design(conn, site_id):
    scheme = random.choice(COLOR_SCHEMES)
    conn.execute(
        insert(designs).values(
            site_id=site_id,
            title_font=_DEFAULT_FONT,
            subtitle_font=_DEFAULT_FONT,
            headings_font=_DEFAULT_FONT,
            content_font=_DEFAULT_FONT,
            header_color=scheme.header_color,
            title_color=scheme.title_color,
            subtitle_color=scheme.subtitle_color,
            hue=scheme.hue,
            brightness=scheme.brightness,
        )
    )


def _insert_page_with_revisions(conn, site_id, name, revisions_data, *, page_created):
    """Insert one page and all of its revisions, preserving numbers + timestamps.

    Returns the latest revision's created datetime (for bumping sites.updated).
    """
    page_id = conn.execute(
        insert(pages)
        .values(site_id=site_id, name=name, created=page_created)
        .returning(pages.c.id)
    ).scalar_one()

    latest_created = None
    ordered = sorted(revisions_data, key=lambda r: r["revision"])
    for i, rev in enumerate(ordered):
        created = _parse_dt(rev["created_at"])
        # `changes` is display-only diff HTML in jottit.pub; we don't synthesize
        # diffs, so mark the first revision as created and leave the rest blank.
        changes = "<em>Created page</em>" if i == 0 else None
        conn.execute(
            insert(revisions).values(
                page_id=page_id,
                revision=rev["revision"],
                content=rev["content"],
                changes=changes,
                created=created,
            )
        )
        if created is not None:
            latest_created = created
    return latest_created


def _import_profile(conn, profile, used_public_urls):
    username = profile.get("username")
    public_url = None
    note = ""
    if username:
        if username in RESERVED_PUBLIC_URLS:
            note = f"username '{username}' is reserved -> secret URL only"
        elif username in used_public_urls:
            note = f"username '{username}' already taken -> secret URL only"
        else:
            existing = conn.execute(
                select(sites.c.id).where(sites.c.public_url == username)
            ).first()
            if existing is not None:
                note = f"public_url '{username}' already exists in DB -> secret URL only"
            else:
                public_url = username
                used_public_urls.add(username)

    site_created = _parse_dt(profile.get("created_at"))
    secret_url = _generate_unique_secret_url(conn)
    password_hash = auth.hash_password(secrets.token_urlsafe(24))

    site_id = conn.execute(
        insert(sites)
        .values(
            secret_url=secret_url,
            public_url=public_url,
            title=profile.get("name") or username,
            email=profile.get("email"),
            password=password_hash,
            security="public",
            created=site_created,
        )
        .returning(sites.c.id)
    ).scalar_one()
    _insert_design(conn, site_id)

    latest = _insert_page_with_revisions(
        conn,
        site_id,
        "",
        [{"revision": 1, "content": profile.get("bio") or "", "created_at": profile.get("created_at")}],
        page_created=site_created,
    )

    for page in profile.get("pages", []):
        page_latest = _insert_page_with_revisions(
            conn,
            site_id,
            page["slug"],
            page["revisions"],
            page_created=_parse_dt(page.get("created_at")),
        )
        if page_latest is not None and (latest is None or page_latest > latest):
            latest = page_latest

    if latest is not None:
        conn.execute(sites.update().where(sites.c.id == site_id).values(updated=latest))

    return secret_url, public_url, note


def _import_unclaimed_page(conn, page):
    site_created = _parse_dt(page.get("created_at"))
    secret_url = _generate_unique_secret_url(conn)
    site_id = conn.execute(
        insert(sites)
        .values(secret_url=secret_url, security="public", created=site_created)
        .returning(sites.c.id)
    ).scalar_one()
    _insert_design(conn, site_id)
    latest = _insert_page_with_revisions(
        conn, site_id, "", page["revisions"], page_created=site_created
    )
    if latest is not None:
        conn.execute(sites.update().where(sites.c.id == site_id).values(updated=latest))
    return secret_url


def _site_url(domain, secret_url, public_url):
    if public_url:
        return f"https://{public_url}.{domain}/"
    return f"https://{domain}/{secret_url}/"


def import_bundle(conn, bundle, *, domain="jottit.pub"):
    """Import a parsed bundle into the DB via `conn`. Returns (owner_rows, unclaimed_count).

    `owner_rows` is a list of (email, site_url, note) for the profile sites.
    The caller owns the transaction boundary.
    """
    owner_rows = []
    used_public_urls: set[str] = set()
    for profile in bundle.get("profiles", []):
        secret_url, public_url, note = _import_profile(conn, profile, used_public_urls)
        owner_rows.append((profile.get("email"), _site_url(domain, secret_url, public_url), note))
    unclaimed = 0
    for page in bundle.get("unclaimed_pages", []):
        _import_unclaimed_page(conn, page)
        unclaimed += 1
    return owner_rows, unclaimed


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: import_from_jottit_org.py <bundle.json>")
    bundle = json.load(open(sys.argv[1]))
    domain = os.environ.get("JOTTIT_DOMAIN", "jottit.pub")

    engine = make_engine(os.environ["DATABASE_URL"])
    with engine.begin() as conn:
        owner_rows, unclaimed = import_bundle(conn, bundle, domain=domain)

    print(f"Imported {len(bundle.get('profiles', []))} sites from profiles, {unclaimed} unclaimed-page sites.\n")
    print("Owner sites (owners use 'Forgot password' to set a password):")
    for email, url, note in owner_rows:
        suffix = f"   [{note}]" if note else ""
        print(f"  {email or '(no email)'}\t{url}{suffix}")


if __name__ == "__main__":
    main()
