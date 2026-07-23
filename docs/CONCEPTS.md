# Concept → code map

One page for reviewers: where each required concept actually lives in the codebase, its greppable
**signpost** banner, and which phase built it. Cross-reference with `tasks/todo.md` for the
verification note behind each phase. See `backend/app/README.md` for the folder=concept overview.

Domain reminder: this agent triages **Stripe payments support tickets**, grounded in real Stripe
documentation (see the README's "Domain" section) — the concepts below are demonstrated *through*
that concrete product, not in the abstract.

## Concept modules

| Concept | Where in code | Signpost | Phase |
|---|---|---|---|
| Orchestration without a framework | `backend/app/agents/orchestrator.py` — `_run_pipeline()`/`triage()`: hand-rolled classify→retrieve→resolve→critique→revision. No LangChain/CrewAI/LangGraph. | `── Concept: ORCHESTRATION (FRAMEWORK-FREE) ──` | 4 |
| RAG (retrieval-augmented generation) | `backend/app/rag/fetch.py` (HTTP+markdownify), `chunking.py`, `ingest.py` (pipeline), `embeddings.py` (TEI client), `seed_data.py` (synthetic KB). | `── Concept: RAG ──` | 1 |
| Lexical + semantic search in Postgres/pgvector | `backend/app/rag/search.py` — `lexical_search()` (`tsvector`/`ts_rank`), `semantic_search()` (`vector` cosine), `hybrid_search()` (RRF). Schema: `backend/app/schema.sql` (`chunks.embedding vector(384)`, generated `fts tsvector`, GIN + HNSW). | `── Concept: LEXICAL + SEMANTIC SEARCH (PGVECTOR) ──` | 1 |
| Tools (function calling) | `backend/app/tools/registry.py` — JSON schemas + dispatcher for `hybrid_search`/`get_document`/`get_ticket`/`escalate`; `backend/app/agents/loop.py` — the tool-use loop. | `── Concept: TOOLS (FUNCTION CALLING) ──` / `── Concept: TOOLS (THE HAND-ROLLED LOOP) ──` | 3 |
| MCP (Model Context Protocol) | `backend/app/mcp/server.py` (FastMCP, Streamable HTTP `:9000/mcp`, its own compose service) exposes the same tools; `backend/app/mcp/client.py` consumes them into the neutral `ToolSpec`/dispatch. `POST /agent/answer-mcp`. | `── Concept: MCP (SERVER) ──` / `── Concept: MCP (CLIENT) ──` | 5 |
| Skills | `backend/app/skills/loader.py` (filesystem `SKILL.md` loader, progressive disclosure) + `backend/app/skills/definitions/policy-reply-formatter/SKILL.md`; injected into `_resolve()`'s system prompt only when drafting a reply. | `── Concept: SKILLS ──` | 5 |
| LLM API + provider abstraction | `backend/app/llm/base.py` (neutral `LLMProvider`/`Message`/`ToolSpec`/`Usage`/`LLMResponse`), `gemini.py`, `factory.py` (`get_provider()` on `LLM_PROVIDER`). Swapping to Claude = write `anthropic.py` + one env var. | `── Concept: LLM API + PROVIDER ABSTRACTION ──` | 2 |
| Observability (spans, traces, cost) | `backend/app/observability.py` — `Trace`/`span()` via `contextvars`; `backend/app/api/traces.py` (`GET /traces`, `GET /traces/{id}` nested tree); `cost_usd()` from `settings.model_costs`. | `── Concept: OBSERVABILITY ──` | 6 |
| Evals (golden set, deterministic + LLM-as-judge) | `backend/app/evals/golden.json` (20 cases), `metrics.py`, `judge.py`, `runner.py` (`run_eval()`), `backend/app/api/evals.py`. | `── Concept: EVALS ──` | 7 |

## Cross-cutting techniques (a named home + a signpost, not a folder)

| Technique | File + symbol | Signpost | Phase |
|---|---|---|---|
| Context management with subagents | `agents/orchestrator.py` — `_classify()/_plan()/_retrieve()/_resolve()/_critique()`: each a fresh, isolated LLM call (`[user(msg)]` only); only a compact dict/string returns, so the orchestrator never accumulates a growing transcript. | `── Concept: CONTEXT MANAGEMENT (SUBAGENTS) ──` | 4 |
| Parallelism | `agents/orchestrator.py` — `asyncio.gather(_classify_emit(), _plan_emit())` and `asyncio.gather(*[_retrieve_emit(i, q) ...])`; overlap provable on real span timestamps, and live via `triage_events()`'s `asyncio.Queue` fan-in. | `── Concept: PARALLELISM ──` | 4, 8 |
| Retry / backoff | `llm/retry.py` — `with_retry()`: exponential backoff + jitter on 429/5xx/timeouts; parses Gemini's `RetryInfo.retryDelay`. `POST /llm/retry-demo`. | `── Concept: RETRY / BACKOFF ──` | 2 |
| Prompt caching | `llm/base.py` `Usage.cached_tokens`, surfaced through spans (`cache_read_tokens`) and `/traces` `cache_hit_pct`; honest 0% on Gemini free tier — plumbing is provider-neutral. `POST /llm/cache-demo`. | `── Concept: PROMPT CACHING ──` | 2 |

## Also demonstrated (UI / UX)

| Concept | Where in code | Phase |
|---|---|---|
| Streaming UX for agents | `orchestrator.py` — `triage_events()` (async generator, real per-phase events); `backend/app/api/agent.py` — `POST /agent/triage/stream` (SSE, `data: ...\n\n` + `[DONE]`); `frontend/src/lib/sse.ts`. | 8 |
| Making agent internals legible (UI) | `frontend/src/components/SpanWaterfall.tsx` (one Gantt reused for the live SSE timeline and the retrospective trace detail — see `frontend/src/lib/waterfall.ts`); `frontend/src/pages/{Triage,Observability,Evals}Page.tsx`. Design from `ui-ux-pro-max` + `dataviz` skills. | 8 |
