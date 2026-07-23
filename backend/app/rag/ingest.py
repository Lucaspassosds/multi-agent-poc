"""Ingest pipeline: (fetch | synthetic) -> chunk -> embed -> store.

Populates `documents` + `chunks`. Flow (spec 02):
HTTP fetch (url->md) -> RecursiveCharacterTextSplitter (md->chunks) -> TEI (chunk->vector) -> Postgres.
"""
# ── Concept: RAG ── ingest pipeline: (fetch | synthetic) → chunk → embed → store into pgvector.
import json

from app.db import get_pool
from app.embeddings import embed
from app.rag.chunking import chunk_markdown
from app.rag.fetch import fetch_to_markdown
from app.seed_data import KB_ARTICLES, PAST_TICKETS

# Real English doc pages fetched via HTTP (server-rendered; Accept-Language=en-US → English).
FETCH_URLS = [
    # Stripe payments docs (English requires a US egress; see rag/fetch.py note)
    "https://docs.stripe.com/refunds",
    "https://docs.stripe.com/disputes",
    "https://docs.stripe.com/billing/subscriptions/cancel",
    "https://docs.stripe.com/payments/3d-secure",
    # English Wikipedia payment topics
    "https://en.wikipedia.org/wiki/Chargeback",
    "https://en.wikipedia.org/wiki/3-D_Secure",
    "https://en.wikipedia.org/wiki/Credit_card_fraud",
    "https://en.wikipedia.org/wiki/Payment_Card_Industry_Data_Security_Standard",
]


async def _store_document(conn, *, source_type, external_id, title, url, content, metadata) -> int:
    doc_id = await conn.fetchval(
        """INSERT INTO documents (source_type, external_id, title, url, content, metadata)
           VALUES ($1, $2, $3, $4, $5, $6::jsonb) RETURNING id""",
        source_type, external_id, title, url, content, json.dumps(metadata),
    )
    chunks = chunk_markdown(content)
    if not chunks:
        return 0
    vectors = await embed(chunks)
    await conn.executemany(
        "INSERT INTO chunks (document_id, ordinal, content, embedding) VALUES ($1, $2, $3, $4)",
        [(doc_id, i, c, v) for i, (c, v) in enumerate(zip(chunks, vectors))],
    )
    return len(chunks)


async def ingest_all(*, reset: bool = True, do_fetch: bool = True) -> dict:
    pool = await get_pool()
    counts = {"fetched_kb": 0, "synthetic_kb": 0, "tickets": 0, "chunks": 0, "fetch_error": None}

    async with pool.acquire() as conn:
        if reset:
            await conn.execute("TRUNCATE documents RESTART IDENTITY CASCADE")

        # 1) Fetched KB (HTTP). Non-fatal if a page is unreachable.
        if do_fetch:
            try:
                for d in await fetch_to_markdown(FETCH_URLS):
                    n = await _store_document(
                        conn, source_type="kb", external_id=d["url"], title=d["title"],
                        url=d["url"], content=d["markdown"], metadata={"origin": "fetch"},
                    )
                    counts["fetched_kb"] += 1
                    counts["chunks"] += n
            except Exception as e:  # network unreachable -> keep going with synthetic
                counts["fetch_error"] = repr(e)

        # 2) Synthetic KB articles
        for a in KB_ARTICLES:
            n = await _store_document(
                conn, source_type="kb", external_id=a["external_id"], title=a["title"],
                url=None, content=a["content"], metadata={"origin": "synthetic"},
            )
            counts["synthetic_kb"] += 1
            counts["chunks"] += n

        # 3) Past resolved tickets (precedent)
        for t in PAST_TICKETS:
            content = f"Subject: {t['subject']}\n\n{t['body']}\n\nResolution: {t['resolution']}"
            n = await _store_document(
                conn, source_type="ticket", external_id=t["external_id"], title=t["subject"],
                url=None, content=content,
                metadata={"category": t["category"], "priority": t["priority"], "resolution": t["resolution"]},
            )
            counts["tickets"] += 1
            counts["chunks"] += n

    return counts
