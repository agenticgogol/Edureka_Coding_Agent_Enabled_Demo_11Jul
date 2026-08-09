"""Small pricing helper used by checkout-service (unrelated to the seeded
bug; here so the repo has more than a single-file surface for search_code
to traverse)."""
from __future__ import annotations

from cart import CartItem


def apply_percent_discount(items: list[CartItem], percent: float) -> list[CartItem]:
    """Return a new list of CartItems with unit_price_cents reduced by
    `percent` percent, rounded down to the nearest cent."""
    if not (0 <= percent <= 100):
        raise ValueError("percent must be between 0 and 100")
    factor = 1 - (percent / 100)
    return [
        CartItem(
            sku=item.sku,
            unit_price_cents=int(item.unit_price_cents * factor),
            quantity=item.quantity,
        )
        for item in items
    ]
