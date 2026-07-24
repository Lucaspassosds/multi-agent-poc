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
from app.skills import loader as _skills
from app.tools import fixtures

# --------------------------------------------------------------------------- #
# Output models  (typed structured output -> MCP outputSchema)
# --------------------------------------------------------------------------- #
class HitScores(BaseModel):
    lexical: float | None = None
    semantic: float | None = None
    fused: float
    lexical_rank: int | None = None
    semantic_rank: int | None = None


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
            lexical_rank=row.get("lexical_rank"),
            semantic_rank=row.get("semantic_rank"),
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


async def escalate(*, ticket_ref: str | None = None, reason: str,
                   severity: str = "medium") -> EscalateResult:
    """PROPOSE an escalation. Writes NOTHING — the gate. The write commits only
    when a human approves via POST /agent/escalations (see app/api/escalations.py)."""
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
