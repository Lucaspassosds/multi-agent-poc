-- Phase 1 schema: documents + their embedded/searchable chunks.
-- Runs idempotently on startup (see app/db.py:init_schema).

CREATE EXTENSION IF NOT EXISTS vector;

-- A source unit of knowledge: a KB article OR a past resolved ticket.
CREATE TABLE IF NOT EXISTS documents (
    id          BIGSERIAL PRIMARY KEY,
    source_type TEXT        NOT NULL,               -- 'kb' | 'ticket'
    external_id TEXT,                                -- ticket id / url slug (for dedupe + get_* tools)
    title       TEXT,
    url         TEXT,
    content     TEXT        NOT NULL,
    metadata    JSONB       NOT NULL DEFAULT '{}',  -- e.g. ticket resolution/category/priority
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Chunks are what we actually search: each has BOTH a vector (semantic)
-- and a generated tsvector (lexical) column — hybrid search reads both.
CREATE TABLE IF NOT EXISTS chunks (
    id          BIGSERIAL PRIMARY KEY,
    document_id BIGINT      NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    ordinal     INT         NOT NULL,
    content     TEXT        NOT NULL,
    embedding   VECTOR(384) NOT NULL,
    fts         TSVECTOR    GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- GIN index → fast lexical (full-text) search; HNSW index → fast approx. nearest-neighbour vector search.
CREATE INDEX IF NOT EXISTS chunks_fts_idx       ON chunks USING GIN  (fts);
CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops);
