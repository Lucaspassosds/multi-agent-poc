# Improvements Phase C — MCP / Skills / Tools Complete Rework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the three interlocking depth specs as one coherent change: a typed, annotated, gated tool **registry** (spec 05) that is the single source of truth; an MCP server exposing **all three primitives** — tools, resources, prompts — importing that registry with zero re-declared schemas/annotations (spec 03); and a real skill **library** with three-level progressive disclosure, a bundled executable script, and model-driven selection (spec 04). The three share ONE tool contract, which is why they are planned together.

**Architecture:** `app/tools/registry.py` owns the contract: Pydantic **input** models (validation) + hand-authored flat JSON input schemas (Gemini-safe) + Pydantic **output** models (→ MCP `outputSchema`) + a single `ANNOTATIONS` table (`readOnlyHint`/`destructiveHint`/`idempotentHint`) + a shared row→hit projection. `app/mcp/server.py` imports the registry's tool coroutines, output models, and `ANNOTATIONS` — declaring nothing itself — and adds resources (`kb://doc/{id}`, `kb://index`, `ticket://{id}`, `skill://{name}`) and prompts (`/triage-refund`, `/draft-reply`, `/summarize-thread`). `app/skills/loader.py` gains a real YAML frontmatter parser, three-level disclosure, and `load_skill`/`run_skill_script`; `app/skills/definitions/` holds ≥3 skills including `refund-policy/scripts/refund_eligibility.py`. The `check_refund_eligibility` tool delegates to that script (Tools ↔ Skills). `escalate` is a **pure proposal** — it writes nothing; a new `POST /agent/escalations` approve endpoint is the only writer (Human-in-the-loop gate). The orchestrator's retrieve step is routed through the MCP client with an in-process fallback, making MCP load-bearing.

**Tech Stack:** Python 3.12 + FastAPI + asyncpg/pgvector + Pydantic v2; `mcp` **1.28.1** (FastMCP) — verified in-container: `@mcp.tool(annotations=ToolAnnotations(...), structured_output=True)`, `@mcp.resource("kb://doc/{id}")`, `@mcp.prompt()`; `ToolAnnotations` fields = `title, readOnlyHint, destructiveHint, idempotentHint, openWorldHint`; `Tool` carries `outputSchema`. LLM provider is Gemini (`gemini-flash-lite-latest`) via the neutral `app/llm/base.py` layer. No test framework (deliberate repo convention).

---

## Global Constraints

- **Prerequisite — spec 01 moves must exist first.** Verified on 2026-07-23: the Phase A restructure has **NOT** been applied yet — the repo still has `app/agents/tools.py`, `app/mcp_server.py`, `app/mcp_client.py`, `app/skills.py`, and `app/skills/policy-reply-formatter/`; there is **no** `app/tools/`, `app/mcp/`, `app/skills/loader.py`, or `app/skills/definitions/`. This plan references **post-move paths** as instructed. **Task 0** lands exactly the spec-01 moves the Phase C files depend on (steps 4/5/6) so the plan is self-contained and runnable; if Phase A has since been completed, Task 0 degrades to a verification no-op. Do Task 0 first — every later task assumes the post-move tree.
- **The contract is declared ONCE.** Input/output Pydantic models, the flat input JSON schemas (`TOOL_SPECS`), and the `ANNOTATIONS` table live only in `app/tools/registry.py`. `app/mcp/server.py` and the orchestrator **import** them. A `grep` for a re-declared annotation or a second `hybrid_search` projection body must come back empty (spec 03 + 05 acceptance).
- **Input schemas are hand-authored flat dicts** (matching the existing 4 tools) so they stay Gemini function-calling-safe (no `$defs`/`anyOf`/`null` unions that trip the provider). Strictness (`additionalProperties:false`, `enum`s, `required`) is expressed in those flat dicts; runtime validation uses the Pydantic input models (`extra="forbid"`). **Output** models are Pydantic (typed dispatch + FastMCP `outputSchema`).
- **`escalate` writes nothing.** The tool returns a `proposed`, `committed:false` handle. The ONLY code path that writes to the DB is the approval endpoint. "Without approval, no write occurs" must be literally true (spec 05 acceptance) — verify by calling the tool and confirming `escalations` stays empty.
- **`check_refund_eligibility` must actually run the bundled script** (`refund-policy/scripts/refund_eligibility.py`) via `run_skill_script` — not re-implement the policy inline (spec 04/05 tie).
- **Do not regress existing behavior:** `/agent/triage`, `/agent/triage/stream`, `/agent/answer`, `/agent/answer-mcp`, `/search`, `/ingest`, ticket history, observability spans, and the eval `search_mode` regression path (lexical/semantic/hybrid) must all keep working. `rag/search.py`'s `hybrid_search(query, k)` positional call sites (orchestrator, `/search`) must be preserved — new behavior is added behind a keyword-only flag.
- **No test framework exists in this repo** (documented, pre-existing convention). Verification is manual per task: `docker compose up -d --build`, `docker compose logs`, `curl` against `:8000` and the MCP endpoint at `:9000/mcp`, and a Python one-liner run inside a container for MCP client assertions. Each task ends with a concrete command + expected output, then a commit.
- **Run/verify commands:** backend at `http://localhost:8000`, MCP server at `http://localhost:9000/mcp`, frontend at `http://localhost:5173`. `docker compose up -d --build` to (re)build; `docker compose logs backend` / `docker compose logs mcp` to read logs; `docker compose exec backend python -c "..."` to run in-container probes.

---

## File Structure

**New files**
- `backend/app/tools/__init__.py` — package marker (Task 0).
- `backend/app/tools/registry.py` — the reworked typed/annotated/gated registry (moved from `agents/tools.py`, then rewritten Tasks 3/6). **The contract.**
- `backend/app/tools/fixtures.py` — mock Stripe-like `CUSTOMERS` + `PAYMENTS` store (Task 2).
- `backend/app/mcp/__init__.py` — package marker (Task 0).
- `backend/app/mcp/server.py` — reworked MCP server, all 3 primitives (moved from `mcp_server.py`, rewritten Task 4).
- `backend/app/mcp/client.py` — MCP client + `hybrid_search_via_mcp` + capability probe (moved from `mcp_client.py`, extended Task 8).
- `backend/app/skills/loader.py` — real YAML frontmatter, 3-level disclosure, `load_skill`/`run_skill_script` (moved from `skills.py`, rewritten Task 5).
- `backend/app/skills/definitions/policy-reply-formatter/SKILL.md` — moved (Task 0).
- `backend/app/skills/definitions/refund-policy/SKILL.md` + `scripts/refund_eligibility.py` + `references/refund-policy.md` (Task 5).
- `backend/app/skills/definitions/dispute-response/SKILL.md` + `references/dispute-playbook.md` (Task 5).
- `backend/app/api_escalations.py` — approve / reject / list endpoints (Task 7).

**Modified files**
- `backend/app/rag/search.py` — add keyword-only `detailed=False` to `hybrid_search` (Task 1).
- `backend/app/agents/loop.py` — import `TOOL_SPECS`/`dispatch` from `app.tools.registry` (Task 0).
- `backend/app/agents/orchestrator.py` — import `load_skill`/`run_skill_script` from `app.skills.loader` (Task 0); model-driven skill selection + level-3 script run (Task 6); retrieve via MCP client w/ fallback (Task 8).
- `backend/app/api_agent.py` — import MCP client from `app.mcp.client`; mount escalations router note (Task 0 / Task 7).
- `backend/app/main.py` — `app.include_router(escalations_router)` (Task 7).
- `backend/app/schema.sql` — `escalations` table + `tickets` `status`/`assignee` columns (Task 7).
- `docker-compose.yml` — `mcp` service command `python -m app.mcp.server` (Task 0).
- `backend/pyproject.toml` — add `pyyaml` dependency (Task 5).

---

## Shared Contract — Interfaces (declared once in `app/tools/registry.py`)

These are the exact symbols every consumer imports. They must match byte-for-byte across the registry, the MCP server, and the orchestrator.

**Output models (Pydantic → MCP `outputSchema` + typed dispatch):**
`HitScores`, `SearchHit`, `HybridSearchResult`, `DocumentResult`, `TicketResult`, `CustomerResult`, `PaymentStatusResult`, `RefundEligibilityResult`, `EscalateResult`, `SkillBody`, `SkillScriptResult`.

**Input models (validation, `extra="forbid"`):**
`HybridSearchInput`, `GetDocumentInput`, `GetTicketInput`, `LookupCustomerInput`, `GetPaymentStatusInput`, `CheckRefundEligibilityInput`, `LoadSkillInput`, `RunSkillScriptInput`, `EscalateInput`.

**Tool coroutines (called directly by the MCP server wrappers AND by `dispatch`):**
```
async def hybrid_search(*, query, k=5, source_type=None) -> HybridSearchResult
async def get_document(*, document_id) -> DocumentResult
async def get_ticket(*, ticket_id) -> TicketResult
async def lookup_customer(*, customer_id=None, email=None) -> CustomerResult
async def get_payment_status(*, payment_id) -> PaymentStatusResult
async def check_refund_eligibility(*, payment_id) -> RefundEligibilityResult
async def load_skill_tool(*, name) -> SkillBody
async def run_skill_script_tool(*, name, script, args=None) -> SkillScriptResult
async def escalate(*, ticket_ref=None, reason, severity="medium") -> EscalateResult
```

**Registry exports consumed elsewhere:**
- `TOOL_SPECS: list[ToolSpec]` — flat, strict, Gemini-safe input schemas → consumed by `agents/loop.py` (in-process path).
- `dispatch(name: str, args: dict) -> str` — validates via input models, runs the coroutine, returns `model.model_dump_json()`; never raises → consumed by `agents/loop.py`.
- `ANNOTATIONS: dict[str, dict]` — tool name → MCP annotation kwargs → consumed by `app/mcp/server.py`.
- `hit_from_row(row: dict) -> SearchHit` — the single row→hit projection (kills the duplicate `_hybrid_search` body).

**MCP client symbols consumed by the orchestrator (Task 8):**
- `mcp_search_or_local(search_mode: str)` — asynccontextmanager yielding `(search_fn, transport)` where `search_fn(subquestion, k) -> list[dict]` and `transport ∈ {"mcp","in-process"}`.

---

## Task 0: Land the spec-01 moves the Phase C files depend on

Bring the tree to the post-move shape all later tasks assume. Pure `git mv` + import fixups + one docker-compose line — **no behavior change**. If Phase A already ran, each move is already done; verify and skip.

**Files:**
- Move: `agents/tools.py`→`tools/registry.py`; `mcp_server.py`→`mcp/server.py`; `mcp_client.py`→`mcp/client.py`; `skills.py`→`skills/loader.py`; `skills/policy-reply-formatter/`→`skills/definitions/policy-reply-formatter/`.
- Add: `tools/__init__.py`, `mcp/__init__.py`.
- Modify: `agents/loop.py`, `agents/orchestrator.py`, `api_agent.py`, `mcp/server.py` (import path only), `skills/loader.py` (`_SKILLS_DIR`), `docker-compose.yml`.

