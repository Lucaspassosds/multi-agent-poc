# Multi-Agent POC — Support Ticket Triage & Resolution

> **Goal:** A framework-free, multi-agent system that triages incoming support tickets and
> drafts cited resolutions, demonstrating every required AI-engineering concept.
> **Stack:** FastAPI (Python 3.11+) · React + Vite · Postgres 16 + pgvector · Claude API.
> **Working style:** Teach-as-we-build. Each phase has a "🎓 Concept" note explaining the idea
> in plain terms so Lucas can present it confidently.

---

## Product in one paragraph
A support agent (or the system automatically) submits a ticket. An **orchestrator agent**
coordinates specialized **subagents**: a **classifier** (category/priority/sentiment), one or more
**retrievers** that run **hybrid search** over the knowledge base + past resolved tickets, a
**resolver** that drafts a reply grounded in retrieved evidence, and a **critic** that checks the
draft against policy and citation coverage. The UI streams every agent step live, a dashboard shows
traces/tokens/cost/cache-hits, and an evals screen scores the whole pipeline against a golden set.

---

## Demo script (what we'll show)
1. Submit ticket: *"I was charged twice for my subscription this month, please refund the duplicate."*
2. Watch the live timeline: classify → retrieve (parallel) → draft → critic → final.
3. Show the answer with **citations** to KB articles / past tickets.
4. Open the **observability dashboard**: per-step latency, tokens, **prompt-cache savings**, retries.
5. Force an API error to show **retry/backoff** recovering.
6. Run the **evals** and show accuracy + LLM-as-judge scores.

---

## Concept → Phase coverage matrix (the requirements checklist)
| Topic | Where it's demonstrated | Phase |
|---|---|---|
| Orquestração sem framework | Hand-rolled orchestrator loop, no LangChain/CrewAI | 4 |
| Gestão de contexto c/ subagentes | Subagents with isolated context; only summaries return to parent | 4 |
| Paralelismo | `asyncio.gather` / `TaskGroup` for concurrent retrievers | 4 |
| RAG | Ingest → chunk → embed → retrieve grounding context | 1 |
| Pesquisa léxica + semântica (pg_vector) | Postgres full-text (`tsvector`) + vector (`<=>`) fused via RRF | 1 |
| Tools | `hybrid_search`, `get_ticket`, `get_document`, `escalate` | 3 |
| MCP | Search tools re-exposed as an MCP server the agent consumes | 5 |
| Skills | One Claude Agent Skill (e.g. "policy-reply-formatter") | 5 |
| Claude API | Direct Messages API: streaming, tool_use, system prompts | 2 |
| Resolver retry | Exponential backoff + jitter on API/tool failures | 2 |
| Prompt Caching | `cache_control` on system prompt + tools + KB context | 2 |
| Observabilidade | Span-based tracing stored in PG + React dashboard | 6 |
| Evals | Golden set + deterministic metrics + LLM-as-judge | 7 |

---

## Architecture
```
React (Vite)  ──HTTP/SSE──▶  FastAPI  ──▶  Agent layer (pure Python)
  Triage UI                   /ingest        orchestrator loop
  Observability               /triage (SSE)  ├─ classifier subagent
  Evals report                /traces        ├─ retriever subagents (parallel)
                              /evals         ├─ resolver subagent
                                             └─ critic subagent
                                                  │
                        tools ──▶ hybrid_search / get_* / escalate
                        (also exposed via MCP server)
                                                  │
                              Postgres 16 + pgvector
                     documents · tickets · chunks · traces · eval_runs
```

**Locked decisions (see `specs/00-overview.md` for full rationale):**
- **Runtime:** Docker-first for all architectural deps (fallback `uv` for backend). System Python 3.8 is EOL → containers use 3.12.
- **Postgres:** Docker `pgvector/pgvector:pg16` (local PG12 has no pgvector).
- **Embedding model:** `bge-small-en-v1.5` (384-dim, English), served via **TEI** container (backend calls it over HTTP). Upgrade path: `nomic-embed-text-v1.5`.
- **KB source:** crawl **Stripe public docs** with **Crawl4AI** (url→markdown). Language: **English**.
- **Chunking:** `RecursiveCharacterTextSplitter` from standalone `langchain-text-splitters` (utility only — NOT orchestration).
- **Past tickets:** ~30 **synthetic** resolved tickets for precedent retrieval.
- **LLM:** provider abstraction (`LLMProvider`). **Now: Gemini free tier** — all roles on `gemini-flash-lite-latest` (the only model with generous free quota: `flash-latest`→3.5 is 20/day, `pro` 429, `2.0-flash` limit 0). **Target: Claude** (haiku/sonnet/opus tiering) via one `LLM_PROVIDER` swap. See spec 03.
- **No agent framework:** only the provider SDK (`google-genai` now / `anthropic` later) + our own loop. This is the whole point.

