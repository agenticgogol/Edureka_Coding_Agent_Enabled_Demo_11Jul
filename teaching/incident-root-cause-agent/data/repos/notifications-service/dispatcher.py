"""Notification dispatch queue for notifications-service (synthetic,
working code — simulates sending, doesn't call a real network)."""
from __future__ import annotations

from templates import render_template

SENT_LOG: list[dict] = []


def dispatch(channel: str, recipient: str, template_name: str, **kwargs) -> dict:
    if channel not in ("email", "sms", "push"):
        raise ValueError(f"unsupported channel: {channel}")
    body = render_template(template_name, **kwargs)
    record = {"channel": channel, "recipient": recipient, "body": body}
    SENT_LOG.append(record)
    return record
