# Concept → code map

One page for reviewers: where each required concept actually lives in the codebase, and which
phase built it. Cross-reference with `tasks/todo.md` for the verification note behind each phase.

Domain reminder: this agent triages **Stripe payments support tickets**, grounded in real Stripe
documentation (see the README's "Domain" section) — the concepts below are demonstrated *through*
that concrete product, not in the abstract.

| Concept | Where in code | Phase |
|---|---|---|
| Orchestration without a framework *(orquestração sem framework)* | `backend/app/agents/orchestrator.py` — `_run_pipeline()`/`triage()`: hand-rolled classify→retrieve→resolve→critique→revision flow. No LangChain/CrewAI/LangGraph. | 4 |
| Context management with subagents *(gestão de contexto)* | Same file — `_classify()`, `_plan()`, `_retrieve()`, `_resolve()`, `_critique()`: each is a fresh, isolated LLM call (`[user(msg)]` only); only a compact dict/string returns to the orchestrator, which never accumulates a growing transcript. | 4 |
| Parallelism | `orchestrator.py` — `asyncio.gather(_classify_emit(), _plan_emit())` and `asyncio.gather(*[_retrieve_emit(i, q) ...])`; proven on real timestamps (not just logs) via `Trace`/`span()` overlap, and again live via `triage_events()`'s `asyncio.Queue` fan-in from concurrently-running phases. | 4, 8 |
| RAG (retrieval-augmented generation) | `backend/app/rag/fetch.py` (HTTP+markdownify), `chunking.py` (RecursiveCharacterTextSplitter), `ingest.py` (pipeline), `embeddings.py` (TEI client). | 1 |
| Lexical + semantic search in Postgres/pgvector | `backend/app/rag/search.py` — `lexical_search()` (`tsvector`/`ts_rank`), `semantic_search()` (`vector` cosine via pgvector), `hybrid_search()` (Reciprocal Rank Fusion of both). Schema: `backend/app/schema.sql` (`chunks.embedding vector(384)`, generated `fts tsvector`, GIN + HNSW indexes). | 1 |
| Tools (function calling) | `backend/app/agents/tools.py` — JSON schemas + dispatcher for `hybrid_search`/`get_document`/`get_ticket`/`escalate`; `backend/app/agents/loop.py` — the tool-use loop (call → tool_use → execute → feed back → final). | 3 |
| MCP (Model Context Protocol) | `backend/app/mcp_server.py` (FastMCP, Streamable HTTP `:9000/mcp`, its own compose service) exposes the same tools; `backend/app/mcp_client.py` consumes them over the protocol into the same neutral `ToolSpec`/dispatch the tool loop already uses. `POST /agent/answer-mcp`. | 5 |
| Skills | `backend/app/skills.py` (filesystem `SKILL.md` loader, progressive disclosure) + `backend/app/skills/policy-reply-formatter/SKILL.md`; injected into `_resolve()`'s system prompt only when drafting a reply. | 5 |
| LLM API + provider abstraction | `backend/app/llm/base.py` (neutral `LLMProvider`/`Message`/`ToolSpec`/`Usage`/`LLMResponse` types), `gemini.py` (current provider), `factory.py` (`get_provider()` switches on `LLM_PROVIDER`). Swapping to Claude = write `anthropic.py` + one env var. | 2 |
| Retry / backoff | `backend/app/llm/retry.py` — `with_retry()`: exponential backoff + jitter on 429/5xx/timeouts; parses Gemini's own `RetryInfo.retryDelay` on 429 rather than guessing. `POST /llm/retry-demo`. | 2 |
| Prompt caching | `Usage.cached_tokens` in `llm/base.py`, surfaced end-to-end through spans (`cache_read_tokens`) and the `/traces` `cache_hit_pct` field; reports honestly as 0% on the Gemini free tier (caching is gated there) — the plumbing is provider-neutral and will populate once Claude is wired in. `POST /llm/cache-demo`. | 2 |
| Observability (spans, traces, cost) | `backend/app/observability.py` — `Trace`/`span()` via `contextvars` (so nested + concurrent spans parent correctly with no manual id-threading); `backend/app/api_traces.py` (`GET /traces`, `GET /traces/{id}` nested tree); `cost_usd()` cost attribution from `settings.model_costs`. | 6 |
| Evals (golden set, deterministic + LLM-as-judge) | `backend/app/evals/golden.json` (20 cases), `metrics.py` (classification/priority accuracy, retrieval hit-rate, citation coverage), `judge.py` (structured faithfulness/helpfulness call), `runner.py` (`run_eval()`), `backend/app/api_evals.py`. | 7 |
| Streaming UX for agents | `orchestrator.py` — `triage_events()` (async generator, real per-phase events, not simulated); `backend/app/api_agent.py` — `POST /agent/triage/stream` (SSE, same `data: ...\n\n` + `[DONE]` convention as `/llm/stream`); `frontend/src/lib/sse.ts` (fetch-stream client, since the body is POSTed and `EventSource` is GET-only). | 8 |
| Making agent internals legible (UI) | `frontend/src/components/SpanWaterfall.tsx` (one Gantt/timeline component reused for both the live SSE timeline and the retrospective trace detail — see `frontend/src/lib/waterfall.ts`'s two adapters); `frontend/src/pages/{Triage,Observability,Evals}Page.tsx`. Design system sourced from the `ui-ux-pro-max` + `dataviz` skills, not hand-picked. | 8 |