---

## Phases (checkable)

### Phase 0 — Project scaffold & environment  → spec `01-infrastructure.md`
- [x] `docker-compose.yml`: `db` (pgvector/pg16), `embeddings` (TEI + bge-small-en-v1.5), `crawler` (Crawl4AI, on-demand `crawl` profile), `backend`, `frontend`
- [x] Backend Dockerfile (`python:3.12-slim` + `uv`), FastAPI app, `GET /health` (checks db + TEI)
- [x] Frontend Dockerfile (`node:24`), Vite + React + TypeScript placeholder
- [x] `.env.example` + `.env` + `.gitignore` (ignore `.env`)
- [x] `README.md` with run instructions
- [x] Verify: `docker compose up` → all services boot; `/health` green; TEI returns 384-dim vector ✅ (db on host port 5433 to avoid local PG12)
- 🎓 Concept: containers per concern; service-name networking; how pieces connect before any AI.

### Phase 1 — Ingest (crawl→chunk→embed) & hybrid search  → spec `02-rag.md`
- [x] Schema: `documents`, `chunks(content, embedding vector(384), fts tsvector)`, GIN + HNSW indexes
- [x] Crawl4AI client → markdown. ⚠️ Deviation: Stripe docs geolocate to pt-BR from a BR IP (server blocks Accept-Language override), so crawler points at **English Wikipedia payment topics** (Chargeback/3-D Secure/Card fraud/PCI DSS). Crawler needs `CRAWL4AI_API_TOKEN` or it binds loopback-only.
- [x] Chunking with `RecursiveCharacterTextSplitter` (~800/100)
- [x] TEI embedding client (chunk text → 384-dim vector)
- [x] Synthetic past tickets ingested (15 tickets + 8 synthetic KB articles; ~30 was aspirational)
- [x] `POST /ingest` runs the full pipeline; lexical / semantic / hybrid (RRF) search functions
- [x] Verify ✅: ingest = 4 crawled + 8 KB + 15 tickets = 612 chunks; paraphrase query → lexical 0 hits, semantic/hybrid nail it
- 🎓 Concept: embeddings, semantic vs lexical, RRF in ~10 lines, chunking trade-offs.

### Phase 2 — LLM API foundations: provider abstraction, retry, caching  → spec `03-claude-integration.md`
- [x] `LLMProvider` interface + `GeminiProvider` (`app/llm/base.py`,`gemini.py`,`factory.py`); factory on `LLM_PROVIDER`
- [x] Streaming chat via the interface (`GET /llm/stream`, SSE)
- [x] Retry/backoff with jitter (`app/llm/retry.py`); `/llm/retry-demo` recovers after 3 attempts ✅
- [x] Structured output (schema-constrained JSON) — `/llm/classify-demo` → `{billing,high,angry}` ✅
- [~] Caching: interface normalizes `Usage.cached_tokens`. ⚠️ Gemini FREE tier gates caching (implicit off; explicit 429 storage quota) → not demonstrable until Claude swap / paid tier. `/llm/cache-demo` reports this honestly.
- [x] Verify ✅: `/llm/chat` returns real Gemini output+usage; model IDs fixed to `-latest` aliases (2.5-* gated for new keys); critic=`gemini-3.5-flash` (pro is 429 on free tier).
- 🎓 Concept: one interface over many providers; how caching bills differently; retry patterns.