**Interfaces:** No contract change yet — this task only relocates symbols. `TOOL_SPECS`, `dispatch`, `run_agent`, `list_tool_specs`, `make_dispatch`, `mcp_session`, `list_skills`, `load_skill` keep their names; only their import paths change.

- [ ] **Step 1: Move the files with git (preserves history)**

```bash
cd /home/lucas/PROJETOS/multi-agent-poc/backend/app
mkdir -p tools mcp skills/definitions
touch tools/__init__.py mcp/__init__.py
git mv agents/tools.py    tools/registry.py
git mv mcp_server.py      mcp/server.py
git mv mcp_client.py      mcp/client.py
git mv skills.py          skills/loader.py
git mv skills/policy-reply-formatter skills/definitions/policy-reply-formatter
```

- [ ] **Step 2: Fix `_SKILLS_DIR` in `skills/loader.py`**

The loader moved one level deeper AND the skills moved into `definitions/`. Change:
```python
_SKILLS_DIR = Path(__file__).parent / "skills"
```
to:
```python
# loader.py now lives in app/skills/, and skill packages live in app/skills/definitions/<name>/
_SKILLS_DIR = Path(__file__).parent / "definitions"
```

- [ ] **Step 3: Fix the self-import in `mcp/server.py`**

`mcp/server.py` imports `_get_document` from the old tools module. Change:
```python
from app.agents.tools import _get_document
from app.rag.search import hybrid_search as _hybrid
```
to:
```python
from app.tools import registry
from app.rag.search import hybrid_search as _hybrid
```
and update its two tool bodies to call `registry._get_document`-equivalent — but this file is fully rewritten in Task 4, so the minimal change here is only to make it import successfully. Simplest: temporarily inline the two existing bodies to not depend on the moved private symbol:
```python
@mcp.tool()
async def get_document(document_id: int) -> dict:
    """Fetch the full text of a knowledge-base document by its numeric id."""
    from app.db import get_pool
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, source_type, title, url, content FROM documents WHERE id = $1", int(document_id)
    )
    if not row:
        return {"error": f"document {document_id} not found"}
    return {"id": row["id"], "title": row["title"], "source_type": row["source_type"],
            "content": row["content"][:4000]}
```
(This whole file is replaced in Task 4; this keeps the intermediate commit runnable.)

- [ ] **Step 4: Fix imports in the consumers**

`agents/loop.py` line 7:
```python
from app.agents.tools import TOOL_SPECS, dispatch
```
→
```python
from app.tools.registry import TOOL_SPECS, dispatch
```

`agents/orchestrator.py` line 25:
```python
from app.skills import load_skill
```
→
```python
from app.skills.loader import load_skill
```

`api_agent.py` line 12:
```python
from app.mcp_client import list_tool_specs, make_dispatch, mcp_session
```
→
```python
from app.mcp.client import list_tool_specs, make_dispatch, mcp_session
```

- [ ] **Step 5: Update the docker-compose `mcp` service command**

In `docker-compose.yml`, the `mcp` service:
```yaml
    command: ["python", "-m", "app.mcp_server"]
```
→
```yaml
    command: ["python", "-m", "app.mcp.server"]
```

- [ ] **Step 6: Rebuild and verify nothing broke**

```bash
cd /home/lucas/PROJETOS/multi-agent-poc
docker compose up -d --build
sleep 8
docker compose logs backend --tail 20
docker compose logs mcp --tail 20
curl -s localhost:8000/health
curl -s -X POST localhost:8000/agent/answer-mcp -H 'content-type: application/json' \
  -d '{"message":"why was I charged twice?"}' | head -c 300
```
Expected: `backend` and `mcp` both boot with no `ImportError`/`ModuleNotFoundError`; `/health` returns `{"status":"ok"...}`; `/agent/answer-mcp` returns a JSON object with `"tools_source":"mcp"` and `"mcp_tools":["hybrid_search","get_document"]` (still the OLD 2-tool server — correct at this checkpoint).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor(structure): land spec-01 moves for the MCP/Skills/Tools rework

git mv agents/tools.py->tools/registry.py, mcp_server.py->mcp/server.py,
mcp_client.py->mcp/client.py, skills.py->skills/loader.py, and the skill
package into skills/definitions/. Fixes _SKILLS_DIR, consumer imports, and
the mcp service command. Behavior unchanged; the reworks land in place next.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 1: Per-source scores in `hybrid_search` (RAG foundation for typed hits)

Spec 05 requires typed hits carrying per-source **lexical / semantic / fused** scores. Add this as a keyword-only, default-off flag so the existing positional call sites are untouched and there is still exactly one RRF implementation.

**Files:** Modify `backend/app/rag/search.py`.

**Interfaces:**
- Produces: `hybrid_search(query, k=10, rrf_k=60, pool_n=20, *, detailed=False) -> list[dict]`. When `detailed=True`, each row additionally carries `lexical_score: float | None` and `semantic_score: float | None` alongside the existing fused `score`.
- Consumed by: `app/tools/registry.py::hybrid_search` (Task 3, always passes `detailed=True`).

- [ ] **Step 1: Replace `hybrid_search` in `backend/app/rag/search.py`**

Replace the function (lines 54-70) with:
```python
async def hybrid_search(query: str, k: int = 10, rrf_k: int = 60, pool_n: int = 20,
                        *, detailed: bool = False) -> list[dict]:
    # Run both retrievals concurrently — a first taste of the parallelism theme.
    lex, sem = await asyncio.gather(
        lexical_search(query, pool_n),
        semantic_search(query, pool_n),
    )

    scores: dict[int, float] = {}
    meta: dict[int, dict] = {}
    lex_score: dict[int, float] = {}
    sem_score: dict[int, float] = {}
    for source, ranked in (("lexical", lex), ("semantic", sem)):
        for rank, row in enumerate(ranked):
            cid = row["id"]
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (rrf_k + rank + 1)
            meta[cid] = row
            (lex_score if source == "lexical" else sem_score)[cid] = row["score"]

    top = sorted(scores, key=lambda cid: scores[cid], reverse=True)[:k]
    out: list[dict] = []
    for cid in top:
        row = {**meta[cid], "score": round(scores[cid], 6)}
        if detailed:
            # Component contributions per source (None if that source didn't surface this chunk).
            row["lexical_score"] = round(lex_score[cid], 6) if cid in lex_score else None
            row["semantic_score"] = round(sem_score[cid], 6) if cid in sem_score else None
        out.append(row)
    return out
```

- [ ] **Step 2: Verify (in-container probe)**

```bash
docker compose up -d --build backend
docker compose exec backend python -c "
import asyncio, json
from app.rag.search import hybrid_search
async def m():
    rows = await hybrid_search('duplicate charge refund', k=3, detailed=True)
    print(json.dumps([{k: r.get(k) for k in ('id','source_type','score','lexical_score','semantic_score')} for r in rows], indent=2))
asyncio.run(m())
"
```
Expected: 3 rows, each with a `score` and at least one of `lexical_score`/`semantic_score` populated (the other may be `null` when only one retriever surfaced the chunk). `/search` still works unchanged: `curl -s 'localhost:8000/search?q=refund&k=3'` returns rows without the new fields.

- [ ] **Step 3: Commit**

```bash
git add backend/app/rag/search.py
git commit -m "feat(rag): optional per-source scores on hybrid_search (detailed=True)

Keyword-only flag exposes each hit's lexical/semantic component scores next
to the fused RRF score, for spec-05 typed SearchHit output. Default off so
the orchestrator and /search positional call sites are unchanged; still one
RRF implementation.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Mock Stripe-like fixtures (`lookup_customer` / `get_payment_status` data)

Spec 05 adds NEW read tools over seeded fixtures — "real function-calling against a system". A dedicated in-memory fixture store (a mock Stripe API) is cleaner than forcing customers/payments into the `documents` table and needs no schema churn. Keys align with the seeded `PAST_TICKETS` so a triaged ticket can be tied to a plausible customer/payment.

**Files:** New `backend/app/tools/fixtures.py`.

**Interfaces:**
- Produces: `CUSTOMERS: dict[str, dict]` (keyed by `cust_id`), `EMAIL_INDEX: dict[str, str]` (email→cust_id), `PAYMENTS: dict[str, dict]` (keyed by `payment_id`).
- Consumed by: `registry.lookup_customer`, `registry.get_payment_status`, `registry.check_refund_eligibility` (Task 3/6).

- [ ] **Step 1: Create `backend/app/tools/fixtures.py`**

```python
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
```

- [ ] **Step 2: Verify import**

```bash
docker compose exec backend python -c "
from app.tools.fixtures import CUSTOMERS, PAYMENTS, EMAIL_INDEX
print('customers', len(CUSTOMERS), 'payments', len(PAYMENTS))
print('alice ->', EMAIL_INDEX['alice@example.com'])
print('pay_1004 age', PAYMENTS['pay_1004']['age_days'])
"
```
Expected: `customers 4 payments 5`, `alice -> cust_alice`, `pay_1004 age 144`.

- [ ] **Step 3: Commit**

```bash
git add backend/app/tools/fixtures.py
git commit -m "feat(tools): mock Stripe-like customer/payment fixtures

In-process deterministic fixture store backing the new lookup_customer /
get_payment_status / check_refund_eligibility read tools. Keys align with
seeded PAST_TICKETS so precedent tickets map to plausible payments; carries
exactly the fields the refund-policy script reasons over.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: The typed, annotated registry — the contract (spec 05 core)

Rewrite `app/tools/registry.py`: Pydantic input+output models, the flat `TOOL_SPECS` (strict, Gemini-safe), the `ANNOTATIONS` table declared once, the shared `hit_from_row` projection, the read tools, the pure `escalate` proposal, and a validating `dispatch`. `check_refund_eligibility`, `load_skill_tool`, `run_skill_script_tool` are stubbed here and completed in Task 6 (after skills exist), but their specs/annotations/coroutine signatures are declared now so the contract is stable.

**Files:** Rewrite `backend/app/tools/registry.py`.

**Interfaces:** Produces the full Shared Contract above. Consumes `app.rag.search.hybrid_search(detailed=True)`, `app.tools.fixtures`, `app.db.get_pool`, `app.llm.base.ToolSpec`.

- [ ] **Step 1: Write `backend/app/tools/registry.py`**

