"""Observability surfacing that the React Run Inspector consumes.

- /observability/config: tells the frontend whether Langfuse is enabled at all.
- /observability/metrics/{chart}: real Langfuse Metrics API v2 aggregates (observations,
  cost, latency, scores), normalized in app/langfuse_metrics.py. Langfuse dashboards don't
  support shareable/embeddable links, so this — not an iframe — is how the Run Inspector's
  Analytics section gets its charts (spec 06's documented API-pull fallback).
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException

from app import langfuse_client, langfuse_metrics

router = APIRouter(prefix="/observability", tags=["observability"])


@router.get("/config")
async def config():
    return {"langfuse_enabled": langfuse_client.enabled}


@router.get("/metrics/{chart}")
async def metrics(chart: str, granularity: str = "day", hours: int = 24 * 7):
    if chart not in langfuse_metrics.CHARTS:
        raise HTTPException(status_code=400, detail=f"unknown chart {chart!r}, expected one of {langfuse_metrics.CHARTS}")
    now = datetime.now(timezone.utc)
    frm = now - timedelta(hours=hours)
    return await langfuse_metrics.query(chart, granularity, frm.isoformat(), now.isoformat())
