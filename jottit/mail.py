"""Outbound email.

Two backends, picked at send time by the env:

- Resend HTTP API when `RESEND_API_KEY` and `MAIL_FROM` are set
  (production path; see https://resend.com/docs/api-reference).
- An in-process outbox otherwise (dev + tests inspect what would
  have been sent without making a network call).

The outbox is always populated, so tests can assert what we tried to
send even when the live backend isn't wired.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import requests
from flask import current_app


@dataclass
class SentEmail:
    to: str
    subject: str
    body: str


@dataclass
class Outbox:
    sent: list[SentEmail] = field(default_factory=list)


def outbox() -> Outbox:
    extensions = current_app.extensions
    if "outbox" not in extensions:
        extensions["outbox"] = Outbox()
    return extensions["outbox"]


def send(*, to: str, subject: str, body: str) -> None:
    """Send an outbound email. Records the attempt in the outbox either way."""
    current_app.logger.info("mail: to=%s subject=%r", to, subject)
    outbox().sent.append(SentEmail(to=to, subject=subject, body=body))

    api_key = os.environ.get("RESEND_API_KEY")
    sender = os.environ.get("MAIL_FROM")
    if not api_key or not sender:
        return

    try:
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={"from": sender, "to": to, "subject": subject, "text": body},
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException:
        # Don't bubble up — the user-visible action (claim / forgot-password)
        # should still succeed; missed emails surface in app logs.
        current_app.logger.exception("mail: Resend delivery failed (to=%s)", to)
