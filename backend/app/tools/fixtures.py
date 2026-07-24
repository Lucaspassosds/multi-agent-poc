"""Mock Stripe-like fixtures (topic: "tools").

An in-process stand-in for an external payments system, so lookup_customer /
get_payment_status / check_refund_eligibility exercise real function-calling
against a "system" without a live Stripe account. Deterministic and offline,
like seed_data.py. Payment ids are referenced from PAST_TICKETS metadata so a
triaged precedent ticket maps to a plausible customer + payment.
"""
from __future__ import annotations

# Each payment carries exactly the fields refund_eligibility.py reasons over.
PAYMENTS: dict[str, dict] = {
    "pay_1001": {  # TKT-1001 duplicate charge — settled, refundable
        "payment_id": "pay_1001", "customer_id": "cust_alice", "amount_usd": 29.0,
        "currency": "usd", "status": "succeeded", "created": "2026-07-18",
        "age_days": 5, "is_subscription": True, "refunded": False,
        "dispute_open": False, "renewal_within_14d": True,
    },
    "pay_1003": {  # TKT-1003 refund already issued
        "payment_id": "pay_1003", "customer_id": "cust_bob", "amount_usd": 49.0,
        "currency": "usd", "status": "refunded", "created": "2026-07-15",
        "age_days": 8, "is_subscription": False, "refunded": True,
        "dispute_open": False, "renewal_within_14d": False,
    },
    "pay_1004": {  # TKT-1004 older than 90 days -> manual bank transfer
        "payment_id": "pay_1004", "customer_id": "cust_carol", "amount_usd": 120.0,
        "currency": "usd", "status": "succeeded", "created": "2026-03-01",
        "age_days": 144, "is_subscription": False, "refunded": False,
        "dispute_open": False, "renewal_within_14d": False,
    },
    "pay_1010": {  # TKT-1010 chargeback open -> not eligible
        "payment_id": "pay_1010", "customer_id": "cust_dave", "amount_usd": 75.0,
        "currency": "usd", "status": "disputed", "created": "2026-07-10",
        "age_days": 13, "is_subscription": False, "refunded": False,
        "dispute_open": True, "renewal_within_14d": False,
    },
    "pay_2001": {  # pending authorization hold -> not a real charge
        "payment_id": "pay_2001", "customer_id": "cust_alice", "amount_usd": 50.0,
        "currency": "usd", "status": "pending", "created": "2026-07-22",
        "age_days": 1, "is_subscription": False, "refunded": False,
        "dispute_open": False, "renewal_within_14d": False,
    },
}

CUSTOMERS: dict[str, dict] = {
    "cust_alice": {
        "customer_id": "cust_alice", "email": "alice@example.com", "name": "Alice Martin",
        "created": "2025-01-12", "lifetime_value_usd": 348.0,
        "subscription_status": "active", "payment_ids": ["pay_1001", "pay_2001"],
    },
    "cust_bob": {
        "customer_id": "cust_bob", "email": "bob@example.com", "name": "Bob Chen",
        "created": "2025-06-03", "lifetime_value_usd": 49.0,
        "subscription_status": "none", "payment_ids": ["pay_1003"],
    },
    "cust_carol": {
        "customer_id": "cust_carol", "email": "carol@example.com", "name": "Carol Diaz",
        "created": "2024-11-20", "lifetime_value_usd": 120.0,
        "subscription_status": "canceled", "payment_ids": ["pay_1004"],
    },
    "cust_dave": {
        "customer_id": "cust_dave", "email": "dave@example.com", "name": "Dave Okoro",
        "created": "2025-09-14", "lifetime_value_usd": 75.0,
        "subscription_status": "none", "payment_ids": ["pay_1010"],
    },
}

EMAIL_INDEX: dict[str, str] = {c["email"].lower(): cid for cid, c in CUSTOMERS.items()}
