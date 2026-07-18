# 02 — RAG: ingest & hybrid search (Phase 1)

## Purpose
Turn crawled Stripe docs + synthetic past tickets into a searchable corpus, and expose **lexical**,
**semantic**, and **hybrid** search over Postgres/pgvector.

## Ingest pipeline
```
Crawl4AI (url → markdown)
        └─▶ RecursiveCharacterTextSplitter (md → chunks, ~800 chars / 100 overlap)
                └─▶ TEI (chunk text → 384-dim vector)
                        └─▶ Postgres: store chunk text, embedding (vector), tsvector (FTS)
```
- Crawl targets: a small allowlist of Stripe docs URLs (billing/refunds/subscriptions/disputes). Respect `robots.txt`; keep to a handful of pages for the POC.
- Synthetic past tickets: ~30 resolved tickets generated once (subject, body, resolution, category), ingested the same way (their `resolution` text is what's retrieved as precedent).

## Data model (DDL sketch)
```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE documents (          -- a crawled page or a past ticket
  id           BIGSERIAL PRIMARY KEY,
  source_type  TEXT NOT NULL,     -- 'kb' | 'ticket'
  url          TEXT,              -- for kb
  title        TEXT,
  category     TEXT,              -- for tickets: refund/dispute/...
  created_at   TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE chunks (
  id          BIGSERIAL PRIMARY KEY,
  document_id BIGINT REFERENCES documents(id) ON DELETE CASCADE,
  ordinal     INT NOT NULL,
  content     TEXT NOT NULL,
  embedding   vector(384) NOT NULL,
  fts         tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED
);

CREATE INDEX chunks_fts_idx  ON chunks USING GIN (fts);
CREATE INDEX chunks_vec_idx  ON chunks USING hnsw (embedding vector_cosine_ops);
```

## Search contract (Python)
```python
async def lexical_search(q: str, k: int) -> list[Hit]     # ts_rank over fts
async def semantic_search(q: str, k: int) -> list[Hit]    # embedding <=> query_vec (cosine)
async def hybrid_search(q: str, k: int) -> list[Hit]      # RRF fusion of the two
# Hit = {chunk_id, document_id, title, url, content, score, source_type}
```

### Reciprocal Rank Fusion (RRF)
For each result list, score = Σ 1 / (rrf_k + rank), with `rrf_k = 60` (standard). Merge by chunk_id, sum scores, sort desc. ~10 lines of Python; no ML needed.

```
score(chunk) = 1/(60 + rank_lexical) + 1/(60 + rank_semantic)
```

## Behavior / acceptance
- [ ] `POST /ingest` crawls the allowlist + loads synthetic tickets, prints counts (docs, chunks).
- [ ] Query `"duplicate charge refund"` returns sensible chunks for lexical, semantic, and hybrid.
- [ ] A **comparison endpoint/script** shows the three rankings side by side (proves hybrid ≠ either alone).
- [ ] Semantic finds a paraphrase (e.g. "billed twice") that lexical misses; hybrid keeps both.

## 🎓 Teaching notes
- `tsvector`/`to_tsvector('english', ...)` tokenizes + stems words for fast keyword search via a GIN index.
- `<=>` is pgvector's cosine-distance operator; `ORDER BY embedding <=> $1 LIMIT k` is a nearest-neighbor query (HNSW index makes it fast).
- Why RRF over score-averaging: lexical and cosine scores live on different scales; RRF only uses **rank position**, so no fragile normalization.
- Chunk size trade-off: smaller chunks = more precise retrieval but more rows + risk of losing context; ~800/100 is a sane POC default.

## Open questions
- Exact Crawl4AI request/response shape (endpoint, markdown field) — confirm against the running container in Phase 1.