### Phase 3 — Tools + single agent
- [x] Tool schemas: `hybrid_search`, `get_document`, `get_ticket`, `escalate` (`app/agents/tools.py`)
- [x] Tool dispatcher (name → python fn), errors returned as JSON (never raises)
- [x] Single-agent loop (`app/agents/loop.py`): call → tool_use → execute → feed back → final
- [x] Verify ✅: `/agent/answer` on the double-charge ticket → hybrid_search → get_document(5) → cited reply (3 iters). Fixed Gemini-3 `thought_signature` echo in provider.
- 🎓 Concept: the tool-use loop; JSON schemas; how the model "decides" to call a tool.

### Phase 4 — Multi-agent orchestration (the centerpiece)
- [x] Orchestrator (`app/agents/orchestrator.py`, framework-free): classify∥plan → retrieve×N → resolve → critique → revision
- [x] Subagents: classifier / retriever / resolver / critic — each a fresh isolated-context call, tiered model
- [x] Context management: subagents return compact summaries (not raw transcripts)
- [x] Parallelism: retrievers via `asyncio.gather`
- [x] Verify ✅: `/agent/triage` → classify {refund,high,neutral}, 3 retrievers **2.25× speedup**, critic forced 1 revision, grounded final. Fixed thinking-model JSON truncation via `thinking_budget=0`.
- 🎓 Concept: why subagents keep context clean; orchestrator vs worker roles; parallel fan-out.

### Phase 5 — MCP server + Skills
- [x] Standalone MCP server (`app/mcp_server.py`, FastMCP Streamable-HTTP :9000/mcp; own compose service)
- [x] Backend consumes it (`app/mcp_client.py`): lists tools → neutral ToolSpec → same agent loop
- [x] One Skill — filesystem `SKILL.md` "policy-reply-formatter" (`app/skills.py`, progressive disclosure; native Agent Skills API deferred to Claude)
- [x] Verify ✅: `/agent/answer-mcp` used MCP `['hybrid_search','get_document']`; `/agent/triage?skill=true` → disclaimer + `(per: …)` citations present (toggle with `skill=false`)
- 🎓 Concept: what problem MCP solves (tool interoperability); Skills vs raw tools.

### Phase 6 — Observability
- [ ] Span model: run → agent steps → tool calls (id, parent, tokens, latency, cache, retries)
- [ ] Persist traces to Postgres; `GET /traces`, `GET /traces/{id}`
- [ ] React dashboard: timeline, token/cost breakdown, cache-hit %, retry count
- [ ] Verify: a triage run produces a complete, inspectable trace
- 🎓 Concept: spans/traces; what to measure in agent systems; cost attribution.

### Phase 7 — Evals
- [ ] Golden set (~20 tickets w/ expected category + reference answer)
- [ ] Deterministic metrics: classification accuracy, retrieval hit-rate, citation coverage
- [ ] LLM-as-judge for answer quality (faithfulness, helpfulness)
- [ ] `POST /evals/run`, `GET /evals`; React report screen
- [ ] Verify: eval run produces scores; a deliberate regression is caught
- 🎓 Concept: why evals matter; deterministic vs model-graded; guarding against regressions.

### Phase 8 — Frontend polish
- [ ] Triage screen: submit ticket, live SSE agent timeline, final cited answer
- [ ] Observability dashboard (from Phase 6)
- [ ] Evals report (from Phase 7)
- [ ] Verify: full demo script runs cleanly end-to-end
- 🎓 Concept: streaming UX for agents; making agent internals legible to humans.

### Phase 9 — Docs & presentation
- [ ] `README` architecture diagram + run guide
- [ ] One-page "concept → where in code" map for reviewers
- [ ] Short talking-track / slides outline for the demo
- 🎓 Concept: how to present AI-eng work to an engineering audience.

---

## Open decisions — all resolved ✅
1. Runtime → **Docker-first** (fallback uv). 2. Embeddings → **bge-small-en-v1.5 via TEI (384-dim)**. 3. KB → **Stripe docs, English**.
4. Past tickets → **~30 synthetic**. 5. Chunking → **RecursiveCharacterTextSplitter**.
6. LLM → **provider abstraction; Gemini free tier now, Claude later** (Anthropic credits blocked). See `specs/03`.
- ✅ Gemini API key obtained. ⏳ Deferred: Anthropic API key once credits unblock (enables native Skills API + Claude `cache_control` metrics).

---

## Review (filled in as we complete phases)
_(empty)_
