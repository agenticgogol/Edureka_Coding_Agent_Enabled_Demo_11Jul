"""Seeds one prior resolved incident into the `incidents` table so
`search_similar_incidents` has a real precedent to match against on a
second demo run, per the build brief.

NOT executed automatically by this module or by `interface.py` — run it
explicitly:

    python -m backend.agent.seed_data

This makes exactly ONE real OpenAI embedding call (see the cost-approval
note in this module's README before running it).
"""
from __future__ import annotations

from . import db
from .llm import embed

SEED_INCIDENT_TEXT = (
    "Checkout API returns 500 for a small number of users with very large "
    "shopping carts (60+ line items). Started after the last checkout-service "
    "deploy. No errors in auth-service or notifications-service."
)

SEED_ROOT_CAUSE = (
    "cart.calculate_cart_total accumulates the running total through "
    "_wrap_16bit, a simulated signed-16-bit integer wraparound. Once the "
    "running total exceeds the 16-bit range, it wraps to a negative number, "
    "which fails the `assert total_cents >= 0` in checkout_api.checkout and "
    "surfaces to callers as an HTTP 500."
)


def seed() -> None:
    db.init_db()
    embedding = embed(SEED_INCIDENT_TEXT)
    db.insert_incident(
        incident_id="seed-incident-0001",
        incident_text=SEED_INCIDENT_TEXT,
        embedding=embedding,
        identified_repo="checkout-service",
        identified_file="cart.py",
        root_cause=SEED_ROOT_CAUSE,
        classification="code-issue",
        matched_precedent_id=None,
        drafted_patch_summary=(
            "Removed the _wrap_16bit call in calculate_cart_total so the "
            "running total accumulates as a plain Python int with no "
            "fixed-width overflow."
        ),
        ticket_id="TCKT-seed0001",
        approval_status="approved",
        test_result="passed",
        outcome="closed_pass",
    )
    print("Seeded 1 prior incident (checkout-service / cart.py overflow) with a real embedding.")


if __name__ == "__main__":
    seed()
