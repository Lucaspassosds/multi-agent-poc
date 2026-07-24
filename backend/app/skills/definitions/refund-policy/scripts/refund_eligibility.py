#!/usr/bin/env python3
"""Deterministic refund-eligibility decision (level-3 skill script).

Invoked by the loader as:  python refund_eligibility.py '<json args>'
Reads facts from argv[1] (JSON), prints a JSON decision to stdout. No I/O, no
network — pure policy logic, so it is repeatable and cheap.
"""
import json
import sys

POLICY_WINDOW_DAYS = 90


def decide(f: dict) -> dict:
    status = (f.get("status") or "").lower()
    days = f.get("days_since_payment")

    if f.get("dispute_open") or status == "disputed":
        return _r(False, "none",
                  "A chargeback/dispute is open; we cannot also issue a refund (double refund).")
    if f.get("refunded") or status == "refunded":
        return _r(False, "none", "This payment was already refunded.")
    if status == "pending":
        return _r(False, "none",
                  "This is a pending authorization hold, not a settled charge; it drops off "
                  "automatically within 7 business days and must not be refunded.")
    if status == "failed":
        return _r(False, "none", "This payment failed, so there is nothing to refund.")
    if f.get("is_subscription") and not f.get("within_renewal_window"):
        return _r(False, "none",
                  "Subscription refunds are only available within 14 days of renewal; this is "
                  "outside that window.")
    if isinstance(days, int) and days > POLICY_WINDOW_DAYS:
        return _r(True, "manual_bank_transfer",
                  f"The charge is older than {POLICY_WINDOW_DAYS} days and can no longer be "
                  "refunded to the card; a manual bank transfer is required.")
    return _r(True, "card_refund",
              "Within the 90-day window; refundable to the original card in 5-10 business days.")


def _r(eligible: bool, method: str, reason: str) -> dict:
    return {"eligible": eligible, "method": method, "reason": reason,
            "policy_window_days": POLICY_WINDOW_DAYS}


if __name__ == "__main__":
    facts = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    print(json.dumps(decide(facts)))
