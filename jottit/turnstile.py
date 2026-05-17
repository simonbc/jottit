"""Cloudflare Turnstile verification.

When TURNSTILE_SECRET is unset (local dev, tests), verify() short-
circuits to True so the form remains usable. In production, set both
TURNSTILE_SITEKEY (template) and TURNSTILE_SECRET (server) — a missing
or invalid token rejects the request.
"""

from __future__ import annotations

import os

import requests
from flask import request

_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def sitekey() -> str:
    """Public site key for the <div data-sitekey="…"> attribute."""
    return os.environ.get("TURNSTILE_SITEKEY", "")


def verify() -> bool:
    """Verify the `cf-turnstile-response` token from the current request.

    Returns True if Turnstile isn't configured (dev), if the token is
    valid, or — defensive — if Cloudflare itself errors out (so an
    outage there doesn't take down site creation).
    """
    secret = os.environ.get("TURNSTILE_SECRET", "")
    if not secret:
        return True

    token = request.form.get("cf-turnstile-response", "")
    if not token:
        return False

    try:
        response = requests.post(
            _VERIFY_URL,
            data={"secret": secret, "response": token, "remoteip": request.remote_addr or ""},
            timeout=5,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        # Defensive: Cloudflare reachability problems should not block
        # legitimate users. Spam waves still get blocked by the rest of
        # the stack.
        return True

    return bool(payload.get("success"))
