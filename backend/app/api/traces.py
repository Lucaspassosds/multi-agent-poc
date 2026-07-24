"""Phase 6 — read side of observability: list traces and drill into a span tree.

Written to be consumed directly by the Phase 8 dashboard (a waterfall over `GET /traces/{id}`).
"""
from fastapi import APIRouter, HTTPException, Query

from app.config import settings
from app.db import get_pool
from app.observability import cost_usd

router = APIRouter(prefix="/traces", tags=["traces"])


def _pct(numerator: int, denominator: int) -> float:
    return round(numerator / denominator * 100, 1) if denominator else 0.0


def _over_budget(cost_usd_total: float, duration_seconds: float) -> bool:
    return cost_usd_total > settings.cost_budget_usd or (duration_seconds * 1000) > settings.latency_budget_ms


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
                "over_budget": _over_budget(float(r["total_cost_usd"]), r["duration_seconds"]),
            }
            for r in rows
        ],
        "total": total,
        "budgets": {"cost_budget_usd": settings.cost_budget_usd, "latency_budget_ms": settings.latency_budget_ms},
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


@router.get("/stats")
async def stats(name: str = Query("triage", pattern="^(triage|eval|agent)$")):
    pool = await get_pool()
    pct = await pool.fetchrow(
        """
        SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (ended_at - started_at))) AS p50,
               percentile_cont(0.95) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (ended_at - started_at))) AS p95,
               count(*) AS n
        FROM traces WHERE name = $1
        """,
        name,
    )
    role_rows = await pool.fetch(
        """
        SELECT s.name, s.model,
               count(*) AS calls,
               COALESCE(SUM(s.input_tokens), 0)  AS input_tokens,
               COALESCE(SUM(s.output_tokens), 0) AS output_tokens,
               COALESCE(SUM(s.cache_read_tokens), 0) AS cache_read_tokens,
               COALESCE(SUM(s.retries), 0)       AS retries
        FROM spans s JOIN traces t ON t.id = s.trace_id
        WHERE t.name = $1
        GROUP BY s.name, s.model
        ORDER BY SUM(s.input_tokens) + SUM(s.output_tokens) DESC
        """,
        name,
    )
    per_role = [
        {
            "role": r["name"],
            "model": r["model"],
            "calls": r["calls"],
            "input_tokens": r["input_tokens"],
            "output_tokens": r["output_tokens"],
            "cache_read_tokens": r["cache_read_tokens"],
            "retries": r["retries"],
            "cost_usd": cost_usd(r["model"], r["input_tokens"], r["output_tokens"]),
        }
        for r in role_rows
    ]
    return {
        "name": name,
        "n_runs": pct["n"],
        "p50_seconds": round(pct["p50"], 3) if pct["p50"] is not None else None,
        "p95_seconds": round(pct["p95"], 3) if pct["p95"] is not None else None,
        "per_role": per_role,
        "budgets": {"cost_budget_usd": settings.cost_budget_usd,
                    "latency_budget_ms": settings.latency_budget_ms},
    }


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
    duration_seconds = (trace_row["ended_at"] - trace_row["started_at"]).total_seconds()

    return {
        "id": trace_row["id"],
        "name": trace_row["name"],
        "ticket_id": trace_row["ticket_id"],
        "status": trace_row["status"],
        "started_at": trace_row["started_at"].isoformat(),
        "ended_at": trace_row["ended_at"].isoformat(),
        "duration_seconds": round(duration_seconds, 3),
        "total_tokens": trace_row["total_tokens"],
        "total_cost_usd": float(trace_row["total_cost_usd"]),
        "cache_hit_pct": _pct(total_cache, total_input),
        "over_budget": _over_budget(float(trace_row["total_cost_usd"]), duration_seconds),
        "langfuse_trace_id": trace_row["langfuse_trace_id"],
        "langfuse_url": trace_row["langfuse_url"],
        "spans": _build_tree(spans),
    }