```python
"""Typed, annotated, gated tool registry (topic: "tools") — THE contract.

A tool = a JSON-schema-described function the model may call. The model never
runs code; it emits a tool call, WE execute the Python here and feed a typed
result back. This module is the single source of truth: the MCP server
(app/mcp/server.py) imports these coroutines, output models, and ANNOTATIONS —
it re-declares nothing.

Design:
- INPUT schemas are authored as flat dicts (TOOL_SPECS) so they stay compatible
  with Gemini function-calling (no $defs/anyOf/null unions). Strictness lives
  here: additionalProperties:false, enums, required.
- Runtime input validation uses the Pydantic *Input models (extra="forbid").
- OUTPUT is typed Pydantic (-> FastMCP outputSchema + typed dispatch), never a
  json.dumps blob.
- ANNOTATIONS (readOnlyHint/destructiveHint/idempotentHint) are declared ONCE.
"""
from __future__ import annotations

import json
import uuid

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.db import get_pool
from app.llm.base import ToolSpec
from app.rag.search import hybrid_search as _rag_hybrid
from app.tools import fixtures

# --------------------------------------------------------------------------- #
# Output models  (typed structured output -> MCP outputSchema)
# --------------------------------------------------------------------------- #
class HitScores(BaseModel):
    lexical: float | None = None
    semantic: float | None = None
    fused: float


class SearchHit(BaseModel):
    chunk_id: int
    document_id: int
    source_type: str
    title: str | None = None
    preview: str
    scores: HitScores


class HybridSearchResult(BaseModel):
    query: str
    k: int
    source_type: str | None = None
    hits: list[SearchHit]


class DocumentResult(BaseModel):
    found: bool
    id: int | None = None
    title: str | None = None
    source_type: str | None = None
    url: str | None = None
    content: str = ""


class TicketResult(BaseModel):
    found: bool
    ticket_id: str
    subject: str | None = None
    content: str = ""
    metadata: dict = Field(default_factory=dict)


class CustomerResult(BaseModel):
    found: bool
    customer_id: str = ""
    email: str = ""
    name: str = ""
    created: str = ""
    lifetime_value_usd: float = 0.0
    subscription_status: str = ""
    payment_ids: list[str] = Field(default_factory=list)


class PaymentStatusResult(BaseModel):
    found: bool
    payment_id: str = ""
    customer_id: str = ""
    amount_usd: float = 0.0
    currency: str = ""
    status: str = ""            # succeeded | pending | failed | refunded | disputed
    created: str = ""
    age_days: int = 0
    is_subscription: bool = False
    refunded: bool = False
    dispute_open: bool = False


class RefundEligibilityResult(BaseModel):
    found: bool
    payment_id: str | None = None
    eligible: bool = False
    reason: str = ""
    method: str = "none"        # card_refund | manual_bank_transfer | none
    policy_window_days: int = 90
    skill: str = "refund-policy"
    script: str = "refund_eligibility.py"


class EscalateResult(BaseModel):
    handle: str
    status: str                 # 'proposed' (never committed by the tool)
    committed: bool
    ticket_ref: str | None = None
    reason: str
    severity: str


class SkillBody(BaseModel):
    found: bool
    name: str
    body: str = ""


class SkillScriptResult(BaseModel):
    ok: bool
    name: str
    script: str
    output: dict = Field(default_factory=dict)
    error: str | None = None


# --------------------------------------------------------------------------- #
# Input models  (validation only; schemas for the model are the flat dicts below)
# --------------------------------------------------------------------------- #
class HybridSearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1)
    k: int = Field(5, ge=1, le=25)
    source_type: str | None = Field(None, pattern="^(kb|ticket)$")


class GetDocumentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: int


class GetTicketInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticket_id: str = Field(min_length=1)


class LookupCustomerInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    customer_id: str | None = None
    email: str | None = None


class GetPaymentStatusInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    payment_id: str = Field(min_length=1)


class CheckRefundEligibilityInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    payment_id: str = Field(min_length=1)


class LoadSkillInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1)


class RunSkillScriptInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1)
    script: str = Field(min_length=1)
    args: dict = Field(default_factory=dict)


class EscalateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticket_ref: str | None = None
    reason: str = Field(min_length=1)
    severity: str = Field("medium", pattern="^(low|medium|high)$")


# --------------------------------------------------------------------------- #
# Annotations (single source of truth; imported by the MCP server)
# --------------------------------------------------------------------------- #
_READ = {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False}
ANNOTATIONS: dict[str, dict] = {
    "hybrid_search": {**_READ, "title": "Search KB + past tickets"},
    "get_document": {**_READ, "title": "Get KB document"},
    "get_ticket": {**_READ, "title": "Get past ticket"},
    "lookup_customer": {**_READ, "title": "Look up customer"},
    "get_payment_status": {**_READ, "title": "Get payment status"},
    "check_refund_eligibility": {**_READ, "title": "Check refund eligibility (skill script)"},
    "load_skill": {**_READ, "title": "Load a skill body"},
    "run_skill_script": {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False,
                         "title": "Run a bundled skill script"},
    "escalate": {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False,
                 "openWorldHint": True, "title": "Propose escalation to a human (gated)"},
}


# --------------------------------------------------------------------------- #
# Shared projection (the ONLY row->hit body; kills the duplicate _hybrid_search)
# --------------------------------------------------------------------------- #
def hit_from_row(row: dict) -> SearchHit:
    return SearchHit(
        chunk_id=row["id"],
        document_id=row["document_id"],
        source_type=row["source_type"],
        title=row.get("title"),
        preview=row["content"][:300],
        scores=HitScores(
            lexical=row.get("lexical_score"),
            semantic=row.get("semantic_score"),
            fused=row["score"],
        ),
    )


# --------------------------------------------------------------------------- #
# Tool coroutines (called directly by the MCP server AND by dispatch)
# --------------------------------------------------------------------------- #
async def hybrid_search(*, query: str, k: int = 5, source_type: str | None = None) -> HybridSearchResult:
    # Over-fetch when filtering so the post-filter can still return up to k hits.
    fetch_k = k * 3 if source_type else k
    rows = await _rag_hybrid(query, fetch_k, detailed=True)
    if source_type:
        rows = [r for r in rows if r["source_type"] == source_type]
    rows = rows[:k]
    return HybridSearchResult(query=query, k=k, source_type=source_type,
                              hits=[hit_from_row(r) for r in rows])


async def get_document(*, document_id: int) -> DocumentResult:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, source_type, title, url, content FROM documents WHERE id = $1", int(document_id)
    )
    if not row:
        return DocumentResult(found=False, id=document_id)
    return DocumentResult(found=True, id=row["id"], title=row["title"],
                          source_type=row["source_type"], url=row["url"],
                          content=row["content"][:4000])


async def get_ticket(*, ticket_id: str) -> TicketResult:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT external_id, title, content, metadata FROM documents "
        "WHERE source_type = 'ticket' AND external_id = $1", str(ticket_id)
    )
    if not row:
        return TicketResult(found=False, ticket_id=ticket_id)
    meta = row["metadata"]
    return TicketResult(found=True, ticket_id=row["external_id"], subject=row["title"],
                        content=row["content"],
                        metadata=json.loads(meta) if isinstance(meta, str) else (meta or {}))


async def lookup_customer(*, customer_id: str | None = None, email: str | None = None) -> CustomerResult:
    cid = customer_id
    if cid is None and email:
        cid = fixtures.EMAIL_INDEX.get(email.lower())
    c = fixtures.CUSTOMERS.get(cid) if cid else None
    if not c:
        return CustomerResult(found=False)
    return CustomerResult(found=True, **c)


async def get_payment_status(*, payment_id: str) -> PaymentStatusResult:
    p = fixtures.PAYMENTS.get(payment_id)
    if not p:
        return PaymentStatusResult(found=False, payment_id=payment_id)
    return PaymentStatusResult(found=True, **p)


async def check_refund_eligibility(*, payment_id: str) -> RefundEligibilityResult:
    # Completed in Task 6 once run_skill_script + the refund-policy script exist.
    raise NotImplementedError("wired in Task 6")


async def load_skill_tool(*, name: str) -> SkillBody:
    raise NotImplementedError("wired in Task 6")


async def run_skill_script_tool(*, name: str, script: str, args: dict | None = None) -> SkillScriptResult:
    raise NotImplementedError("wired in Task 6")


async def escalate(*, ticket_ref: str | None = None, reason: str,
                   severity: str = "medium") -> EscalateResult:
    """PROPOSE an escalation. Writes NOTHING — the gate. The write commits only
    when a human approves via POST /agent/escalations (see api_escalations.py)."""
    handle = "ESC-" + uuid.uuid4().hex[:8]
    return EscalateResult(handle=handle, status="proposed", committed=False,
                          ticket_ref=ticket_ref, reason=reason, severity=severity)


# --------------------------------------------------------------------------- #
# Flat, strict, Gemini-safe input schemas + dispatch
# --------------------------------------------------------------------------- #
def _obj(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "additionalProperties": False,
            "properties": properties, "required": required}


TOOL_SPECS: list[ToolSpec] = [
    ToolSpec(
        name="hybrid_search",
        description="Search the knowledge base and past resolved tickets for relevant passages. "
                    "Use this before answering any factual or policy question. "
                    "Optionally filter to a single source_type.",
        parameters=_obj({
            "query": {"type": "string", "description": "What to search for"},
            "k": {"type": "integer", "description": "Number of results (1-25, default 5)"},
            "source_type": {"type": "string", "enum": ["kb", "ticket"],
                            "description": "Restrict to KB articles or past tickets"},
        }, ["query"]),
    ),
    ToolSpec(
        name="get_document",
        description="Fetch the full text of a knowledge-base document by its numeric id.",
        parameters=_obj({"document_id": {"type": "integer"}}, ["document_id"]),
    ),
    ToolSpec(
        name="get_ticket",
        description="Fetch a past resolved ticket and its resolution by ticket id (e.g. 'TKT-1001').",
        parameters=_obj({"ticket_id": {"type": "string"}}, ["ticket_id"]),
    ),
    ToolSpec(
        name="lookup_customer",
        description="Look up a customer by customer_id or email in the payments system.",
        parameters=_obj({
            "customer_id": {"type": "string"},
            "email": {"type": "string"},
        }, []),
    ),
    ToolSpec(
        name="get_payment_status",
        description="Get the status and metadata of a payment by payment_id (e.g. 'pay_1001').",
        parameters=_obj({"payment_id": {"type": "string"}}, ["payment_id"]),
    ),
    ToolSpec(
        name="check_refund_eligibility",
        description="Deterministically decide whether a payment can be refunded, and how, by running "
                    "the refund-policy skill's script over the payment's metadata.",
        parameters=_obj({"payment_id": {"type": "string"}}, ["payment_id"]),
    ),
    ToolSpec(
        name="load_skill",
        description="Load the full body (level 2) of a skill by name for its house rules/instructions.",
        parameters=_obj({"name": {"type": "string"}}, ["name"]),
    ),
    ToolSpec(
        name="run_skill_script",
        description="Run a bundled executable script (level 3) shipped with a skill, passing JSON args.",
        parameters=_obj({
            "name": {"type": "string"},
            "script": {"type": "string"},
            "args": {"type": "object"},
        }, ["name", "script"]),
    ),
    ToolSpec(
        name="escalate",
        description="Propose escalating this ticket to a human agent when it cannot be resolved from "
                    "available information. This does NOT act on its own — it returns a proposal that a "
                    "human must approve.",
        parameters=_obj({
            "ticket_ref": {"type": "string"},
            "reason": {"type": "string"},
            "severity": {"type": "string", "enum": ["low", "medium", "high"]},
        }, ["reason"]),
    ),
]

_INPUT_MODELS: dict[str, type[BaseModel]] = {
    "hybrid_search": HybridSearchInput,
    "get_document": GetDocumentInput,
    "get_ticket": GetTicketInput,
    "lookup_customer": LookupCustomerInput,
    "get_payment_status": GetPaymentStatusInput,
    "check_refund_eligibility": CheckRefundEligibilityInput,
    "load_skill": LoadSkillInput,
    "run_skill_script": RunSkillScriptInput,
    "escalate": EscalateInput,
}

_DISPATCH = {
    "hybrid_search": hybrid_search,
    "get_document": get_document,
    "get_ticket": get_ticket,
    "lookup_customer": lookup_customer,
    "get_payment_status": get_payment_status,
    "check_refund_eligibility": check_refund_eligibility,
    "load_skill": load_skill_tool,
    "run_skill_script": run_skill_script_tool,
    "escalate": escalate,
}


async def dispatch(name: str, args: dict) -> str:
    """Validate args, run the tool, return a JSON string of the typed result.
    Never raises — a bad call degrades to an {"error": ...} tool_result the loop
    can recover from (is_error semantics)."""
    fn = _DISPATCH.get(name)
    model = _INPUT_MODELS.get(name)
    if fn is None:
        return json.dumps({"error": f"unknown tool {name}"})
    try:
        validated = model(**(args or {})) if model else None
        result = await fn(**(validated.model_dump() if validated else {}))
    except ValidationError as exc:
        return json.dumps({"error": "invalid arguments", "detail": exc.errors()}, default=str)
    except Exception as exc:  # noqa: BLE001 - fed back to the model as an error tool_result
        return json.dumps({"error": repr(exc)})
    return result.model_dump_json() if isinstance(result, BaseModel) else json.dumps(result, default=str)
```

