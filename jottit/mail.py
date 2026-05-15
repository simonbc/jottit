from __future__ import annotations

from dataclasses import dataclass, field

from flask import current_app

# Log-only mail stub. M8 will swap the body of `send()` for real SMTP and
# keep the outbox shape (or replace it with the equivalent record-mode the
# SMTP backend ships).


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
    """Record an outbound email. Logs a one-liner; full body lives in the outbox."""
    current_app.logger.info("mail: to=%s subject=%r", to, subject)
    outbox().sent.append(SentEmail(to=to, subject=subject, body=body))
