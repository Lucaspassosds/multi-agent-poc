# 06 — Observability (Phase 6)

## Purpose
Make the agent's internals legible: every step, its latency, tokens, cost, cache hits, and retries —
stored and shown in a dashboard. (topic: "observabilidade".)

## 🎓 Concepts
- **Trace** = one triage run. **Span** = one step within it (an agent turn, a tool call, a subagent).
- Spans nest (orchestrator → retriever → tool call), forming a tree with timings — the same model as
  OpenTelemetry, kept deliberately simple here.

## Data model (Postgres)
```sql
CREATE TABLE traces (
  id          BIGSERIAL PRIMARY KEY,
  ticket_id   BIGINT,
  started_at  TIMESTAMPTZ, ended_at TIMESTAMPTZ,
  status      TEXT,                        -- ok | error
  total_tokens INT, total_cost_usd NUMERIC
);
CREATE TABLE spans (
  id          BIGSERIAL PRIMARY KEY,
  trace_id    BIGINT REFERENCES traces(id) ON DELETE CASCADE,
  parent_id   BIGINT REFERENCES spans(id),
  name        TEXT,        -- 'orchestrator' | 'classifier' | 'retriever' | 'tool:hybrid_search' | ...
  span_type   TEXT,        -- agent | subagent | tool | llm_call
  model       TEXT,
  started_at  TIMESTAMPTZ, ended_at TIMESTAMPTZ,
  input_tokens INT, output_tokens INT,
  cache_read_tokens INT, cache_creation_tokens INT,
  retries     INT DEFAULT 0,
  error       TEXT
);
```

## Instrumentation
- A small context-manager / decorator (`with span("retriever", parent=...)`) that records timing and,
  for LLM calls, pulls `response.usage` (input/output/cache tokens) and computes cost from the per-model
  rates in config.
- No external APM — a custom span writer is enough for a POC and keeps the concept visible. (Optionally
  emit OpenTelemetry-compatible spans as a stretch goal.)

## API
- `GET /traces` — list (id, ticket, status, tokens, cost, duration).
- `GET /traces/{id}` — full span tree for the timeline view.

## Dashboard (React — built in Phase 8)
- Timeline / waterfall of spans (shows parallelism visually).
- Per-run totals: tokens, **cost**, **cache-hit %**, retry count, wall-clock.
- Drill into a span: model, prompt/response token split, errors.

## Behavior / acceptance
- [ ] A triage run produces a complete, inspectable trace with a nested span tree.
- [ ] Parallel retrievers visibly overlap on the timeline.
- [ ] Cache-hit % and cost per run are shown and match `usage` fields.

## Open questions
- Cost table lives in config (per-model $/Mtok) — keep in sync with `specs/03`. Acceptable for a POC.
