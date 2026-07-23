"""Tools the agent can call (topic: "tools") + a dispatcher.

A tool = a JSON-schema-described function the model may choose to call. The model
never runs code; it emits a tool call, WE execute the Python here and feed the result back.
"""
# ── Concept: TOOLS (FUNCTION CALLING) ── JSON-schema tool specs + a dispatcher: hybrid_search / get_document / get_ticket / escalate.
import json

from app.db import get_pool
from app.llm.base import ToolSpec
from app.rag.search import hybrid_search as _hybrid

TOOL_SPECS = [
    ToolSpec(
        name="hybrid_search",
        description="Search the knowledge base and past resolved tickets for relevant passages. "
                    "Use this before answering any factual or policy question.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to search for"},
                "k": {"type": "integer", "description": "Number of results (default 5)"},
            },
            "required": ["query"],
        },
    ),
    ToolSpec(
        name="get_document",
        description="Fetch the full text of a knowledge-base document by its numeric id.",
        parameters={
            "type": "object",
            "properties": {"document_id": {"type": "integer"}},
            "required": ["document_id"],
        },
    ),
    ToolSpec(
        name="get_ticket",
        description="Fetch a past resolved ticket and its resolution by ticket id (e.g. 'TKT-1001').",
        parameters={
            "type": "object",
            "properties": {"ticket_id": {"type": "string"}},
            "required": ["ticket_id"],
        },
    ),
    ToolSpec(
        name="escalate",
        description="Escalate to a human agent when the ticket cannot be resolved from available info.",
        parameters={
            "type": "object",
            "properties": {"reason": {"type": "string"}},
            "required": ["reason"],
        },
    ),
]


async def _hybrid_search(query: str, k: int = 5) -> list[dict]:
    rows = await _hybrid(query, k)
    return [
        {"chunk_id": r["id"], "document_id": r["document_id"], "source_type": r["source_type"],
         "title": r["title"], "preview": r["content"][:300]}
        for r in rows
    ]


async def _get_document(document_id: int) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, source_type, title, url, content FROM documents WHERE id = $1", int(document_id)
    )
    if not row:
        return {"error": f"document {document_id} not found"}
    return {"id": row["id"], "title": row["title"], "source_type": row["source_type"],
            "content": row["content"][:4000]}


async def _get_ticket(ticket_id: str) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT external_id, title, content, metadata FROM documents "
        "WHERE source_type = 'ticket' AND external_id = $1", str(ticket_id)
    )
    if not row:
        return {"error": f"ticket {ticket_id} not found"}
    meta = row["metadata"]
    return {"ticket_id": row["external_id"], "subject": row["title"], "content": row["content"],
            "metadata": json.loads(meta) if isinstance(meta, str) else meta}


async def _escalate(reason: str) -> dict:
    return {"escalated": True, "reason": reason}


_DISPATCH = {
    "hybrid_search": _hybrid_search,
    "get_document": _get_document,
    "get_ticket": _get_ticket,
    "escalate": _escalate,
}


async def dispatch(name: str, args: dict) -> str:
    """Run a tool by name; always returns a JSON string (errors included, never raises)."""
    fn = _DISPATCH.get(name)
    if fn is None:
        return json.dumps({"error": f"unknown tool {name}"})
    try:
        result = await fn(**(args or {}))
    except Exception as exc:  # fed back to the model as an error tool_result so it can adapt
        return json.dumps({"error": repr(exc)})
    return json.dumps(result, default=str)
