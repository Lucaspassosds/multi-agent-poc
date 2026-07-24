"""FastAPI entrypoint.

Phase 0: GET /health (probes Postgres + the embedding service).
Phase 1: POST /ingest (build the knowledge base) and GET /search (lexical/semantic/hybrid).
"""
from contextlib import asynccontextmanager

import asyncpg
import httpx
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from app.api.agent import router as agent_router
from app.api.escalations import router as escalations_router
from app.api.evals import router as evals_router
from app.api.llm import router as llm_router
from app.api.observability import router as observability_router
from app.api.tickets import router as tickets_router
from app.api.traces import router as traces_router
from app.config import settings
from app.db import close_pool, get_pool, init_schema
from app import langfuse_client
from app.rag import search as search_mod
from app.rag.ingest import ingest_all


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure the schema exists, then warm the connection pool (with the pgvector codec).
    await init_schema()
    await get_pool()
    langfuse_client.init()          # auth-check once; stays disabled on failure
    yield
    langfuse_client.flush()         # drain any buffered events before shutdown
    await close_pool()


app = FastAPI(
    title="Multi-Agent Support Triage POC",
    description=(
        "A framework-free multi-agent system that triages Stripe payments support tickets — "
        "refunds, disputes, failed charges, subscription billing — and drafts cited resolutions "
        "grounded in real Stripe documentation."
    ),
    lifespan=lifespan,
)

# Allow the Vite dev server (Phase 8 UI) to call the API from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(llm_router)
app.include_router(agent_router)
app.include_router(traces_router)
app.include_router(tickets_router)
app.include_router(evals_router)
app.include_router(escalations_router)
app.include_router(observability_router)


async def _check_db() -> bool:
    try:
        conn = await asyncpg.connect(settings.database_url, timeout=3)
        try:
            await conn.execute("SELECT 1")
        finally:
            await conn.close()
        return True
    except Exception:
        return False


async def _check_tei() -> bool:
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get(f"{settings.tei_url}/health")
            return resp.status_code == 200
    except Exception:
        return False


@app.get("/health")
async def health():
    db_ok = await _check_db()
    tei_ok = await _check_tei()
    return {
        "status": "ok" if (db_ok and tei_ok) else "degraded",
        "db": db_ok,
        "tei": tei_ok,
        "provider": settings.llm_provider,
    }


@app.post("/ingest")
async def ingest(fetch: bool = Query(True), reset: bool = Query(True)):
    """Build the knowledge base. `fetch=false` skips HTTP fetch (uses only synthetic data)."""
    return await ingest_all(reset=reset, do_fetch=fetch)


def _trim(rows: list[dict], preview: int = 240) -> list[dict]:
    out = []
    for r in rows:
        out.append({
            "chunk_id": r["id"],
            "document_id": r["document_id"],
            "source_type": r["source_type"],
            "title": r["title"],
            "url": r["url"],
            "score": r["score"],
            "preview": (r["content"][:preview] + "…") if len(r["content"]) > preview else r["content"],
        })
    return out


@app.get("/search")
async def search(
    q: str = Query(..., min_length=1),
    mode: str = Query("hybrid", pattern="^(lexical|semantic|hybrid)$"),
    k: int = Query(5, ge=1, le=25),
):
    fn = search_mod.SEARCH_FNS[mode]
    rows = await fn(q, k)
    return {"mode": mode, "query": q, "results": _trim(rows)}
