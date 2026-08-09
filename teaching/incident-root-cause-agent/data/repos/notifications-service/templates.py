"""Notification templates for notifications-service (synthetic, working
code)."""
from __future__ import annotations

TEMPLATES = {
    "order_confirmed": "Hi {name}, your order #{order_id} is confirmed! Total: ${total}",
    "password_reset": "Hi {name}, click here to reset your password: {reset_link}",
    "shipment_update": "Hi {name}, your order #{order_id} has shipped and will arrive by {eta}.",
}


class UnknownTemplateError(Exception):
    pass


def render_template(template_name: str, **kwargs) -> str:
    if template_name not in TEMPLATES:
        raise UnknownTemplateError(f"no such template: {template_name}")
    return TEMPLATES[template_name].format(**kwargs)
