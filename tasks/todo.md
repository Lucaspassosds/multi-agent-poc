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
- **KB source:** **Stripe docs + Wikipedia payment topics** via HTTP fetch + markdownify (url→markdown). Language: **English** (Stripe needs a US egress/VPN). crawl4ai was evaluated and dropped.
- **Chunking:** `RecursiveCharacterTextSplitter` from standalone `langchain-text-splitters` (utility only — NOT orchestration).
- **Past tickets:** ~30 **synthetic** resolved tickets for precedent retrieval.
- **LLM:** provider abstraction (`LLMProvider`). **Now: Gemini free tier** — all roles on `gemini-flash-lite-latest` (the only model with generous free quota: `flash-latest`→3.5 is 20/day, `pro` 429, `2.0-flash` limit 0). **Target: Claude** (haiku/sonnet/opus tiering) via one `LLM_PROVIDER` swap. See spec 03.
- **No agent framework:** only the provider SDK (`google-genai` now / `anthropic` later) + our own loop. This is the whole point.

---

## Phases (checkable)

### Phase 0 — Project scaffold & environment  → spec `01-infrastructure.md`
- [x] `docker-compose.yml`: `db` (pgvector/pg16), `embeddings` (TEI + bge-small-en-v1.5), `backend`, `frontend`, `mcp`
- [x] Backend Dockerfile (`python:3.12-slim` + `uv`), FastAPI app, `GET /health` (checks db + TEI)
- [x] Frontend Dockerfile (`node:24`), Vite + React + TypeScript placeholder
- [x] `.env.example` + `.env` + `.gitignore` (ignore `.env`)
- [x] `README.md` with run instructions
- [x] Verify: `docker compose up` → all services boot; `/health` green; TEI returns 384-dim vector ✅ (db on host port 5433 to avoid local PG12)
- 🎓 Concept: containers per concern; service-name networking; how pieces connect before any AI.

### Phase 1 — Ingest (crawl→chunk→embed) & hybrid search  → spec `02-rag.md`
- [x] Schema: `documents`, `chunks(content, embedding vector(384), fts tsvector)`, GIN + HNSW indexes
- [x] Fetch client → markdown (`rag/fetch.py`, HTTP + markdownify). ⚠️ Stripe geo-localizes via client-side JS → crawl4ai's headless browser returns pt-BR (and hangs behind a VPN); server-rendered HTML honors `Accept-Language: en-US`, so we fetch via HTTP with a US egress (VPN). Ingests 4 Stripe docs + 4 Wikipedia payment topics. crawl4ai was evaluated and dropped.
- [x] Chunking with `RecursiveCharacterTextSplitter` (~800/100)
- [x] TEI embedding client (chunk text → 384-dim vector)
- [x] Synthetic past tickets ingested (15 tickets + 8 synthetic KB articles; ~30 was aspirational)
- [x] `POST /ingest` runs the full pipeline; lexical / semantic / hybrid (RRF) search functions
- [x] Verify ✅: ingest = 8 fetched (4 Stripe EN + 4 Wikipedia) + 8 synthetic KB + 15 tickets = 645 chunks; Stripe docs English (pt_markers=0) & top hits for Stripe queries; paraphrase query → lexical 0 hits, semantic/hybrid nail it
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
- [x] Span model: `traces`+`spans` tables (`schema.sql`); `app/observability.py` — `Trace`/`span()` via
      contextvars, so nested spans (and parallel retrievers) parent correctly with no manual id-threading
- [x] Persist traces to Postgres; `GET /traces` (list + cache-hit%/retries via join), `GET /traces/{id}` (nested tree)
- [x] Cost attribution: `settings.model_costs` ($/Mtok, list price) + `cost_usd()`; retries surfaced via
      `llm/retry.py::last_attempts()` (ContextVar set by `with_retry` on success)
- [x] Instrumented all 3 agent entrypoints: `orchestrator.triage()` (classifier/planner/retriever×N/resolver/critic
      spans), `loop.run_agent()` (llm_call + tool:* spans) — used by `/agent/answer`, `/agent/answer-mcp`, `/agent/triage`
- [~] React dashboard (timeline/waterfall) — deferred to Phase 8 per spec; data is fully ready via `/traces/{id}`
- [x] Verify ✅: `/agent/triage` → trace with root "triage" span, classifier∥planner, 3 retriever spans whose
      `started_at` all sit within 50ms of each other and durations overlap ~1.2-1.4s (proves parallelism on
      timestamps, not just logs); `/agent/answer` → `agent` root → `llm_call`→`tool:hybrid_search`→`llm_call`;
      `/agent/answer-mcp` traces the same way. `cache_hit_pct=0` (expected — Gemini free tier, same as Phase 2).
- 🎓 Concept: spans/traces; what to measure in agent systems; cost attribution.

### Phase 7 — Evals
- [x] Golden set: 20 tickets (`app/evals/golden.json`), grounded in the real seeded KB titles/categories
      so `must_cite`/`expected_category` are checkable against what the pipeline actually produces
- [x] Deterministic metrics (`app/evals/metrics.py`): classification (category+priority) accuracy,
      retrieval hit-rate (must_cite title ∈ retrieved evidence), citation coverage (evidence titles
      that literally appear in the final reply — a documented proxy, not claim-level attribution)
- [x] LLM-as-judge (`app/evals/judge.py`): one structured call/case → faithfulness + helpfulness
      (0-1 + reasoning), `settings.model_critic` (flash-lite per the locked free-tier decision)