- [ ] **Step 2: Verify the read tools + gated escalate through the loop**

```bash
docker compose up -d --build backend
# Read tools return typed data through the single-agent loop:
docker compose exec backend python -c "
import asyncio, json
from app.tools import registry as r
async def m():
    print('lookup', (await r.lookup_customer(email='alice@example.com')).model_dump())
    print('payment', (await r.get_payment_status(payment_id='pay_1004')).model_dump())
    print('search', (await r.hybrid_search(query='refund timeline', k=2)).model_dump())
    print('escalate', (await r.escalate(reason='cannot verify charge', severity='high')).model_dump())
asyncio.run(m())
"
# Strict schema: an unknown arg is rejected by dispatch (not silently ignored):
docker compose exec backend python -c "
import asyncio
from app.tools.registry import dispatch
print(asyncio.run(dispatch('get_payment_status', {'payment_id':'pay_1001','bogus':1})))
"
```
Expected: `lookup` shows Alice with `found:true`; `payment` shows `pay_1004` `age_days:144`; `search` returns `hits` each with a `scores` object; `escalate` returns `status:"proposed", committed:false` and an `ESC-...` handle. The bad-arg call returns `{"error":"invalid arguments", ...}` (proving `additionalProperties:false` is enforced at runtime).

- [ ] **Step 3: Commit**

```bash
git add backend/app/tools/registry.py
git commit -m "feat(tools): typed, annotated, gated registry — the shared contract

Pydantic input(validation)/output(typed structured results) models, flat
Gemini-safe strict input schemas (additionalProperties:false + enums), a
single ANNOTATIONS table, one shared hit_from_row projection, new mock reads
(lookup_customer/get_payment_status), and a pure escalate proposal that writes
nothing. check_refund_eligibility/load_skill/run_skill_script are declared and
completed in the skills task. dispatch validates and returns typed JSON.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: MCP server — all three primitives, importing the registry (spec 03)

Rewrite `app/mcp/server.py` to expose the FULL tool set (annotations + `outputSchema` imported from the registry, never re-declared), plus **resources** and **prompts**. FastMCP 1.28.1 confirmed: `@mcp.tool(annotations=ToolAnnotations(**...), structured_output=True)` with a Pydantic return type emits `outputSchema`; `@mcp.resource("kb://doc/{id}")` supports URI templates; `@mcp.prompt()` registers prompts.

**Files:** Rewrite `backend/app/mcp/server.py`.

**Interfaces:**
- Consumes from `app.tools.registry`: the tool coroutines, output models (`HybridSearchResult`, `DocumentResult`, `TicketResult`, `CustomerResult`, `PaymentStatusResult`, `RefundEligibilityResult`, `EscalateResult`, `SkillBody`, `SkillScriptResult`), and `ANNOTATIONS`.
- Consumes from `app.skills.loader`: `list_skills`, `skill_markdown` (Task 5 adds `skill_markdown`; guard with a fallback so this task's intermediate build works — see Step 1 note).
- Consumes `app.db.get_pool` for resource reads.

- [ ] **Step 1: Write `backend/app/mcp/server.py`**

```python
"""Standalone MCP server (topic: "MCP") — all three primitives.

Exposes the reworked tool registry over the Model Context Protocol (Streamable
HTTP) so ANY MCP-aware client — our own backend, Claude Desktop, an MCP
inspector — can discover and call them. Adds the two primitives most POCs skip:
RESOURCES (URI-addressed context data) and PROMPTS (user-controlled templates ->
slash commands).

Single source of truth: tool coroutines, typed output models, and annotations
are IMPORTED from app/tools/registry.py — this file declares none of them, so
the "write once, reuse anywhere" claim is literally true.

Run as its own container: `python -m app.mcp.server` (docker-compose `mcp`).

Why the backend talks to this over a LOCAL MCP client instead of the Anthropic
API's `mcp_servers` connector: this server lives on the private docker network
with no public URL, and the connector requires a publicly reachable endpoint.
The local-client path is therefore the correct integration here (kept from the
original design).
"""
import json

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from app.db import get_pool
from app.skills.loader import list_skills, skill_markdown
from app.tools import registry as r

mcp = FastMCP("support-kb", host="0.0.0.0", port=9000)


def _ann(name: str) -> ToolAnnotations:
    """Wrap the registry's single-source annotation dict in the MCP type."""
    return ToolAnnotations(**r.ANNOTATIONS[name])


# --------------------------------------------------------------------------- #
# Primitive 1 — Tools (thin wrappers; behavior + annotations come from registry)
# --------------------------------------------------------------------------- #
@mcp.tool(annotations=_ann("hybrid_search"), structured_output=True)
async def hybrid_search(query: str, k: int = 5,
                        source_type: str | None = None) -> r.HybridSearchResult:
    """Search the knowledge base and past resolved tickets for relevant passages."""
    return await r.hybrid_search(query=query, k=k, source_type=source_type)


@mcp.tool(annotations=_ann("get_document"), structured_output=True)
async def get_document(document_id: int) -> r.DocumentResult:
    """Fetch the full text of a knowledge-base document by its numeric id."""
    return await r.get_document(document_id=document_id)


@mcp.tool(annotations=_ann("get_ticket"), structured_output=True)
async def get_ticket(ticket_id: str) -> r.TicketResult:
    """Fetch a past resolved ticket and its resolution by ticket id."""
    return await r.get_ticket(ticket_id=ticket_id)


@mcp.tool(annotations=_ann("lookup_customer"), structured_output=True)
async def lookup_customer(customer_id: str | None = None,
                          email: str | None = None) -> r.CustomerResult:
    """Look up a customer by customer_id or email."""
    return await r.lookup_customer(customer_id=customer_id, email=email)


@mcp.tool(annotations=_ann("get_payment_status"), structured_output=True)
async def get_payment_status(payment_id: str) -> r.PaymentStatusResult:
    """Get the status and metadata of a payment by payment_id."""
    return await r.get_payment_status(payment_id=payment_id)


@mcp.tool(annotations=_ann("check_refund_eligibility"), structured_output=True)
async def check_refund_eligibility(payment_id: str) -> r.RefundEligibilityResult:
    """Decide whether a payment can be refunded by running the refund-policy skill script."""
    return await r.check_refund_eligibility(payment_id=payment_id)


@mcp.tool(annotations=_ann("load_skill"), structured_output=True)
async def load_skill(name: str) -> r.SkillBody:
    """Load a skill's full body (level 2)."""
    return await r.load_skill_tool(name=name)


@mcp.tool(annotations=_ann("run_skill_script"), structured_output=True)
async def run_skill_script(name: str, script: str,
                           args: dict | None = None) -> r.SkillScriptResult:
    """Run a bundled skill script (level 3) with JSON args."""
    return await r.run_skill_script_tool(name=name, script=script, args=args)


@mcp.tool(annotations=_ann("escalate"), structured_output=True)
async def escalate(reason: str, ticket_ref: str | None = None,
                   severity: str = "medium") -> r.EscalateResult:
    """Propose escalating to a human (gated — writes nothing; needs approval)."""
    return await r.escalate(ticket_ref=ticket_ref, reason=reason, severity=severity)


# --------------------------------------------------------------------------- #
# Primitive 2 — Resources (application-controlled context data, URI-addressed)
# --------------------------------------------------------------------------- #
@mcp.resource("kb://index", mime_type="application/json")
async def kb_index() -> str:
    """Browsable catalog of KB documents: id, title, source_type."""
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT id, title, source_type, external_id FROM documents ORDER BY source_type, id"
    )
    return json.dumps([
        {"id": r_["id"], "title": r_["title"], "source_type": r_["source_type"],
         "external_id": r_["external_id"]}
        for r_ in rows
    ])


@mcp.resource("kb://doc/{doc_id}", mime_type="text/markdown")
async def kb_doc(doc_id: str) -> str:
    """A single KB document as markdown (metadata header + content)."""
    doc = await r.get_document(document_id=int(doc_id))
    if not doc.found:
        return f"# Not found\n\nNo document with id {doc_id}."
    return (f"# {doc.title}\n\n"
            f"_source_type: {doc.source_type}_  \n"
            f"_url: {doc.url or '(synthetic)'}_\n\n{doc.content}")


@mcp.resource("ticket://{external_id}", mime_type="text/markdown")
async def ticket_resource(external_id: str) -> str:
    """A seeded past ticket (precedent) as markdown."""
    t = await r.get_ticket(ticket_id=external_id)
    if not t.found:
        return f"# Not found\n\nNo ticket {external_id}."
    return f"# {t.subject}\n\n{t.content}\n\n---\nmetadata: {json.dumps(t.metadata)}"


@mcp.resource("skill://{name}", mime_type="text/markdown")
async def skill_resource(name: str) -> str:
    """A skill's SKILL.md (ties MCP <-> spec 04)."""
    md = skill_markdown(name)
    return md if md is not None else f"# Not found\n\nNo skill '{name}'."


# --------------------------------------------------------------------------- #
# Primitive 3 — Prompts (user-controlled templates -> slash commands)
# --------------------------------------------------------------------------- #
@mcp.prompt(title="Triage a refund request")
def triage_refund(ticket: str) -> str:
    """Seed a refund-triage conversation for a customer ticket."""
    return (
        "You are a payments support triage assistant. Triage this refund request:\n\n"
        f"{ticket}\n\n"
        "Steps: (1) hybrid_search the KB + past tickets for the refund policy and precedent; "
        "(2) if a payment id is present, call get_payment_status then check_refund_eligibility; "
        "(3) draft a concise, cited, customer-ready reply. If it cannot be resolved, call escalate."
    )


