"""Cart total calculation for checkout-service.

Synthetic bug (seeded intentionally for the teaching demo): when a cart
has a large number of line items / high line totals, ``calculate_cart_total``
truncates the running total using a fixed-width 16-bit signed integer
wraparound emulation, instead of using Python's native arbitrary-precision
ints. This mimics the classic "integer overflow in cart total" bug family
seen in statically-typed checkout services, ported here in Python so the
bug is reachable without needing an actual native fixed-width int type.

Concretely: `_wrap_16bit` mimics int16 wraparound. For large carts (many
items or high unit prices/quantities), the running total overflows the
simulated 16-bit range and wraps around to a negative number, which then
causes `checkout_api.checkout` to raise an assertion, surfacing to the
caller as a 500.
"""
from __future__ import annotations

from dataclasses import dataclass

INT16_MIN = -32768
INT16_MAX = 32767


@dataclass
class CartItem:
    sku: str
    unit_price_cents: int
    quantity: int


def _wrap_16bit(value: int) -> int:
    """Emulate signed 16-bit integer wraparound (the seeded bug).

    Real-world equivalent: a checkout service written in a language with
    fixed-width integers (e.g. int16/short) whose running-total accumulator
    was never upgraded to a wider type as cart sizes grew.
    """
    range_size = INT16_MAX - INT16_MIN + 1
    wrapped = (value - INT16_MIN) % range_size + INT16_MIN
    return wrapped


def calculate_cart_total(items: list[CartItem]) -> int:
    """Return the cart total in cents.

    BUG: uses `_wrap_16bit` on the running total, so large carts (many
    items and/or high price*quantity) silently wrap around to a negative
    or corrupted total instead of growing normally. This is the root
    cause behind "checkout API returns 500 on large carts" — a corrupted
    negative total fails a downstream `assert total_cents >= 0` in
    `checkout_api.checkout`.

    THE FIX (for the teaching demo's draft_patch/apply_patch flow): drop
    the `_wrap_16bit` call and accumulate using a plain Python int, which
    has no fixed-width overflow.
    """
    total = 0
    for item in items:
        line_total = item.unit_price_cents * item.quantity
        total = _wrap_16bit(total + line_total)
    return total


def calculate_item_count(items: list[CartItem]) -> int:
    return sum(item.quantity for item in items)
