"""Synthetic English seed data for the POC knowledge base.

- KB_ARTICLES: help-center-style articles (procedures/policies) an agent can cite.
- PAST_TICKETS: resolved tickets used as *precedent* during retrieval.

Kept deterministic (no LLM generation) so ingest is free, offline, and repeatable.
"""

KB_ARTICLES = [
    {
        "external_id": "kb-duplicate-charge",
        "title": "Duplicate or double charges",
        "content": (
            "## Duplicate or double charges\n\n"
            "A customer may see two identical charges for a single purchase. The most common causes are: "
            "(1) a genuine duplicate submission (the customer clicked pay twice), or (2) a temporary "
            "authorization hold that appears alongside the final capture and disappears in 5-7 business days.\n\n"
            "### How to resolve\n"
            "1. Ask for the last 4 digits of the card and the charge dates/amounts.\n"
            "2. Check whether one entry is a pending authorization (not a real charge). Pending holds are "
            "released automatically within 7 business days and should not be refunded.\n"
            "3. If two settled charges exist for the same order, issue a refund for the duplicate.\n"
            "4. Refunds return to the original payment method in 5-10 business days.\n\n"
            "Policy: never refund a pending authorization; explain it will drop off automatically."
        ),
    },
    {
        "external_id": "kb-refund-policy",
        "title": "Refund policy and timelines",
        "content": (
            "## Refund policy and timelines\n\n"
            "Refunds can be issued in full or partially within 90 days of the original payment. After 90 days, "
            "the original charge can no longer be refunded and a manual bank transfer is required.\n\n"
            "### Timelines\n"
            "- Card refunds: 5-10 business days to appear on the customer's statement.\n"
            "- The money is returned to the original payment method only; we cannot refund to a different card.\n\n"
            "### Eligibility\n"
            "Subscriptions are refundable for the current period if cancelled within 14 days of renewal. "
            "One-time purchases are refundable if the service was not delivered."
        ),
    },
    {
        "external_id": "kb-subscription-cancel",
        "title": "Cancelling a subscription",
        "content": (
            "## Cancelling a subscription\n\n"
            "Customers can cancel anytime from Billing > Manage plan. Cancellation stops the next renewal; "
            "access continues until the end of the current billing period.\n\n"
            "### Refund on cancellation\n"
            "If a customer cancels within 14 days of an automatic renewal and has not used the service heavily, "
            "issue a prorated or full refund for the current period at the agent's discretion.\n\n"
            "To stop an upcoming renewal without refunding, simply cancel before the renewal date."
        ),
    },
    {
        "external_id": "kb-failed-payment",
        "title": "Failed or declined payments",
        "content": (
            "## Failed or declined payments\n\n"
            "Payments fail for reasons including insufficient funds, expired cards, incorrect CVC, or the bank's "
            "fraud checks. The customer's bank ultimately decides whether to approve a charge.\n\n"
            "### How to resolve\n"
            "1. Ask the customer to verify card number, expiry, and CVC.\n"
            "2. Suggest trying another card or contacting their bank to authorize the merchant.\n"
            "3. For subscriptions, failed renewals retry automatically for 7 days (dunning) before the plan lapses.\n"
        ),
    },
    {
        "external_id": "kb-chargeback-dispute",
        "title": "Chargebacks and disputes",
        "content": (
            "## Chargebacks and disputes\n\n"
            "A chargeback happens when a customer disputes a charge with their bank instead of requesting a refund "
            "from us. Chargebacks incur a fee and should be prevented by resolving issues directly.\n\n"
            "### Guidance\n"
            "- If a customer threatens a chargeback, offer a refund first — it is cheaper and faster.\n"
            "- If a chargeback is already open, we cannot also issue a refund (that would double-refund); respond "
            "to the dispute with evidence instead.\n"
            "- Escalate suspected fraudulent disputes to the risk team."
        ),
    },
    {
        "external_id": "kb-update-payment-method",
        "title": "Updating a payment method",
        "content": (
            "## Updating a payment method\n\n"
            "Customers can add or change cards in Billing > Payment methods. The new card becomes the default for "
            "future charges; existing scheduled charges use whichever card is default at renewal time.\n\n"
            "If a renewal failed because a card expired, ask the customer to add a valid card and then retry the "
            "invoice from the Billing page."
        ),
    },
    {
        "external_id": "kb-invoice-receipt",
        "title": "Invoices and receipts",
        "content": (
            "## Invoices and receipts\n\n"
            "A receipt is emailed automatically after every successful payment. Customers can download past invoices "
            "and receipts from Billing > Invoice history. VAT/tax IDs can be added to invoices before download.\n\n"
            "If a customer did not receive a receipt, confirm the email on file and re-send from the invoice page."
        ),
    },
    {
        "external_id": "kb-3ds-authentication",
        "title": "3-D Secure authentication prompts",
        "content": (
            "## 3-D Secure authentication\n\n"
            "Some payments require 3-D Secure (3DS) — an extra verification step (SMS code or bank app approval) "
            "mandated by the customer's bank, especially in Europe (SCA). A payment can be declined if 3DS is not "
            "completed.\n\n"
            "### How to resolve\n"
            "Ask the customer to complete the bank's verification prompt, ensure pop-ups are allowed, and retry. "
            "If the bank app never prompts, advise contacting the bank to enable online authentication."
        ),
    },
]


