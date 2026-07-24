---
name: refund-policy
description: Decide whether and how a payment can be refunded (90-day card window, subscriptions, disputes, pending holds). Load when a ticket asks about refund eligibility or timelines.
allowed-tools:
  - run_skill_script
  - get_payment_status
---

# Refund Policy

Use this skill to decide **refund eligibility** deterministically instead of guessing.

## When to use
A ticket asks "can I get a refund", references a charge age, a subscription renewal, a
pending charge, or an open dispute.

## How to decide
Do NOT reason about eligibility in prose. Gather the payment facts (via `get_payment_status`
or from the ticket) and run the bundled script:

`run_skill_script(name="refund-policy", script="refund_eligibility.py", args={...})`

Required `args` (see `references/refund-policy.md` for the full rules):
`days_since_payment` (int|null), `status` (str), `refunded` (bool), `dispute_open` (bool),
`is_subscription` (bool), `within_renewal_window` (bool).

The script returns `{eligible, reason, method, policy_window_days}`. Use its `reason`
verbatim as the basis for the customer explanation; never override its verdict.
