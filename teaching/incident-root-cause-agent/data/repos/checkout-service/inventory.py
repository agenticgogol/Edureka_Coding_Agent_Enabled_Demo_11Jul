"""Inventory availability check for checkout-service (unrelated to the
seeded bug; adds repo-search surface)."""
from __future__ import annotations

from cart import CartItem

# Synthetic in-memory stock levels keyed by SKU.
STOCK: dict[str, int] = {
    "SKU-WIDGET": 500,
    "SKU-GADGET": 120,
    "SKU-GIZMO": 75,
}


def is_in_stock(item: CartItem) -> bool:
    available = STOCK.get(item.sku, 0)
    return available >= item.quantity


def validate_stock(items: list[CartItem]) -> list[str]:
    """Return a list of SKUs that are out of stock for the requested
    quantities; empty list means everything is available."""
    return [item.sku for item in items if not is_in_stock(item)]
