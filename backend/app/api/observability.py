"""Phase D — observability surfacing that the Phase-E React panels consume.

- /observability/config: hands the frontend the shared Langfuse dashboard URL to iframe
  (embed-first per spec 06 F).
- /observability/langfuse-metrics: the API-pull FALLBACK for when the embed is blocked by
  CSP/auth — best-effort aggregates via the Langfuse public Metrics API. Fails soft to an
  explanatory payload so the UI can show the in-app KPIs instead.
"""
import base64

import httpx
from fastapi import APIRouter

from app import langfuse_client
from app.config import settings

router = APIRouter(prefix="/observability", tags=["observability"])


@router.get("/config")
async def config():
    return {
        "langfuse_enabled": langfuse_client.enabled,
        "langfuse_dashboard_url": settings.langfuse_dashboard_url or None,
    }


@router.get("/langfuse-metrics")
async def langfuse_metrics():
    """Best-effort pull of daily cost/latency/token aggregates. Verify the exact Metrics API
    query shape against the Langfuse docs at build time — this is the fallback, embed is primary."""
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        return {"available": False, "reason": "no Langfuse keys configured"}
    token = base64.b64encode(
        f"{settings.langfuse_public_key}:{settings.langfuse_secret_key}".encode()
    ).decode()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{settings.langfuse_base_url}/api/public/metrics/daily",
                headers={"Authorization": f"Basic {token}"},
            )
            resp.raise_for_status()
            return {"available": True, "data": resp.json()}
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "reason": str(exc)}
