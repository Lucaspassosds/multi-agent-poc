"""Phase 6 — read side of observability: list traces and drill into a span tree.

Written to be consumed directly by the Phase 8 dashboard (a waterfall over `GET /traces/{id}`).
"""
from fastapi import APIRouter, HTTPException, Query

from app.db import get_pool

router = APIRouter(prefix="/traces", tags=["traces"])


def _pct(numerator: int, denominator: int) -> float:
    return round(numerator / denominator * 100, 1) if denominator else 0.0


@router.get("")
async def list_traces(limit: int = Query(20, ge=1, le=200), offset: int = Query(0, ge=0)):
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT t.id, t.name, t.ticket_id, t.status, t.started_at, t.ended_at,
               t.total_tokens, t.total_cost_usd,
               EXTRACT(EPOCH FROM (t.ended_at - t.started_at)) AS duration_seconds,
               COALESCE(SUM(s.input_tokens), 0)     AS total_input_tokens,
               COALESCE(SUM(s.cache_read_tokens), 0) AS total_cache_tokens,
               COALESCE(SUM(s.retries), 0)          AS total_retries
        FROM traces t
        LEFT JOIN spans s ON s.trace_id = t.id
        GROUP BY t.id
        ORDER BY t.started_at DESC
        LIMIT $1 OFFSET $2
        """,
        limit, offset,
    )
    total = await pool.fetchval("SELECT count(*) FROM traces")
    return {
        "traces": [
            {
                "id": r["id"],
                "name": r["name"],
                "ticket_id": r["ticket_id"],
                "status": r["status"],
                "started_at": r["started_at"].isoformat(),
                "ended_at": r["ended_at"].isoformat(),
                "duration_seconds": round(r["duration_seconds"], 3),
                "total_tokens": r["total_tokens"],
                "total_cost_usd": float(r["total_cost_usd"]),
                "cache_hit_pct": _pct(r["total_cache_tokens"], r["total_input_tokens"]),
                "retries": r["total_retries"],
            }
            for r in rows
        ],
        "total": total,
    }


def _build_tree(spans: list[dict]) -> list[dict]:
    by_id = {s["id"]: {**s, "children": []} for s in spans}
    roots = []
    for s in by_id.values():
        parent = s["parent_id"]
        if parent is not None and parent in by_id:
            by_id[parent]["children"].append(s)
        else:
            roots.append(s)
    return roots


@router.get("/{trace_id}")
async def get_trace(trace_id: int):
    pool = await get_pool()
    trace_row = await pool.fetchrow("SELECT * FROM traces WHERE id = $1", trace_id)
    if trace_row is None:
        raise HTTPException(status_code=404, detail="trace not found")

    span_rows = await pool.fetch(
        "SELECT * FROM spans WHERE trace_id = $1 ORDER BY id", trace_id
    )
    spans = [
        {
            "id": r["id"],
            "parent_id": r["parent_id"],
            "name": r["name"],
            "span_type": r["span_type"],
            "model": r["model"],
            "started_at": r["started_at"].isoformat(),
            "ended_at": r["ended_at"].isoformat(),
            "duration_seconds": round((r["ended_at"] - r["started_at"]).total_seconds(), 3),
            "input_tokens": r["input_tokens"],
            "output_tokens": r["output_tokens"],
            "cache_read_tokens": r["cache_read_tokens"],
            "cache_creation_tokens": r["cache_creation_tokens"],
            "retries": r["retries"],
            "error": r["error"],
        }
        for r in span_rows
    ]
    total_input = sum(s["input_tokens"] for s in spans)
    total_cache = sum(s["cache_read_tokens"] for s in spans)

    return {
        "id": trace_row["id"],
        "name": trace_row["name"],
        "ticket_id": trace_row["ticket_id"],
        "status": trace_row["status"],
        "started_at": trace_row["started_at"].isoformat(),
        "ended_at": trace_row["ended_at"].isoformat(),
        "duration_seconds": round((trace_row["ended_at"] - trace_row["started_at"]).total_seconds(), 3),
        "total_tokens": trace_row["total_tokens"],
        "total_cost_usd": float(trace_row["total_cost_usd"]),
        "cache_hit_pct": _pct(total_cache, total_input),
        "spans": _build_tree(spans),
    }