PAST_TICKETS = [
    {
        "external_id": "TKT-1001", "category": "billing", "priority": "high",
        "subject": "Charged twice for my monthly plan",
        "body": "I see two charges of $29 on the same day for my subscription. I only signed up once.",
        "resolution": "Confirmed two settled charges for the same invoice; refunded the duplicate $29. "
                      "Refund posts in 5-10 business days.",
    },
    {
        "external_id": "TKT-1002", "category": "billing", "priority": "medium",
        "subject": "Pending charge looks like a double charge",
        "body": "There are two $50 entries but one says pending. Did you charge me twice?",
        "resolution": "Explained the pending entry is an authorization hold that drops off within 7 business days; "
                      "no refund needed.",
    },
    {
        "external_id": "TKT-1003", "category": "refund", "priority": "medium",
        "subject": "Refund not received yet",
        "body": "You refunded me 3 days ago but I don't see the money.",
        "resolution": "Card refunds take 5-10 business days; provided the refund ID and asked to wait until day 10.",
    },
    {
        "external_id": "TKT-1004", "category": "refund", "priority": "low",
        "subject": "Can I get a refund after 4 months?",
        "body": "I want a refund for a charge from four months ago.",
        "resolution": "Charge is older than 90 days and cannot be refunded to the card; opened a manual bank "
                      "transfer request.",
    },
    {
        "external_id": "TKT-1005", "category": "subscription", "priority": "medium",
        "subject": "Cancel and refund my renewal",
        "body": "My plan auto-renewed yesterday but I meant to cancel. Please refund and cancel.",
        "resolution": "Within the 14-day renewal window; cancelled the plan and issued a full refund for the period.",
    },
    {
        "external_id": "TKT-1006", "category": "subscription", "priority": "low",
        "subject": "How do I stop auto-renewal?",
        "body": "I don't want to be charged next month.",
        "resolution": "Guided the customer to Billing > Manage plan > Cancel; access continues until period end.",
    },
    {
        "external_id": "TKT-1007", "category": "payment_failure", "priority": "high",
        "subject": "My card keeps getting declined",
        "body": "I try to pay but it always fails. My card works elsewhere.",
        "resolution": "Card failed bank fraud check; customer authorized the merchant with their bank and payment "
                      "succeeded.",
    },
    {
        "external_id": "TKT-1008", "category": "payment_failure", "priority": "medium",
        "subject": "Renewal failed, plan expired",
        "body": "My subscription lapsed because payment failed.",
        "resolution": "Expired card; customer added a new card and we retried the invoice successfully.",
    },
    {
        "external_id": "TKT-1009", "category": "dispute", "priority": "high",
        "subject": "I'm going to dispute this with my bank",
        "body": "This charge is wrong and I'll call my bank to reverse it.",
        "resolution": "Offered and issued a refund proactively to avoid a chargeback; customer agreed not to dispute.",
    },
    {
        "external_id": "TKT-1010", "category": "dispute", "priority": "high",
        "subject": "Chargeback already opened, still want refund",
        "body": "I opened a dispute with my bank but also want you to refund me.",
        "resolution": "Explained we cannot refund while a chargeback is open (double refund); responding to the "
                      "dispute instead.",
    },
    {
        "external_id": "TKT-1011", "category": "billing", "priority": "low",
        "subject": "Need an invoice with my VAT number",
        "body": "Can you add my company VAT ID to the invoice?",
        "resolution": "Added the VAT ID in Billing settings and re-generated the invoice for download.",
    },
    {
        "external_id": "TKT-1012", "category": "billing", "priority": "low",
        "subject": "Didn't get a receipt",
        "body": "I paid but no receipt email arrived.",
        "resolution": "Corrected the email on file and re-sent the receipt from the invoice page.",
    },
    {
        "external_id": "TKT-1013", "category": "payment_failure", "priority": "medium",
        "subject": "Payment asks for a code from my bank",
        "body": "It says I need to authenticate with my bank and then fails.",
        "resolution": "3-D Secure step; customer completed the bank app approval and the payment went through.",
    },
    {
        "external_id": "TKT-1014", "category": "refund", "priority": "medium",
        "subject": "Refund to a different card",
        "body": "Please refund me to my new card, the old one is closed.",
        "resolution": "Refunds must go to the original card; since it's closed, arranged a manual bank transfer.",
    },
    {
        "external_id": "TKT-1015", "category": "subscription", "priority": "low",
        "subject": "Change my card for next renewal",
        "body": "I want future charges on a different card.",
        "resolution": "Customer added the new card as default in Billing > Payment methods for future renewals.",
    },
]
