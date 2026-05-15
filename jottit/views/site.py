from __future__ import annotations

from flask import request


def claim(site_slug: str) -> str:
    return f"site:{site_slug} site/claim {request.method} (TODO)"


def signin(site_slug: str) -> str:
    return f"site:{site_slug} site/signin {request.method} (TODO)"


def signout(site_slug: str) -> str:
    return f"site:{site_slug} site/signout POST (TODO)"


def forgot_password(site_slug: str) -> str:
    return f"site:{site_slug} site/forgot-password {request.method} (TODO)"


def change_password(site_slug: str) -> str:
    return f"site:{site_slug} site/change-password {request.method} (TODO)"


def changes(site_slug: str) -> str:
    return f"site:{site_slug} site/changes GET (TODO)"


def changes_atom(site_slug: str) -> str:
    return f"site:{site_slug} site/changes.atom GET (TODO)"


def hide_primer(site_slug: str) -> str:
    return f"site:{site_slug} site/hide-primer POST (TODO)"