@mcp.prompt(title="Draft a customer reply")
def draft_reply(ticket: str, findings: str = "") -> str:
    """Draft a customer reply from a ticket + retrieved context."""
    return (
        "Draft a warm, concise, customer-ready reply grounded ONLY in the findings below. "
        "Cite article titles in-line. Never invent policy.\n\n"
        f"Ticket:\n{ticket}\n\nFindings:\n{findings or '(retrieve with hybrid_search first)'}"
    )


@mcp.prompt(title="Summarize a ticket thread")
def summarize_thread(thread: str) -> str:
    """Summarize a ticket thread into a short status + next action."""
    return ("Summarize this support thread in 3 bullets (what happened, current status, next action):\n\n"
            f"{thread}")


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
```

> **Intermediate-build note:** this task depends on `app.skills.loader.skill_markdown` and the three registry coroutines still raising `NotImplementedError` (Task 6). The server will still **start, list, and describe** all tools/resources/prompts — the `NotImplementedError` only fires if those specific tools are *called*, and `skill_markdown` is added in Task 5 which lands before the Task 6 call sites are exercised. If you build this task before Task 5, temporarily `from app.skills.loader import list_skills` and stub `def skill_markdown(name): return None`. Prefer ordering Task 5 immediately after this one.

- [ ] **Step 2: Verify all three primitives over the protocol**

```bash
docker compose up -d --build mcp
sleep 5
docker compose logs mcp --tail 15   # expect capability/negotiation + "streamable-http" listening
# Use the backend container (has the mcp client + our client helpers) to introspect:
docker compose exec backend python -c "
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
async def m():
    async with streamablehttp_client('http://mcp:9000/mcp') as (rd, wr, *_):
        async with ClientSession(rd, wr) as s:
            init = await s.initialize()
            print('server:', init.serverInfo.name, 'proto:', init.protocolVersion)
            tools = await s.list_tools()
            print('tools:', [t.name for t in tools.tools])
            esc = next(t for t in tools.tools if t.name=='escalate')
            print('escalate annotations:', esc.annotations)
            hs = next(t for t in tools.tools if t.name=='hybrid_search')
            print('hybrid_search has outputSchema:', hs.outputSchema is not None)
            res = await s.list_resources()
            tpls = await s.list_resource_templates()
            print('resource templates:', [t.uriTemplate for t in tpls.resourceTemplates])
            prompts = await s.list_prompts()
            print('prompts:', [p.name for p in prompts.prompts])
            doc = await s.read_resource('kb://doc/1')
            print('kb://doc/1 head:', doc.contents[0].text[:60])
asyncio.run(m())
"
```
Expected: server `support-kb`; tools list = all 9 (`hybrid_search, get_document, get_ticket, lookup_customer, get_payment_status, check_refund_eligibility, load_skill, run_skill_script, escalate`); `escalate annotations` shows `destructiveHint=True idempotentHint=False readOnlyHint=False`; `hybrid_search has outputSchema: True`; resource templates include `kb://doc/{doc_id}`, `ticket://{external_id}`, `skill://{name}`; prompts = `triage_refund, draft_reply, summarize_thread`; `kb://doc/1` returns markdown.

- [ ] **Step 3: Commit**

```bash
git add backend/app/mcp/server.py
git commit -m "feat(mcp): all three primitives, importing the registry contract

Tools now expose registry annotations + Pydantic outputSchema (imported, never
re-declared). Adds resources (kb://index, kb://doc/{id}, ticket://{id},
skill://{name}) and prompts (triage-refund, draft-reply, summarize-thread).
Keeps the documented local-client-vs-connector rationale.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Skill library — real YAML, 3-level disclosure, bundled script (spec 04)

Rewrite `app/skills/loader.py` and populate `app/skills/definitions/` with ≥3 skills, one of which ships an executable script (level 3).

**Files:**
- Modify: `backend/app/skills/loader.py`, `backend/pyproject.toml`.
- New: `backend/app/skills/definitions/refund-policy/SKILL.md`, `.../refund-policy/scripts/refund_eligibility.py`, `.../refund-policy/references/refund-policy.md`, `.../dispute-response/SKILL.md`, `.../dispute-response/references/dispute-playbook.md`.
- (`policy-reply-formatter/SKILL.md` already moved in Task 0.)

**Interfaces:**
- Produces: `list_skills() -> list[dict]` (name+description+allowed_tools, level 1); `load_skill(name) -> str | None` (level 2 body); `skill_markdown(name) -> str | None` (raw SKILL.md, for `skill://`); `list_scripts(name) -> list[str]` and `run_skill_script(name, script, args) -> dict` (level 3); `skill_meta(name) -> dict | None`.
- Consumed by: `app/mcp/server.py` (`list_skills`, `skill_markdown`), `app/tools/registry.py` (Task 6: `load_skill`/`run_skill_script`), `app/agents/orchestrator.py` (Task 6).

- [ ] **Step 1: Add pyyaml to `backend/pyproject.toml`**

Add `"pyyaml>=6"` to the dependencies array (real frontmatter parsing replaces the `---` string split).

- [ ] **Step 2: Write `backend/app/skills/loader.py`**

```python
"""Skills (topic: "skills") — a real library with 3-level progressive disclosure.

Level 1 (always in context): each skill's name + one-line description + allowed-tools
         (list_skills) — cheap, so the base prompt never carries skill bodies.
Level 2 (on relevance):      the SKILL.md body (load_skill) — loaded when a skill is selected.
Level 3 (on demand):         bundled references/ and executable scripts/ (run_skill_script) —
         loaded/run only when the body calls for them.

Provider-agnostic (works on Gemini now); the native Anthropic Agent Skills API is the
deferred, Claude-only alternative.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import yaml

_SKILLS_DIR = Path(__file__).parent / "definitions"


def _parse(md: str) -> tuple[dict, str]:
    """Split real YAML frontmatter (--- ... ---) from the markdown body."""
    if md.startswith("---"):
        parts = md.split("---", 2)
        if len(parts) == 3:
            meta = yaml.safe_load(parts[1]) or {}
            return (meta if isinstance(meta, dict) else {}), parts[2].strip()
    return {}, md.strip()


def _skill_dir(name: str) -> Path | None:
    """Resolve + containment-check a skill directory under definitions/."""
    path = (_SKILLS_DIR / name).resolve()
    if _SKILLS_DIR.resolve() not in path.parents and path != _SKILLS_DIR.resolve():
        return None
    return path if (path / "SKILL.md").exists() else None


def list_skills() -> list[dict]:
    """Level 1: names + one-line descriptions + allowed-tools (what stays in context)."""
    out = []
    for skill_md in sorted(_SKILLS_DIR.glob("*/SKILL.md")):
        meta, _ = _parse(skill_md.read_text())
        out.append({
            "name": meta.get("name", skill_md.parent.name),
            "description": meta.get("description", ""),
            "allowed_tools": meta.get("allowed-tools", []),
        })
    return out


def skill_meta(name: str) -> dict | None:
    d = _skill_dir(name)
    if d is None:
        return None
    meta, _ = _parse((d / "SKILL.md").read_text())
    return meta


def load_skill(name: str) -> str | None:
    """Level 2: the full SKILL.md body — loaded on demand when a task calls for it."""
    d = _skill_dir(name)
    if d is None:
        return None
    _, body = _parse((d / "SKILL.md").read_text())
    return body


def skill_markdown(name: str) -> str | None:
    """The raw SKILL.md (frontmatter + body) — for the skill:// MCP resource."""
    d = _skill_dir(name)
    return (d / "SKILL.md").read_text() if d else None


def list_scripts(name: str) -> list[str]:
    """Level 3 discovery: executable scripts bundled with a skill."""
    d = _skill_dir(name)
    if d is None or not (d / "scripts").is_dir():
        return []
    return sorted(p.name for p in (d / "scripts").glob("*.py"))


async def run_skill_script(name: str, script: str, args: dict | None = None) -> dict:
    """Level 3 execution: run a bundled script in a subprocess, passing args as JSON
    on argv[1] and parsing JSON from stdout. Returns {"ok": bool, "output"|"error": ...}.

    Containment: the script must resolve inside this skill's scripts/ dir — no traversal."""
    d = _skill_dir(name)
    if d is None:
        return {"ok": False, "error": f"unknown skill {name}"}
    script_path = (d / "scripts" / script).resolve()
    if (d / "scripts").resolve() not in script_path.parents or not script_path.exists():
        return {"ok": False, "error": f"script {script} not found in skill {name}"}

    proc = await asyncio.create_subprocess_exec(
        sys.executable, str(script_path), json.dumps(args or {}),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        return {"ok": False, "error": stderr.decode()[:500] or f"exit {proc.returncode}"}
    try:
        return {"ok": True, "output": json.loads(stdout.decode())}
    except json.JSONDecodeError:
        return {"ok": False, "error": f"non-JSON script output: {stdout.decode()[:300]}"}
```

- [ ] **Step 3: Create `refund-policy` skill with a bundled script**

`backend/app/skills/definitions/refund-policy/SKILL.md`:
```markdown
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
```

`backend/app/skills/definitions/refund-policy/scripts/refund_eligibility.py`:
```python
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
```

`backend/app/skills/definitions/refund-policy/references/refund-policy.md`:
```markdown
# Refund policy reference (level 3)

- Card refunds are possible within 90 days of the original payment; they post in 5-10 business days.
- After 90 days the card can no longer be refunded — arrange a manual bank transfer.
- Money returns only to the original payment method.
- Subscriptions: refundable for the current period only if cancelled within 14 days of renewal.
- Pending authorization holds are NOT charges — never refund them; they drop off within 7 business days.
- If a chargeback/dispute is already open, do not refund (double refund) — respond to the dispute instead.
```

- [ ] **Step 4: Create a third skill, `dispute-response`**

`backend/app/skills/definitions/dispute-response/SKILL.md`:
```markdown
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
```

`backend/app/skills/definitions/dispute-response/references/dispute-playbook.md`:
```markdown
# Dispute playbook (level 3)

Evidence to attach when responding to a dispute: order confirmation, delivery/usage logs,
the customer's prior agreement, and any refund already offered. Tone: factual, non-accusatory.
Never promise the bank's outcome — the issuing bank decides.
```

- [ ] **Step 5: Verify the loader + script end to end**

