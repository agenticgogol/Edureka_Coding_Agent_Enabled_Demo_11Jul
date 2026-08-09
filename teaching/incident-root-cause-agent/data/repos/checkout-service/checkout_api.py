"""Checkout API entrypoint for checkout-service.

Calls into `cart.calculate_cart_total`, which carries the seeded bug (see
cart.py). When the bug triggers on a large cart, the `assert` below fails,
which the HTTP layer (not modeled here — synthetic demo) turns into a 500.
"""
from __future__ import annotations

from cart import CartItem, calculate_cart_total, calculate_item_count


class CheckoutError(Exception):
    """Raised when checkout cannot complete; the real service maps this to
    an HTTP 500 response."""


def checkout(items: list[CartItem]) -> dict:
    """Compute the order summary for a cart and "charge" it (simulated).

    Raises CheckoutError (-> 500) if the computed total is corrupted
    (negative), which is exactly what happens once cart.py's bug
    triggers on a large cart.
    """
    total_cents = calculate_cart_total(items)
    item_count = calculate_item_count(items)

    assert total_cents >= 0, (
        f"CheckoutError: computed cart total is negative ({total_cents} cents) "
        f"for {item_count} items — refusing to charge a corrupted amount."
    )

    return {
        "status": "ok",
        "total_cents": total_cents,
        "item_count": item_count,
    }


def checkout_safe(items: list[CartItem]) -> dict:
    """HTTP-layer-style wrapper: converts the assertion failure into the
    CheckoutError a real web framework would turn into a 500 response."""
    try:
        return checkout(items)
    except AssertionError as exc:
        raise CheckoutError(str(exc)) from exc
