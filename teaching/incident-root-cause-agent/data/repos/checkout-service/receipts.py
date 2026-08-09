"""Receipt formatting for checkout-service (unrelated to the seeded bug;
adds repo-search surface / a plausible red herring file)."""
from __future__ import annotations


def format_receipt(total_cents: int, item_count: int) -> str:
    dollars = total_cents / 100
    return f"Order total: ${dollars:.2f} ({item_count} items)"
