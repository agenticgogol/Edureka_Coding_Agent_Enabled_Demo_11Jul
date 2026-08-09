"""Regression test tied to incident "checkout API returns 500 on large
carts". Currently FAILS against the buggy `cart.calculate_cart_total`
(16-bit wraparound) and is expected to PASS once the patch removes the
`_wrap_16bit` call (accumulating with a plain Python int instead).

This is the exact test `run_tests` re-executes after `apply_patch`.
"""
from __future__ import annotations

import sys

from cart import CartItem, calculate_cart_total
from checkout_api import CheckoutError, checkout_safe


def test_large_cart_total_is_not_negative():
    # 80 items at $20 (2000 cents), qty 2 each: line_total = 4000 cents.
    # Against the buggy 16-bit-wraparound accumulator this wraps around to
    # a negative running total partway through the loop.
    items = [
        CartItem(sku=f"SKU-BULK-{i}", unit_price_cents=2000, quantity=2)
        for i in range(80)
    ]
    total = calculate_cart_total(items)
    assert total >= 0, f"cart total wrapped around to a negative value: {total}"

    expected_total = sum(item.unit_price_cents * item.quantity for item in items)
    assert total == expected_total, (
        f"cart total does not match the true sum: got {total}, expected {expected_total}"
    )


def test_large_cart_checkout_does_not_500():
    items = [
        CartItem(sku=f"SKU-BULK-{i}", unit_price_cents=2000, quantity=2)
        for i in range(80)
    ]
    try:
        result = checkout_safe(items)
    except CheckoutError as exc:
        raise AssertionError(f"checkout raised CheckoutError (would surface as HTTP 500): {exc}")

    assert result["status"] == "ok"
    assert result["total_cents"] == 320000


def test_small_cart_still_works():
    items = [CartItem(sku="SKU-WIDGET", unit_price_cents=999, quantity=2)]
    result = checkout_safe(items)
    assert result["status"] == "ok"
    assert result["total_cents"] == 1998


if __name__ == "__main__":
    tests = [
        test_large_cart_total_is_not_negative,
        test_large_cart_checkout_does_not_500,
        test_small_cart_still_works,
    ]
    failures = 0
    for t in tests:
        try:
            t()
            print(f"PASS: {t.__name__}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL: {t.__name__}: {e}")
    if failures:
        print(f"\n{failures}/{len(tests)} tests failed")
        sys.exit(1)
    print(f"\nAll {len(tests)} tests passed")
