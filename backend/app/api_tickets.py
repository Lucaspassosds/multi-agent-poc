"""Ticket history — persist each successful triage run and list/read past runs per session.

Mirrors the read-side conventions of api_traces.py (APIRouter + asyncpg pool + .isoformat()).
The agent timeline is NOT stored here: it already lives in `spans`, reachable via GET
/traces/{trace_id}; a ticket only links to it through `trace_id`.
"""
import json

from fastapi import APIRouter, HTTPException, Query

from app.db import get_pool

router = APIRouter(prefix="/tickets", tags=["tickets"])


async def save_ticket(session_id: str, result: dict) -> int:
    """Persist one successful triage run. `result` is the TriageResult dict the pipeline
    returns (see agents/orchestrator.py). Returns the new tickets.id."""
    pool = await get_pool()
    return await pool.fetchval(
        """
        INSERT INTO tickets (session_id, ticket_text, category, final_reply, result, trace_id)
        VALUES ($1, $2, $3, $4, $5::jsonb, $6)
        RETURNING id
        """,
        session_id,
        result["ticket"],
        (result.get("classification") or {}).get("category"),
        result["final_reply"],
        json.dumps(result),        # asyncpg has no dict->jsonb codec here; send text + ::jsonb cast
        result.get("trace_id"),
    )


@router.get("")
async def list_tickets(
    session_id: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT id, ticket_text, category, trace_id, created_at
        FROM tickets
        WHERE session_id = $1
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        session_id, limit, offset,
    )
    total = await pool.fetchval(
        "SELECT count(*) FROM tickets WHERE session_id = $1", session_id
    )
    return {
        "tickets": [
            {
                "id": r["id"],
                "ticket_text": r["ticket_text"],
                "category": r["category"],
                "trace_id": r["trace_id"],
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ],
        "total": total,
    }


@router.get("/{ticket_id}")
async def get_ticket(ticket_id: int):
    pool = await get_pool()
    row = await pool.fetchrow("SELECT result FROM tickets WHERE id = $1", ticket_id)
    if row is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    result = row["result"]
    # asyncpg returns JSONB as a str (no decoder registered on this pool); normalize to a dict.
    return json.loads(result) if isinstance(result, str) else result