```bash
docker compose up -d --build backend mcp
docker compose exec backend python -c "
import asyncio, json
from app.skills import loader
print('level1:', json.dumps(loader.list_skills(), indent=2))
print('scripts:', loader.list_scripts('refund-policy'))
async def m():
    # >90 days -> manual transfer
    print(await loader.run_skill_script('refund-policy','refund_eligibility.py',
          {'days_since_payment':144,'status':'succeeded','refunded':False,
           'dispute_open':False,'is_subscription':False,'within_renewal_window':False}))
    # dispute open -> not eligible
    print(await loader.run_skill_script('refund-policy','refund_eligibility.py',
          {'status':'disputed','dispute_open':True}))
asyncio.run(m())
"
# skill:// resource over MCP:
docker compose exec backend python -c "
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
async def m():
    async with streamablehttp_client('http://mcp:9000/mcp') as (rd,wr,*_):
        async with ClientSession(rd,wr) as s:
            await s.initialize()
            r = await s.read_resource('skill://refund-policy')
            print(r.contents[0].text[:80])
asyncio.run(m())
"
```
Expected: `list_skills()` returns 3 skills each with `name`/`description`/`allowed_tools` and NO body text (level 1 stays lean); `scripts` = `['refund_eligibility.py']`; the two script runs return `{"ok":true,"output":{...}}` with `method:"manual_bank_transfer"` and `eligible:false` respectively; `skill://refund-policy` returns the SKILL.md starting with `---\nname: refund-policy`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/skills/loader.py backend/app/skills/definitions backend/pyproject.toml
git commit -m "feat(skills): real library — YAML frontmatter, 3-level disclosure, bundled script

Replaces the --- split with a real yaml parser; adds allowed-tools; makes
list_skills level-1-only. Adds load_skill (L2), run_skill_script + list_scripts
(L3), and skill_markdown for the skill:// resource. Ships refund-policy with an
executable refund_eligibility.py, plus dispute-response; total 3 skills.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Wire skills into tools + model-driven selection (Tools ↔ Skills)

Complete the three registry coroutines stubbed in Task 3, then replace the orchestrator's hardcoded single-skill load with model-driven selection that can run the refund-policy script at level 3.

**Files:**
- Modify: `backend/app/tools/registry.py` (complete `check_refund_eligibility`, `load_skill_tool`, `run_skill_script_tool`).
- Modify: `backend/app/agents/orchestrator.py` (skill selection + level-3 run).

**Interfaces:**
- `registry.check_refund_eligibility` consumes `fixtures.PAYMENTS` + `loader.run_skill_script`; `registry.load_skill_tool` consumes `loader.load_skill`; `registry.run_skill_script_tool` consumes `loader.run_skill_script`.
- Orchestrator consumes `loader.list_skills`, `loader.load_skill`, `loader.run_skill_script`.

- [ ] **Step 1: Complete the three registry coroutines**

In `backend/app/tools/registry.py`, add near the top with the other imports:
```python
from app.skills import loader as _skills
```
Replace the three `raise NotImplementedError` bodies:
```python
async def check_refund_eligibility(*, payment_id: str) -> RefundEligibilityResult:
    """Delegate to the refund-policy skill's level-3 script over the payment's metadata.
    Ties Tools <-> Skills: the verdict is computed by refund_eligibility.py, not here."""
    p = fixtures.PAYMENTS.get(payment_id)
    if not p:
        return RefundEligibilityResult(found=False, payment_id=payment_id,
                                       reason=f"payment {payment_id} not found")
    facts = {
        "days_since_payment": p["age_days"],
        "status": p["status"],
        "refunded": p["refunded"],
        "dispute_open": p["dispute_open"],
        "is_subscription": p["is_subscription"],
        "within_renewal_window": p["renewal_within_14d"],
    }
    run = await _skills.run_skill_script("refund-policy", "refund_eligibility.py", facts)
    if not run.get("ok"):
        return RefundEligibilityResult(found=False, payment_id=payment_id,
                                       reason=run.get("error", "script failed"))
    o = run["output"]
    return RefundEligibilityResult(
        found=True, payment_id=payment_id, eligible=o["eligible"], reason=o["reason"],
        method=o["method"], policy_window_days=o["policy_window_days"],
    )


async def load_skill_tool(*, name: str) -> SkillBody:
    body = _skills.load_skill(name)
    if body is None:
        return SkillBody(found=False, name=name)
    return SkillBody(found=True, name=name, body=body)


async def run_skill_script_tool(*, name: str, script: str,
                                args: dict | None = None) -> SkillScriptResult:
    run = await _skills.run_skill_script(name, script, args or {})
    if not run.get("ok"):
        return SkillScriptResult(ok=False, name=name, script=script, error=run.get("error"))
    return SkillScriptResult(ok=True, name=name, script=script, output=run["output"])
```

- [ ] **Step 2: Model-driven skill selection in `orchestrator.py`**

Change the import (line 25, already updated in Task 0):
```python
from app.skills.loader import load_skill
```
→
```python
from app.skills.loader import list_skills, load_skill, run_skill_script
```
Add a selection schema near the other Pydantic models (after `Critique`):
```python
class SkillSelection(BaseModel):
    names: list[str]          # subset of the offered skill names, [] if none apply
```
Replace the hardcoded load in `_run_pipeline` (line 189):
```python
    skill_body = load_skill("policy-reply-formatter") if use_skill else None
```
with a selection helper call (added below) that returns the concatenated bodies + the chosen names + any level-3 evidence, computed from the ticket + classification:
```python
    selected_names: list[str] = []
    skill_body = None
    skill_evidence: dict | None = None
    if use_skill:
        selected_names, skill_body, skill_evidence = await _select_and_run_skills(ticket)
```
Add this helper after `_critique` (it uses the existing `_json`/`_text` + `settings.model_classify`):
```python
async def _select_and_run_skills(ticket: str) -> tuple[list[str], str | None, dict | None]:
    """Level 1 -> 2 -> 3 progressive disclosure, driven by the model (not hardcoded):
    show only names+descriptions, let the model pick, load the chosen bodies, and — if
    refund-policy is chosen — run its level-3 script so its verdict shapes the reply."""
    catalog = list_skills()
    listing = "\n".join(f"- {s['name']}: {s['description']}" for s in catalog)
    async with span("skill_select", "subagent", model=settings.model_classify) as s:
        sel, usage = await _json(
            settings.model_classify,
            "Select which skills apply to this support ticket. Choose only from the offered names; "
            f"return an empty list if none apply.\n\nAvailable skills:\n{listing}",
            ticket, SkillSelection,
        )
        s.record_usage(usage)
    valid = {s_["name"] for s_ in catalog}
    names = [n for n in sel.get("names", []) if n in valid]
    # Always include the reply formatter when drafting (house style), even if unselected.
    if "policy-reply-formatter" not in names:
        names.append("policy-reply-formatter")

    bodies = [b for b in (load_skill(n) for n in names) if b]
    body = "\n\n".join(bodies) if bodies else None

    evidence = None
    if "refund-policy" in names:
        # Level 3: extract the facts the script needs, then run it.
        facts, u = await _json(
            settings.model_classify,
            "Extract refund facts from the ticket as JSON. Unknown numbers -> null; unknown "
            "booleans -> false. Fields: days_since_payment (int|null), status "
            "(succeeded|pending|failed|refunded|disputed), refunded (bool), dispute_open (bool), "
            "is_subscription (bool), within_renewal_window (bool).",
            ticket, _RefundFacts,
        )
        async with span("skill_script:refund_eligibility", "tool"):
            run = await run_skill_script("refund-policy", "refund_eligibility.py", facts)
        if run.get("ok"):
            evidence = {"skill": "refund-policy", "script": "refund_eligibility.py",
                        "verdict": run["output"]}
    return names, body, evidence
```
Add the extraction schema alongside `SkillSelection`:
```python
class _RefundFacts(BaseModel):
    days_since_payment: int | None = None
    status: str = ""
    refunded: bool = False
    dispute_open: bool = False
    is_subscription: bool = False
    within_renewal_window: bool = False
```
Feed the level-3 verdict into the resolver so it "visibly influences the resolution": in `_resolve`, extend the findings string when `skill_evidence` is present. Change the `_resolve` call sites in `_run_pipeline` to pass it through, and inject it in `_resolve`'s prompt. Minimal approach — append to `findings` inside `_run_pipeline` before resolving:
```python
        if skill_evidence:
            v = skill_evidence["verdict"]
            evidences = evidences + [{
                "subquestion": "Refund eligibility (deterministic policy script)",
                "summary": f"refund-policy/refund_eligibility.py -> eligible={v['eligible']}, "
                           f"method={v['method']}: {v['reason']}",
            }]
```
(Place this right after the retrievers finish, before `_resolve`. `_resolve` already renders `e['subquestion']`/`e['summary']` for every evidence item, so the script verdict flows into the draft with no `_resolve` signature change.)

Finally, surface selection + the level-3 badge in the result dict (replace the `skill_used` line):
```python
            "skills_used": selected_names,
            "skill_evidence": skill_evidence,   # {"skill","script","verdict"} or None -> UI badge
```

- [ ] **Step 3: Verify Tools↔Skills + model-driven selection**

```bash
docker compose up -d --build backend mcp
# check_refund_eligibility runs the script (not inline policy):
docker compose exec backend python -c "
import asyncio
from app.tools import registry as r
async def m():
    print((await r.check_refund_eligibility(payment_id='pay_1004')).model_dump())  # >90d
    print((await r.check_refund_eligibility(payment_id='pay_1010')).model_dump())  # dispute
asyncio.run(m())
"
# model-driven selection + level-3 through the real pipeline:
curl -s -X POST 'localhost:8000/agent/triage' -H 'content-type: application/json' \
  -d '{"message":"I want a refund for a charge from four months ago"}' \
  | python -c "import sys,json; d=json.load(sys.stdin); print('skills_used',d['skills_used']); print('skill_evidence',d.get('skill_evidence'))"
```
Expected: `pay_1004` → `eligible:true, method:"manual_bank_transfer"`; `pay_1010` → `eligible:false, method:"none"` (dispute). The triage call returns `skills_used` containing `refund-policy` (and `policy-reply-formatter`), and `skill_evidence.verdict` with `eligible=false`/`method="manual_bank_transfer"` for the 4-months-ago ticket — proving the script's verdict reached the pipeline. Confirm the observability trace has a `skill_select` span and a `skill_script:refund_eligibility` span: `curl -s localhost:8000/traces/<trace_id>`.

- [ ] **Step 4: Commit**

