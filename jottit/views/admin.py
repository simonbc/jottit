from __future__ import annotations

from flask import request


def settings(site_slug: str) -> str:
    return f"admin:{site_slug} admin/settings {request.method} (TODO)"


def design(site_slug: str) -> str:
    return f"admin:{site_slug} admin/design {request.method} (TODO)"


def url_available(site_slug: str) -> str:
    return f"admin:{site_slug} admin/url-available POST (TODO)"


def delete(site_slug: str) -> str:
    return f"admin:{site_slug} admin/delete {request.method} (TODO)"


def change_site_address(site_slug: str) -> str:
    return f"admin:{site_slug} admin/change-site-address {request.method} (TODO)"


def change_password(site_slug: str) -> str:
    return f"admin:{site_slug} admin/change-password {request.method} (TODO)"


def export(site_slug: str) -> str:
    return f"admin:{site_slug} admin/export GET (TODO)"
