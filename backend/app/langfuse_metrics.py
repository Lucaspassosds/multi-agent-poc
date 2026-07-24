"""Langfuse Metrics API v2 client — replaces the deprecated /api/public/metrics/daily
fallback in api/observability.py. Builds the 4 canned chart queries, calls the real v2
endpoint, and normalizes Langfuse's row shape into a chart-agnostic series format so the
frontend never has to touch Langfuse's field-naming quirks.

Verified against a live call to this project's Langfuse Cloud instance (2026-07-24) before
writing the parser below:
- Envelope: {"data": [{"time_dimension": "YYYY-MM-DD", "<agg>_<measure>": value, ...}, ...]}.
- The v2 "count" aggregation comes back as a STRING ("0", "32") while sum/avg/percentiles
  come back as numbers or null — _num() coerces both.
- A day with no observations returns null for sum/percentile metrics (not 0); we zero-fill
  count/cost (no activity that day IS zero) but leave latency/scores sparse (no measurement
  that day is not the same as a measured zero).
- A dimensioned query (scores by name) with no matching rows still returns one filler row per
  day carrying an empty-string group value — dropped, it is not a real series.
- Latency values are in milliseconds; the rest of this app displays seconds, so latency is
  scaled by 0.001 here.
"""
from __future__ import annotations

import base64
import json
import time
import urllib.parse
from typing import Any

import httpx

from app.config import settings

CHARTS = ("observations", "cost", "latency", "scores")

_CACHE_TTL_SECONDS = 60.0
_cache: dict[tuple[str, str, str, str], tuple[float, dict[str, Any]]] = {}


def _auth_headers() -> dict[str, str]:
    token = base64.b64encode(
        f"{settings.langfuse_public_key}:{settings.langfuse_secret_key}".encode()
    ).decode()
    return {"Authorization": f"Basic {token}"}


def _build_query(chart: str, granularity: str, from_ts: str, to_ts: str) -> dict[str, Any]:
    base = {
        "filters": [],
        "timeDimension": {"granularity": granularity},
        "fromTimestamp": from_ts,
        "toTimestamp": to_ts,
    }
    if chart == "observations":
        return {**base, "view": "observations", "dimensions": [],
                "metrics": [{"measure": "count", "aggregation": "count"}]}
    if chart == "cost":
        return {**base, "view": "observations", "dimensions": [],
                "metrics": [{"measure": "totalCost", "aggregation": "sum"}]}
    if chart == "latency":
        return {**base, "view": "observations", "dimensions": [],
                "metrics": [
                    {"measure": "latency", "aggregation": "p50"},
                    {"measure": "latency", "aggregation": "p95"},
                    {"measure": "latency", "aggregation": "p99"},
                ]}
    if chart == "scores":
        return {**base, "view": "scores-numeric", "dimensions": [{"field": "name"}],
                "metrics": [{"measure": "value", "aggregation": "avg"}]}
    raise ValueError(f"unknown chart {chart!r}")


def _num(v: Any) -> float | None:
    """Langfuse returns some aggregates as strings, others as numbers, and null for no-data days."""
    return None if v is None else float(v)


def _zero_fill_series(label: str, rows: list[dict], key: str) -> dict[str, Any]:
    """No activity that day IS zero — used for observation count and total cost."""
    return {"label": label, "points": [{"t": r["time_dimension"], "v": _num(r.get(key)) or 0.0} for r in rows]}


def _sparse_series(label: str, rows: list[dict], key: str, scale: float = 1.0) -> dict[str, Any]:
    """No measurement that day is NOT a measured zero — used for latency and scores."""
    points = []
    for r in rows:
        v = _num(r.get(key))
        if v is not None:
            points.append({"t": r["time_dimension"], "v": v * scale})
    return {"label": label, "points": points}


def _normalize(chart: str, rows: list[dict]) -> list[dict[str, Any]]:
    if chart == "observations":
        return [_zero_fill_series("observations", rows, "count_count")]
    if chart == "cost":
        return [_zero_fill_series("total cost (USD)", rows, "sum_totalCost")]
    if chart == "latency":
        return [
            _sparse_series("p50", rows, "p50_latency", scale=0.001),
            _sparse_series("p95", rows, "p95_latency", scale=0.001),
            _sparse_series("p99", rows, "p99_latency", scale=0.001),
        ]
    if chart == "scores":
        by_name: dict[str, list[dict]] = {}
        for r in rows:
            name = r.get("name") or ""
            if not name:
                continue  # Langfuse's "no group matched that day" filler row — not a real series.
            by_name.setdefault(name, []).append(r)
        return [_sparse_series(name, group_rows, "avg_value") for name, group_rows in sorted(by_name.items())]
    raise ValueError(f"unknown chart {chart!r}")


async def query(chart: str, granularity: str, from_ts: str, to_ts: str) -> dict[str, Any]:
    """Fetch + normalize one chart's series. Fails soft: any error or missing config
    returns {"available": False, "reason": ...} rather than raising, matching every
    other optional-affordance consumer in this app."""
    if chart not in CHARTS:
        raise ValueError(f"unknown chart {chart!r}")
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        return {"available": False, "reason": "no Langfuse keys configured"}

    cache_key = (chart, granularity, from_ts, to_ts)
    now = time.monotonic()
    cached = _cache.get(cache_key)
    if cached and now - cached[0] < _CACHE_TTL_SECONDS:
        return {**cached[1], "cached": True}

    q = _build_query(chart, granularity, from_ts, to_ts)
    url = f"{settings.langfuse_base_url}/api/public/v2/metrics?query=" + urllib.parse.quote(json.dumps(q))
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, headers=_auth_headers())
            resp.raise_for_status()
            rows = resp.json().get("data", [])
    except Exception as exc:  # noqa: BLE001 - a chart failure must never break the page
        return {"available": False, "reason": str(exc)}

    result = {"available": True, "chart": chart, "granularity": granularity, "series": _normalize(chart, rows)}
    _cache[cache_key] = (now, result)
    return {**result, "cached": False}