```bash
git add backend/app/tools/registry.py backend/app/agents/orchestrator.py
git commit -m "feat(tools+skills): check_refund_eligibility runs the skill script; model-driven selection

Completes the registry skill tools (load_skill/run_skill_script/
check_refund_eligibility) so refund eligibility is computed by
refund_eligibility.py, not inline. Orchestrator now selects skills via the
model over list_skills() (no hardcoded name) and runs the refund-policy script
at level 3, injecting its verdict into the resolver + result (skills_used,
skill_evidence badge).

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Gated `escalate` — schema, approval endpoints (the write path)

The tool proposes; the human approves; ONLY the approval endpoint writes. Add the persistence + endpoints. Per the spec open question, use BOTH: a dedicated `escalations` audit table (the handle record) AND `tickets.status`/`assignee` columns (the ticket-status write) — the latter applied when the approval references a known ticket row.

**Files:**
- Modify: `backend/app/schema.sql`, `backend/app/main.py`.
- New: `backend/app/api_escalations.py`.

**Interfaces:**
- `POST /agent/escalations` (approve) — body `{handle, ticket_ref?, ticket_id?, reason, severity, assignee?}` → writes one `escalations` row (`status='approved'`) + optional `tickets` update; returns the committed record.
- `POST /agent/escalations/reject` — records `status='rejected'`, no ticket write.
- `GET /agent/escalations?status=` — list (for the Phase E UI approval card).

- [ ] **Step 1: Extend `backend/app/schema.sql`**

Append (idempotent — `ADD COLUMN IF NOT EXISTS` is supported by Postgres):
```sql
-- Phase C schema: human-in-the-loop escalation approvals. The escalate TOOL writes NOTHING;
-- a row appears here ONLY when a human approves (or rejects) a proposal via the API. Runs
-- idempotently on startup like the tables above.
CREATE TABLE IF NOT EXISTS escalations (
    id          BIGSERIAL   PRIMARY KEY,
    handle      TEXT        UNIQUE NOT NULL,        -- proposal handle from the escalate tool (ESC-xxxx)
    ticket_ref  TEXT,                                -- external ticket id / free-text ref, if any
    ticket_id   BIGINT      REFERENCES tickets(id) ON DELETE SET NULL,  -- links to a saved run, if any
    reason      TEXT        NOT NULL,
    severity    TEXT        NOT NULL,                -- low | medium | high
    status      TEXT        NOT NULL,                -- approved | rejected
    assignee    TEXT,                                -- queue/agent handle set at approval
    decided_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS escalations_status_idx ON escalations (status, decided_at DESC);

-- The ticket-status write half of the gate: applied to a saved ticket when an escalation is approved.
ALTER TABLE tickets ADD COLUMN IF NOT EXISTS status   TEXT;   -- e.g. 'escalated'
ALTER TABLE tickets ADD COLUMN IF NOT EXISTS assignee TEXT;   -- queue/agent handle
```

- [ ] **Step 2: Write `backend/app/api_escalations.py`**

```python
"""Human-in-the-loop escalation approvals (topic: "tools").

The `escalate` tool only PROPOSES (returns a handle, writes nothing). These
endpoints are the sole writers: a row lands in `escalations` — and the linked
ticket's status flips to 'escalated' — only when a human approves. This is the
textbook reason a destructive action becomes a dedicated, gated tool.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.db import get_pool

router = APIRouter(prefix="/agent/escalations", tags=["escalations"])

_DEFAULT_ASSIGNEE = "human-agent-queue"


class ApproveIn(BaseModel):
    handle: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    severity: str = Field("medium", pattern="^(low|medium|high)$")
    ticket_ref: str | None = None
    ticket_id: int | None = None       # links to a saved tickets row, if the client has one
    assignee: str | None = None


class RejectIn(BaseModel):
    handle: str = Field(min_length=1)
    reason: str = Field(min_length=1)


async def _record(body: ApproveIn | RejectIn, *, status: str,
                  assignee: str | None, ticket_id: int | None,
                  ticket_ref: str | None, severity: str) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """INSERT INTO escalations (handle, ticket_ref, ticket_id, reason, severity, status, assignee)
                   VALUES ($1,$2,$3,$4,$5,$6,$7)
                   ON CONFLICT (handle) DO NOTHING
                   RETURNING id, handle, status, assignee, decided_at""",
                body.handle, ticket_ref, ticket_id, body.reason, severity, status, assignee,
            )
            if row is None:
                raise HTTPException(status_code=409, detail=f"handle {body.handle} already decided")
            # The ticket-status write half of the gate (only on approval + a known ticket).
            if status == "approved" and ticket_id is not None:
                await conn.execute(
                    "UPDATE tickets SET status='escalated', assignee=$2 WHERE id=$1",
                    ticket_id, assignee,
                )
    return {"id": row["id"], "handle": row["handle"], "status": row["status"],
            "assignee": row["assignee"], "decided_at": row["decided_at"].isoformat(),
            "ticket_id": ticket_id}


@router.post("")
async def approve(body: ApproveIn):
    """Commit an escalation a human approved. This is the ONLY code path that writes."""
    assignee = body.assignee or _DEFAULT_ASSIGNEE
    return await _record(body, status="approved", assignee=assignee,
                         ticket_id=body.ticket_id, ticket_ref=body.ticket_ref,
                         severity=body.severity)


@router.post("/reject")
async def reject(body: RejectIn):
    """Record a rejected proposal — no ticket write."""
    return await _record(body, status="rejected", assignee=None, ticket_id=None,
                         ticket_ref=None, severity="medium")


@router.get("")
async def list_escalations(status: str | None = Query(None, pattern="^(approved|rejected)$"),
                           limit: int = Query(50, ge=1, le=200)):
    pool = await get_pool()
    if status:
        rows = await pool.fetch(
            "SELECT id, handle, ticket_ref, ticket_id, reason, severity, status, assignee, decided_at "
            "FROM escalations WHERE status=$1 ORDER BY decided_at DESC LIMIT $2", status, limit)
    else:
        rows = await pool.fetch(
            "SELECT id, handle, ticket_ref, ticket_id, reason, severity, status, assignee, decided_at "
            "FROM escalations ORDER BY decided_at DESC LIMIT $1", limit)
    return {"escalations": [
        {**{k: r_[k] for k in ("id", "handle", "ticket_ref", "ticket_id", "reason",
                               "severity", "status", "assignee")},
         "decided_at": r_["decided_at"].isoformat()}
        for r_ in rows
    ]}
```

- [ ] **Step 3: Mount the router in `backend/app/main.py`**

Add the import beside the other routers:
```python
from app.api_escalations import router as escalations_router
```
and register it beside the others:
```python
app.include_router(escalations_router)
```

- [ ] **Step 4: Verify the gate (no write without approval; write on approval)**

```bash
docker compose up -d --build backend
# 1) Calling the escalate tool writes NOTHING:
docker compose exec backend python -c "
import asyncio
from app.tools import registry as r
print(asyncio.run(r.escalate(ticket_ref='TKT-9001', reason='cannot verify identity', severity='high')).model_dump())
"
docker compose exec backend python -c "
import asyncio
from app.db import get_pool
async def m():
    p=await get_pool(); print('rows before approval:', await p.fetchval('SELECT count(*) FROM escalations'))
asyncio.run(m())
"
# 2) Approval is the write:
curl -s -X POST localhost:8000/agent/escalations -H 'content-type: application/json' \
  -d '{"handle":"ESC-testcafe","reason":"cannot verify identity","severity":"high","ticket_ref":"TKT-9001"}'
docker compose exec backend python -c "
import asyncio
from app.db import get_pool
async def m():
    p=await get_pool(); print('rows after approval:', await p.fetchval('SELECT count(*) FROM escalations'))
asyncio.run(m())
"
curl -s 'localhost:8000/agent/escalations?status=approved'
```
Expected: the tool returns `status:"proposed", committed:false`; `rows before approval: 0` (the tool wrote nothing); after `POST`, the endpoint returns `status:"approved", assignee:"human-agent-queue"`; `rows after approval: 1`; the list shows the approved record. A second POST with the same handle returns HTTP 409.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schema.sql backend/app/api_escalations.py backend/app/main.py
git commit -m "feat(api): gated escalate — approval endpoint is the only writer

Adds the escalations audit table + tickets status/assignee columns and
POST/GET /agent/escalations. The escalate tool proposes (writes nothing); a row
lands only when a human approves, which also flips a linked ticket to
'escalated'. Reject + list included for the Phase E approval card.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Make MCP the backbone — orchestrator retrieve via MCP with in-process fallback (spec 03)

Route the orchestrator's hybrid retrieve through the MCP client so MCP is on the critical path, falling back to the in-process registry when the `mcp` service is down. The lexical/semantic eval-regression modes stay in-process (MCP only exposes hybrid).

**Files:**
- Modify: `backend/app/mcp/client.py` (add `mcp_search_or_local`), `backend/app/agents/orchestrator.py` (use it in the retrieve phase).

**Interfaces:**
- Produces (`mcp/client.py`): `@asynccontextmanager async def mcp_search_or_local(search_mode: str)` yielding `(search_fn, transport)` where `search_fn(subquestion: str, k: int) -> list[dict]` returns rows shaped like `rag.hybrid_search` (so `_retrieve`'s existing `r['title']`/`r['content']`/`r['id']`/`r['source_type']` access is unchanged), and `transport ∈ {"mcp","in-process"}`.
- Consumed by: `orchestrator._run_pipeline`.

- [ ] **Step 1: Add the transport helper to `backend/app/mcp/client.py`**

Append:
```python
import json as _json
from contextlib import asynccontextmanager as _acm

from app.rag import search as _search
from app.tools import registry as _registry


def _hits_to_rows(result_json: str) -> list[dict]:
    """MCP hybrid_search returns our HybridSearchResult as structured JSON; project its
    typed hits back to the row shape the retriever subagent already consumes."""
    data = _json.loads(result_json)
    hits = data.get("hits", []) if isinstance(data, dict) else []
    return [{"id": h["chunk_id"], "document_id": h["document_id"],
             "source_type": h["source_type"], "title": h["title"],
             "content": h["preview"], "score": h["scores"]["fused"]}
            for h in hits]


@_acm
async def mcp_search_or_local(search_mode: str):
    """Yield (search_fn, transport). For hybrid mode, probe the MCP server and — if up —
    run retrieval THROUGH the protocol (MCP is the backbone). If the mcp service is down,
    or the mode is lexical/semantic (eval-regression, not exposed over MCP), fall back to
    the in-process path. Capability negotiation (server name/proto/primitives) is logged."""
    if search_mode != "hybrid":
        async def local(subq: str, k: int):
            return await _search._SEARCH_FN_BY_MODE[search_mode](subq, k)  # see note below
        yield local, "in-process"
        return

    try:
        async with mcp_session() as session:
            init_tools = await session.list_tools()
            print(f"[mcp] backbone up: tools={[t.name for t in init_tools.tools]}")

            async def via_mcp(subq: str, k: int):
                res = await session.call_tool("hybrid_search", arguments={"query": subq, "k": k})
                texts = [c.text for c in res.content if getattr(c, "type", None) == "text"]
                return _hits_to_rows(texts[0]) if texts else []

            yield via_mcp, "mcp"
            return
    except Exception as exc:  # noqa: BLE001 - MCP down -> graceful in-process fallback
        print(f"[mcp] backbone unavailable ({exc!r}); falling back to in-process registry")

    async def fallback(subq: str, k: int):
        result = await _registry.hybrid_search(query=subq, k=k)
        return _hits_to_rows(result.model_dump_json())
    yield fallback, "in-process"
```
> **Note on lexical/semantic:** `rag/search.py` exposes `lexical_search`/`semantic_search`/`hybrid_search` but no `_SEARCH_FN_BY_MODE`. Add that mapping to `rag/search.py` (a two-line dict at module bottom) OR replace the `local` branch with an inline dict here. Prefer the inline dict to avoid touching search.py again:
```python
    if search_mode != "hybrid":
        _fns = {"lexical": _search.lexical_search, "semantic": _search.semantic_search}
        async def local(subq: str, k: int):
            return await _fns[search_mode](subq, k)
        yield local, "in-process"
        return
```

- [ ] **Step 2: Use it in `orchestrator._run_pipeline`**

Import at the top of `orchestrator.py`:
```python
from app.mcp.client import mcp_search_or_local
```
Change `_retrieve` to accept an injected `search_fn` instead of reaching into `_SEARCH_FNS`:
```python
async def _retrieve(subquestion: str, search_fn):
    """A retriever subagent: search (via the injected transport), then summarize into a
    compact, cited evidence note."""
    async with span("retriever", "subagent", model=settings.model_classify) as s:
        t0 = time.time()
        rows = await search_fn(subquestion, 4)
        evidence = "\n".join(f"- [{r['title']}] {r['content'][:200]}" for r in rows)
        summary, usage = await _text(
            settings.model_classify,
            "Summarize the evidence into 2-3 sentences that answer the question. Cite sources as [title]. "
            "Use ONLY the evidence provided.",
            f"Question: {subquestion}\n\nEvidence:\n{evidence}",
            max_tokens=300,
        )
        s.record_usage(usage)
        result = {
            "subquestion": subquestion,
            "summary": summary,
            "cited": [
                {"chunk_id": r["id"], "title": r["title"], "source_type": r["source_type"],
                 "snippet": r["content"][:300]}
                for r in rows
            ],
            "seconds": round(time.time() - t0, 2),
        }
        return result, usage
```
Update `_retrieve_emit` (inside `_run_pipeline`) to pass the injected fn, and wrap the retrieve phase in the transport context manager. Replace the retrieve block (lines ~203-217) so the search transport is opened once per run:
```python
    async def _retrieve_emit(index: int, subquestion: str, search_fn):
        await emit({"type": "step_start", "step": "retrieve", "index": index, "subquestion": subquestion})
        result, u = await _retrieve(subquestion, search_fn)
        await emit({"type": "step_done", "step": "retrieve", "index": index, "data": result})
        return result, u
```
and in the pipeline body, replace the `_retrieve_emit(i, q)` gather with:
```python
        # 2) retrievers in parallel — routed through MCP (the backbone) with in-process fallback
        t0 = time.time()
        async with mcp_search_or_local(search_mode) as (search_fn, transport):
            retrieved = await asyncio.gather(
                *[_retrieve_emit(i, q, search_fn) for i, q in enumerate(questions)]
            )
        parallel_seconds = round(time.time() - t0, 2)
```
Then delete the now-unused `_SEARCH_FNS` dict (lines 30-34) and its comment, since `_retrieve` no longer references it and `mcp_search_or_local` owns mode routing. Surface the transport in the result dict (next to `parallelism`):
```python
            "retrieval_transport": transport,   # "mcp" (backbone) or "in-process" (fallback)
```
(Add `transport` to the closure scope — it is bound inside the `async with`; capture it into a `nonlocal`/outer variable, e.g. initialize `retrieval_transport = "in-process"` before the `async with` and assign `retrieval_transport = transport` inside it, then use `retrieval_transport` in the result dict.)

- [ ] **Step 3: Verify backbone + fallback**

```bash
docker compose up -d --build backend mcp
# Backbone path (mcp up): expect retrieval_transport == "mcp"
curl -s -X POST localhost:8000/agent/triage -H 'content-type: application/json' \
  -d '{"message":"why was I charged twice for my subscription?"}' \
  | python -c "import sys,json; d=json.load(sys.stdin); print('transport',d['retrieval_transport']); print('final?',bool(d['final_reply']))"
docker compose logs backend --tail 5   # expect "[mcp] backbone up: tools=[...]"
# Fallback path (mcp down): expect retrieval_transport == "in-process", still resolves
docker compose stop mcp
curl -s -X POST localhost:8000/agent/triage -H 'content-type: application/json' \
  -d '{"message":"refund not received yet"}' \
  | python -c "import sys,json; d=json.load(sys.stdin); print('transport',d['retrieval_transport']); print('final?',bool(d['final_reply']))"
docker compose logs backend --tail 5   # expect "[mcp] backbone unavailable ...; falling back"
docker compose start mcp
```
Expected: with `mcp` up, `transport mcp` and a real `final_reply`; with `mcp` stopped, `transport in-process` and still a real `final_reply` (verified fallback). The eval regression path still works: `curl -s -X POST 'localhost:8000/agent/triage?search_mode=lexical' -d '{"message":"..."}' -H 'content-type: application/json'` returns `transport in-process`.

- [ ] **Step 4: Commit**

```bash
git add backend/app/mcp/client.py backend/app/agents/orchestrator.py
git commit -m "feat(mcp): route orchestrator retrieve through MCP with in-process fallback

hybrid retrieval now runs THROUGH the MCP server (the backbone), degrading to
the in-process registry when the mcp service is down. lexical/semantic eval
modes stay in-process. Result carries retrieval_transport for the UI; capability
negotiation is logged. MCP is now load-bearing, not a side demo.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review

**Spec 05 (Tools) coverage:**
- Strict input schema (`additionalProperties:false`, enums, required) → Task 3 `_obj()` + `TOOL_SPECS` (enums on `source_type`, `severity`; runtime `extra="forbid"` proven in Task 3 Step 2). ✅
- Pydantic-typed structured output → outputSchema → Task 3 output models; consumed as FastMCP `outputSchema` in Task 4 (verified `hybrid_search has outputSchema: True`). ✅
- Annotations declared once, imported by MCP → `ANNOTATIONS` in Task 3; `_ann()` wraps them in Task 4; grep check in Cross-task check below. ✅
- Shared row→dict projection kills duplicate `_hybrid_search` → `hit_from_row` (Task 3); MCP server calls `registry.hybrid_search` (Task 4), no second projection body. ✅
- New mock reads `lookup_customer`/`get_payment_status` over fixtures → Task 2 fixtures + Task 3 coroutines (verified Task 3 Step 2 + Task 4 tool list). ✅
- `check_refund_eligibility` delegates to the skill script → Task 6 Step 1 (`run_skill_script(...)`, verified Task 6 Step 3). ✅
- Real gated `escalate` (DB write + status/handle) deferred to UI approval → Task 3 pure proposal + Task 7 approval endpoint = only writer + `tickets.status='escalated'` (verified Task 7 Step 4: 0 rows before, 1 after). ✅
- `hybrid_search`/`dispatch` name storms resolved → single `dispatch` in registry; `hybrid_search` is one coroutine reused by both paths. ✅

**Spec 03 (MCP) coverage:**
- All three primitives with annotations + outputSchema imported → Task 4 (tools, resources, prompts; verified over the wire in Step 2). ✅
- Resources `kb://doc/{id}`, `kb://index`, `ticket://{id}`, `skill://{name}` → Task 4 (`kb://doc/1` + `skill://refund-policy` read verified in Task 4/5). ✅
- Prompts `/triage-refund`, `/draft-reply`, `/summarize-thread` → Task 4 (`triage_refund`, `draft_reply`, `summarize_thread` in prompt list). ✅
- Orchestrator retrieve through MCP client + verified in-process fallback → Task 8 (both transports verified). ✅
- Local-client-vs-connector rationale kept → Task 4 module docstring. ✅
- Capability negotiation display → Task 4 Step 2 (`initialize()` prints serverInfo/proto) + Task 8 log line. `listChanged` on re-ingest is noted as an open question (see below). ⚠️ (partial — see open questions)

**Spec 04 (Skills) coverage:**
- ≥3 skills in `definitions/` with valid YAML; `list_skills()` returns them → Task 5 (`policy-reply-formatter`, `refund-policy`, `dispute-response`; verified level-1 listing). ✅
- Real YAML frontmatter parser → Task 5 `_parse` uses `yaml.safe_load` (pyyaml added). ✅
- Three-level disclosure → Task 5 (`list_skills` L1 / `load_skill` L2 / `list_scripts`+`run_skill_script` L3). ✅
- Bundled `refund-policy/scripts/refund_eligibility.py` runs at L3, visibly influences resolution → Task 5 (script) + Task 6 (injected into resolver + `skill_evidence` badge; verified via `/agent/triage`). ✅
- Model-driven selection via `load_skill`/`run_skill_script` tool (no hardcoded skill) → Task 6 `_select_and_run_skills` replaces `load_skill("policy-reply-formatter")`. ✅
- `list_skills()` live → drives selection (Task 6) + catalog; no longer dead code. ✅
- `skill://{name}` readable over MCP → Task 4 + Task 5 (`skill_markdown`, verified). ✅

**Cross-task type/signature consistency (the registry symbols must match everywhere):**
- `ANNOTATIONS` keys = the 9 tool names; `_ann(name)` in Task 4 indexes them; no annotation re-declared. Grep gate: `grep -rn "readOnlyHint\|destructiveHint\|idempotentHint" backend/app | grep -v tools/registry.py` must be empty. ✅
- MCP tool wrappers (Task 4) return the exact registry output models (`r.HybridSearchResult` etc.) their coroutines return (Task 3/6) — names match one-to-one. ✅
- `dispatch` (Task 3) validates via `_INPUT_MODELS` whose keys == `_DISPATCH` keys == `TOOL_SPECS` names == `ANNOTATIONS` keys (all 9). ✅
- `hit_from_row` shape ↔ `_hits_to_rows` (Task 8) inverse mapping: `chunk_id→id`, `preview→content`, `scores.fused→score`, plus `document_id/source_type/title` — matches `_retrieve`'s `r['id']/r['document_id']/r['source_type']/r['title']/r['content']` access. ✅
- `check_refund_eligibility` fixture field names (Task 2: `age_days`, `renewal_within_14d`, `dispute_open`, `is_subscription`, `refunded`, `status`) ↔ script arg names (Task 5: `days_since_payment`, `within_renewal_window`, `dispute_open`, `is_subscription`, `refunded`, `status`) mapped explicitly in Task 6 Step 1. ✅
- Orchestrator `run_skill_script('refund-policy','refund_eligibility.py', facts)` ↔ loader containment check + script argv/JSON contract (Task 5). `_RefundFacts` fields == script's expected keys. ✅
- `mcp_search_or_local` yields `(search_fn, transport)`; `_run_pipeline` binds both, threads `search_fn` into `_retrieve_emit`→`_retrieve`, and records `retrieval_transport`. `_retrieve` no longer references the deleted `_SEARCH_FNS`. ✅

**Placeholder scan:** no TBD/TODO; complete code given for every new file and every edit. The only deliberately deferred bodies (`check_refund_eligibility`/`load_skill_tool`/`run_skill_script_tool` raising `NotImplementedError` in Task 3) are explicitly completed in Task 6, and the intermediate build stays runnable because those tools aren't called until Task 6. ✅

**Ordering / dependency integrity:** Task 0 (moves) → 1 (rag) → 2 (fixtures) → 3 (registry, imports 1+2) → 4 (MCP, imports 3; needs 5's `skill_markdown` — build 5 right after, or use the documented stub) → 5 (skills) → 6 (registry↔skills + orchestrator; needs 3+5) → 7 (escalate write path; independent, needs 3's pure tool) → 8 (backbone; needs 3+4). Each task ends runnable + committed. ✅
