# 05 — Tools Rework (typed, annotated, gated)

## Purpose
Turn the tool layer from 4 string-returning functions (with a no-op `escalate`) into a designed,
**strictly-typed, annotated, validated** tool surface with a **real human-in-the-loop `escalate`** and
domain-realistic **mock Stripe-like reads**. This registry is the **single source of truth** the MCP
server (spec 03) and the orchestrator loop both import. Lands in `backend/app/tools/registry.py` (spec 01).

## Current state (why it reads as sloppy)
- `tools.py` (~110 LoC): 4 tools returning `json.dumps(...)` **strings**; `escalate` is a **no-op stub**.
- No strict input schema, no output schema, no annotations, minimal validation.
- Byte-identical `hybrid_search` body duplicated in the MCP server (the false "single source of truth").

## Contract — the reworked registry
| Tool | Kind | Upgrade |
|---|---|---|
| `hybrid_search` | read-only | filters (`source_type`, product area); **structured typed hits** with per-source (lexical/semantic/fused) scores |
| `get_document` / `get_ticket` | read-only | strict input schema; structured typed output |
| `lookup_customer` / `get_payment_status` | read-only | **NEW mock Stripe-like reads** over seeded fixtures — real function-calling "against a system" |
| `check_refund_eligibility` | read-only, deterministic | backed by the **`refund-policy` skill script** (spec 04) — ties Tools ↔ Skills |
| `escalate` | **destructive** | **make it real**: DB write + ticket status + returns a handle; **human-in-the-loop approval gate** surfaced in the UI (spec 08) |

### Quality bar (applies to every tool)
- **Strict input schema**: `additionalProperties: false`, `enum`s for closed sets, required fields.
- **Typed structured output**: Pydantic models → `outputSchema` (consumed by MCP), never `json.dumps` blobs.
- **Annotations**: `readOnlyHint` / `destructiveHint` / `idempotentHint` — declared **once** here and
  imported by the MCP server (spec 03), killing the duplication.
- **Input validation + `is_error` recovery** so a bad call degrades gracefully in the loop.
- One shared **row→dict projection helper** used by both the in-process path and the MCP server
  (retires the "single source of truth" contradiction from spec 02).

### The gated `escalate` (the textbook reason a tool exists)
`escalate` performs a real side effect (writes ticket status + creates a handle), but is **gated**: the
orchestrator proposes the escalation, the UI shows an **approval card**, and the write commits only on
human approval. This is the canonical demonstration of *why* a destructive action is promoted to a
dedicated, annotated tool rather than left to free-text.

## 🎓 Teaching note
Function calling is only as good as its **contract**. Strict schemas stop the model inventing
arguments; typed outputs let downstream code trust the result without re-parsing; annotations tell a
client which calls are safe to auto-run vs. which need a human. The gated `escalate` shows the payoff:
the model can *propose* an irreversible action, but a human authorizes it.

## Acceptance
- [ ] Every tool has a strict input schema (`additionalProperties:false`) and a Pydantic-typed output.
- [ ] Annotations are declared once and imported by the MCP server (no duplication; `grep` proves it).
- [ ] `lookup_customer` / `get_payment_status` return seeded fixture data through the agent loop.
- [ ] `check_refund_eligibility` delegates to the `refund-policy` skill script (spec 04).
- [ ] `escalate` writes to the DB **only after UI approval**; without approval, no write occurs.
- [ ] The `hybrid_search`/`dispatch` name storms (spec 02) are resolved in the new registry.

## Cross-refs & sequencing
- **Build first among 03–05** (or in lockstep with 03): the MCP server imports this contract.
- **Depends on spec 01 step 4** (`agents/tools.py` → `tools/registry.py`).
- **Ties to spec 04** (`check_refund_eligibility` ↔ `refund-policy` script) and **spec 08** (approval card).

## Open questions
- Mock fixtures: extend `seed_data.py` with synthetic customers/payments, or a separate `fixtures/`
  module? Recommend fold into the RAG-owned `rag/seed_data.py` seed path for one ingest story.
- `escalate` persistence: reuse the `tickets` table with a `status`/`assignee` column vs a new
  `escalations` table? Confirm against `schema.sql` at build time.
