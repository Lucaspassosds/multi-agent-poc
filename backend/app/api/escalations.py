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
