---
name: dispute-response
description: How to handle chargebacks and threatened disputes (refund-first, don't double-refund open disputes, escalate suspected fraud). Load for dispute/chargeback tickets.
allowed-tools:
  - hybrid_search
  - escalate
---

# Dispute Response

Guidance for chargeback and dispute tickets.

## Rules
1. If a customer only *threatens* a chargeback, offer a refund first — it is cheaper and faster.
2. If a chargeback is already open, do NOT also refund; respond to the dispute with evidence.
3. Escalate suspected fraudulent disputes to the risk team via `escalate` (severity="high").

See `references/dispute-playbook.md` for phrasing and the evidence checklist.
