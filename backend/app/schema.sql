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

-- Phase 6 schema: one trace per agent/triage run, with a nested span tree per run.
-- See app/observability.py for the writer; runs idempotently on startup like the tables above.
CREATE TABLE IF NOT EXISTS traces (
    id             BIGSERIAL PRIMARY KEY,
    name           TEXT        NOT NULL,       -- 'triage' | 'eval' | 'agent'
    ticket_id      BIGINT,
    started_at     TIMESTAMPTZ NOT NULL,
    ended_at       TIMESTAMPTZ NOT NULL,
    status         TEXT        NOT NULL,        -- 'ok' | 'error'
    total_tokens   INT         NOT NULL DEFAULT 0,
    total_cost_usd NUMERIC     NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS spans (
    id                    BIGSERIAL PRIMARY KEY,
    trace_id              BIGINT REFERENCES traces(id) ON DELETE CASCADE,
    parent_id             BIGINT REFERENCES spans(id) ON DELETE CASCADE,
    name                  TEXT        NOT NULL,   -- 'orchestrator' | 'classifier' | 'retriever' | 'tool:hybrid_search' | ...
    span_type             TEXT        NOT NULL,   -- agent | subagent | tool | llm_call
    model                 TEXT,
    started_at            TIMESTAMPTZ NOT NULL,
    ended_at              TIMESTAMPTZ NOT NULL,
    input_tokens          INT         NOT NULL DEFAULT 0,
    output_tokens         INT         NOT NULL DEFAULT 0,
    cache_read_tokens     INT         NOT NULL DEFAULT 0,
    cache_creation_tokens INT         NOT NULL DEFAULT 0,
    retries               INT         NOT NULL DEFAULT 0,
    error                 TEXT
);

CREATE INDEX IF NOT EXISTS spans_trace_idx  ON spans (trace_id);
CREATE INDEX IF NOT EXISTS spans_parent_idx ON spans (parent_id);

-- Ticket history: one row per SUCCESSFUL triage run, linking the submitted ticket + final
-- reply to its already-persisted trace (spans = the timeline). Scoped per anonymous session_id.
-- Runs idempotently on startup like the tables above.
CREATE TABLE IF NOT EXISTS tickets (
    id           BIGSERIAL   PRIMARY KEY,
    session_id   TEXT        NOT NULL,
    ticket_text  TEXT        NOT NULL,
    category     TEXT,                                  -- from classification, for the sidebar chip
    final_reply  TEXT        NOT NULL,                  -- denormalized for list preview
    result       JSONB       NOT NULL,                  -- full TriageResult → restores the final-reply view
    trace_id     BIGINT      REFERENCES traces(id) ON DELETE SET NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS tickets_session_created_idx ON tickets (session_id, created_at DESC);

-- Phase 7 schema: one eval_runs row per `POST /evals/run`, one eval_cases row per golden-set case.
-- See app/evals/runner.py for the writer.
CREATE TABLE IF NOT EXISTS eval_runs (
    id                       BIGSERIAL PRIMARY KEY,
    started_at               TIMESTAMPTZ NOT NULL,
    ended_at                 TIMESTAMPTZ NOT NULL,
    retrieval_mode           TEXT        NOT NULL,   -- 'lexical' | 'semantic' | 'hybrid'
    n_cases                  INT         NOT NULL,
    classification_accuracy  NUMERIC,
    priority_accuracy        NUMERIC,
    retrieval_hit_rate       NUMERIC,
    citation_coverage        NUMERIC,
    faithfulness_avg         NUMERIC,
    helpfulness_avg          NUMERIC,
    total_cost_usd           NUMERIC
);

CREATE TABLE IF NOT EXISTS eval_cases (
    id                    BIGSERIAL PRIMARY KEY,
    run_id                BIGINT REFERENCES eval_runs(id) ON DELETE CASCADE,
    golden_id             TEXT NOT NULL,
    ticket                TEXT NOT NULL,
    trace_id              BIGINT REFERENCES traces(id),
    predicted_category    TEXT,
    expected_category     TEXT,
    category_correct      BOOLEAN,
    predicted_priority    TEXT,
    expected_priority     TEXT,
    priority_correct      BOOLEAN,
    retrieval_hit         BOOLEAN,
    citation_coverage     NUMERIC,
    faithfulness_score    NUMERIC,
    faithfulness_reasoning TEXT,
    helpfulness_score     NUMERIC,
    helpfulness_reasoning TEXT,
    final_reply           TEXT
);

CREATE INDEX IF NOT EXISTS eval_cases_run_idx ON eval_cases (run_id);

-- Phase C schema: human-in-the-loop escalation approvals. The escalate TOOL writes NOTHING;
-- a row appears here ONLY when a human approves (or rejects) a proposal via the API. Runs
-- idempotently on startup like the tables above.
CREATE TABLE IF NOT EXISTS escalations (
    id          BIGSERIAL   PRIMARY KEY,
    handle      TEXT        UNIQUE NOT NULL,        -- proposal handle from the escalate tool (ESC-xxxx)
    ticket_ref  TEXT,                                -- external ticket id / free-text ref, if any
    ticket_id   BIGINT      REFERENCES tickets(id) ON DELETE SET NULL,  -- links to a saved run, if any
    reason      TEXT        NOT NULL,
    severity    TEXT        NOT NULL,                -- low | medium | high
    status      TEXT        NOT NULL,                -- approved | rejected
    assignee    TEXT,                                -- queue/agent handle set at approval
    decided_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS escalations_status_idx ON escalations (status, decided_at DESC);

-- The ticket-status write half of the gate: applied to a saved ticket when an escalation is approved.
ALTER TABLE tickets ADD COLUMN IF NOT EXISTS status   TEXT;   -- e.g. 'escalated'
ALTER TABLE tickets ADD COLUMN IF NOT EXISTS assignee TEXT;   -- queue/agent handle

-- Phase D: link each Postgres trace to its mirrored Langfuse trace (deep-link + score target).
ALTER TABLE traces ADD COLUMN IF NOT EXISTS langfuse_trace_id TEXT;
ALTER TABLE traces ADD COLUMN IF NOT EXISTS langfuse_url      TEXT;

-- Phase D evals depth: failure taxonomy per case + regression gate per run.
ALTER TABLE eval_cases ADD COLUMN IF NOT EXISTS failure_labels    JSONB;
ALTER TABLE eval_runs  ADD COLUMN IF NOT EXISTS failure_breakdown JSONB;
ALTER TABLE eval_runs  ADD COLUMN IF NOT EXISTS regression        BOOLEAN;
ALTER TABLE eval_runs  ADD COLUMN IF NOT EXISTS baseline_run_id   BIGINT;