- [x] `POST /evals/run?retrieval_mode=lexical|semantic|hybrid`, `GET /evals` (`app/api_evals.py`);
      reuses `orchestrator.triage()` as-is so each case is also a Phase-6 trace (cost visible via
      `/traces/{id}`); React report screen deferred to Phase 8, data's ready
- [x] Regression demo: `search_mode` threaded through `triage()`/`_retrieve()` (dict-dispatch like
      `main.py`'s `/search`) lets `retrieval_mode=lexical` force degraded retrieval on demand
- [~] **Found + fixed a real bug while running this at scale**: Gemini free tier caps at 15
      req/minute; a single `triage()` case alone fires ~7-8 calls, so the golden-set sweep hit sustained
      429s that the old retry (fixed exponential, 8s cap) couldn't survive. Fixed `app/llm/retry.py` to
      parse the 429's own `RetryInfo.retryDelay` (e.g. "37s") and sleep that long instead of guessing —
      root-caused, not a demo-only hack, so it helps every caller. Eval runner also serializes cases
      (`_CONCURRENCY=1`) since a single case already saturates the quota; each case's own internal
      parallelism (classify∥plan, 3 retrievers) is untouched.
- [x] Verify ✅: `POST /evals/run` (hybrid) → 20/20 cases, classification_accuracy=0.80,
      retrieval_hit_rate=1.0, faithfulness_avg=0.915, helpfulness_avg=0.905, cost≈$0.012 (list price).
      `retrieval_mode=lexical` → retrieval_hit_rate 1.0→**0.0**, citation_coverage 0.35→**0.0**,
      faithfulness 0.915→**0.35**, helpfulness 0.905→**0.64** — classification_accuracy unchanged
      (0.80→0.80, as expected, it doesn't depend on retrieval) — the regression is real and isolated
      to the right metrics. `GET /evals` matches; sampled `trace_id`s resolve via `/traces/{id}`.
- 🎓 Concept: why evals matter; deterministic vs model-graded; guarding against regressions.

### Phase 8 — Frontend polish
- [x] Fork resolved with user: spec described `/tickets/triage` as SSE, but only a synchronous
      `/agent/triage` existed. User chose **real streaming** over the no-backend-change option —
      `orchestrator.py` refactored into `_run_pipeline(emit=...)` + `triage_events()` (queue-based
      fan-in from concurrent phases) + a thin `triage()` wrapper (zero behavior change for
      `/agent/triage` and `evals/runner.py`); new `POST /agent/triage/stream` SSE endpoint in
      `api_agent.py`, same `data: ...\n\n` + `[DONE]` convention as `GET /llm/stream`. Small
      additive change: `_retrieve()`'s `cited[]` now carries a `snippet` (needed for the
      "click → source chunk" citation UI, satisfiable without a new route).
- [x] Design system sourced from `ui-ux-pro-max` (Modern Dark / Cinema Mobile style, Inter font,
      dark-only per its own anti-pattern list) + `dataviz` (categorical/status palette validated
      via `validate_palette.js --mode dark --surface #0F172A` — ALL CHECKS PASS; mark specs for
      the waterfall/meters/stat-tiles).
- [x] Triage screen: textarea + presets → `POST /agent/triage/stream` via a hand-rolled
      fetch-stream SSE parser (`lib/sse.ts`) → live `SpanWaterfall` timeline (classify∥plan →
      retrieve×N parallel → resolve → critique → revise) updating in real time → final cited
      answer card (`[Title]` markers → `CitationBadge` popovers) + classification chips.
- [x] Observability dashboard: trace list (`GET /traces`) → trace detail (`GET /traces/{id}`) →
      `SpanWaterfall` (same component, adapted from the real span tree) + stat tiles for
      tokens/cost/cache-hit%/retries.
- [x] Evals report: run button + retrieval_mode selector (with an in-UI ~11-minute-runtime
      warning, per the documented free-tier rate-limit gotcha) → `MetricBar`s for the 6
      aggregates + per-case table with expandable judge reasoning + session-local
      previous-run comparison for the lexical-vs-hybrid regression demo.
- [x] Verify ✅: backend — restarted, probed `POST /agent/triage/stream` directly (Python
      urllib): all 3 retriever `step_start` events land at the identical timestamp (true
      concurrency, not simulated), full event sequence ends in `final`; confirmed `/agent/triage`
      and trace persistence are byte-for-byte unchanged after the refactor. Frontend — `tsc -b`
      clean; headless-Chrome screenshots of all 3 routes show real data rendering correctly
      (Observability lists real past traces; Evals renders the actual Phase-7 lexical-regression
      run — hit-rate 0.00, faithfulness 0.35, matching the documented gotcha numbers exactly) with
      zero console errors beyond a benign React-Router v7 future-flag notice; re-ran the exact
      `sse.ts` parsing algorithm (Node's fetch/ReadableStream, same Web APIs as the browser)
      against the live backend and got the correct interleaved event sequence ending in `final`.
      **Residual gap**: no interactive browser automation (Playwright/chromium-cli) is installed
      in this environment, so the live click-and-watch-the-timeline-animate interaction in
      `TriagePage` was verified by construction and layered proxy checks, not by literally
      clicking the button in a real browser — recommend a quick manual pass in an actual browser
      before the demo.
- 🎓 Concept: streaming UX for agents (real per-step SSE events from concurrent async tasks via
      an `asyncio.Queue` fan-in, not a client-side simulation); making agent internals legible to
      humans (waterfall timelines, cited answers, judge reasoning) — plus a worked example of a
      dark, data-dense design system built from a validated categorical/status color palette
      rather than hand-picked hex values.

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
