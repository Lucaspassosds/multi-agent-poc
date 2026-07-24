"""Search — lexical, semantic, and hybrid (RRF) over the `chunks` table.

- Lexical  : Postgres full-text (`ts_rank` over the generated tsvector). Great for exact
             terms, IDs, error codes — but blind to synonyms/paraphrase.
- Semantic : pgvector cosine distance (`<=>`) over embeddings. Understands meaning, so it
             matches paraphrases — but can drift on rare literal tokens.
- Hybrid   : run both, then fuse the two ranked lists with Reciprocal Rank Fusion (RRF):
             score(doc) = Σ 1 / (k + rank_in_list). Rank-based, so it needs no score
             normalization between the two very different scales. Best of both worlds.
"""
# ── Concept: LEXICAL + SEMANTIC SEARCH (PGVECTOR) ── tsvector lexical + vector cosine, fused with Reciprocal Rank Fusion in hybrid_search().
import asyncio

from app.db import get_pool
from app.rag.embeddings import embed_one

_SELECT = """
    SELECT c.id, c.document_id, c.ordinal, c.content,
           d.title, d.url, d.source_type, d.external_id
"""


async def lexical_search(query: str, k: int = 10) -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch(
        f"""
        {_SELECT}, ts_rank(c.fts, plainto_tsquery('english', $1)) AS score
        FROM chunks c JOIN documents d ON d.id = c.document_id
        WHERE c.fts @@ plainto_tsquery('english', $1)
        ORDER BY score DESC
        LIMIT $2
        """,
        query,
        k,
    )
    return [dict(r) for r in rows]


async def semantic_search(query: str, k: int = 10) -> list[dict]:
    qv = await embed_one(query)
    pool = await get_pool()
    rows = await pool.fetch(
        f"""
        {_SELECT}, 1 - (c.embedding <=> $1) AS score
        FROM chunks c JOIN documents d ON d.id = c.document_id
        ORDER BY c.embedding <=> $1
        LIMIT $2
        """,
        qv,
        k,
    )
    return [dict(r) for r in rows]


async def hybrid_search(query: str, k: int = 10, rrf_k: int = 60, candidate_pool_size: int = 20,
                        *, detailed: bool = False) -> list[dict]:
    # Pull a wider candidate pool from each retriever, then fuse down to k — RRF needs depth to rank.
    # Run both retrievals concurrently — a first taste of the parallelism theme.
    lex, sem = await asyncio.gather(
        lexical_search(query, candidate_pool_size),
        semantic_search(query, candidate_pool_size),
    )

    scores: dict[int, float] = {}
    meta: dict[int, dict] = {}
    lex_score: dict[int, float] = {}
    sem_score: dict[int, float] = {}
    for source, ranked in (("lexical", lex), ("semantic", sem)):
        for rank, row in enumerate(ranked):
            cid = row["id"]
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (rrf_k + rank + 1)
            meta[cid] = row
            (lex_score if source == "lexical" else sem_score)[cid] = row["score"]

    top = sorted(scores, key=lambda cid: scores[cid], reverse=True)[:k]
    out: list[dict] = []
    for cid in top:
        row = {**meta[cid], "score": round(scores[cid], 6)}
        if detailed:
            # Component contributions per source (None if that source didn't surface this chunk).
            row["lexical_score"] = round(lex_score[cid], 6) if cid in lex_score else None
            row["semantic_score"] = round(sem_score[cid], 6) if cid in sem_score else None
        out.append(row)
    return out


# The single source of truth for retrieval-mode dispatch, shared by the HTTP /search endpoint
# (main.py) and the retriever subagents (orchestrator.py). A new mode is added in exactly one
# place. Defaulting a retriever to "lexical"/"semantic" lets the Phase 7 evals demonstrate a
# deliberate regression (hybrid is strictly better) without duplicating the orchestrator flow.
SEARCH_FNS = {
    "lexical": lexical_search,
    "semantic": semantic_search,
    "hybrid": hybrid_search,
}
