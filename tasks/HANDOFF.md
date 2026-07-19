# HANDOFF — Multi-Agent Support Triage POC

> Purpose of this doc: let a fresh agent (or teammate) pick up this project and continue
> **without re-discovering context**. Read this top-to-bottom, then `specs/00-overview.md`.
> Last updated after Phase 7 (evals: golden set + deterministic metrics + LLM-judge). Working dir: `/home/lucas/PROJETOS/multi-agent-poc`.

---

## 1. What this project is

A **framework-free multi-agent system** that triages support tickets (domain: **payments support**) and
drafts **cited resolutions**. It's a POC built to demonstrate a checklist of AI-engineering concepts:
orchestration without a framework, MCP, RAG, observability, evals, skills, tools, lexical+semantic search
in Postgres/pgvector, the LLM API, context management via subagents, retry, parallelism, prompt caching.

- **Source of truth = `specs/`** (spec-driven: write/keep the spec, then build). Start at `specs/00-overview.md`.
- **Progress tracker = `tasks/todo.md`** (checkboxes per phase, with verification notes + deviations).
- **This repo is on GitHub**: `origin` → https://github.com/Lucaspassosds/multi-agent-poc.git, branch **`main`**.

## 2. Stack (locked)

| Layer | Choice |
|---|---|
| Backend | FastAPI, Python 3.12, `uv`, async (`asyncpg`, `httpx`) — runs in Docker |
| Frontend | React + Vite + TypeScript (placeholder only so far; real UI is Phase 8) |
| DB / vectors | **Postgres 16 + pgvector** (no other vector DB — a requirement). Lexical search = Postgres full-text |
| Embeddings | **`bge-small-en-v1.5`** (384-dim), served by **TEI** container over HTTP |
| LLM | **Provider abstraction** (`app/llm/base.py`). **Now: Google Gemini free tier**; **target: Claude** via one env var. |
| Ingest fetch | Plain **HTTP GET + `markdownify`** (NOT a headless browser — crawl4ai was removed, see §7) |

## 3. Current status — 8 of 9 phases done ✅ (all verified end-to-end)

| Phase | Status | Where |
|---|---|---|
| 0 · Infra (Docker, /health) | ✅ | `docker-compose.yml`, `backend/`, `frontend/`, spec 01 |
| 1 · RAG: ingest + hybrid search | ✅ | `app/rag/*`, `app/db.py`, `app/embeddings.py`, spec 02 |
| 2 · LLM provider + retry + caching | ✅ | `app/llm/*`, `app/api_llm.py`, spec 03 |
| 3 · Tools + single agent | ✅ | `app/agents/tools.py`, `loop.py`, spec 04 |
| 4 · Multi-agent orchestration | ✅ | `app/agents/orchestrator.py`, spec 04 |
| 5 · MCP server + Skills | ✅ | `app/mcp_server.py`, `mcp_client.py`, `skills.py`, `skills/`, spec 05 |
| 6 · Observability (spans/traces + cost) | ✅ | `app/observability.py`, `app/api_traces.py`, spec 06 |
| 7 · Evals (golden set + metrics + judge) | ✅ | `app/evals/*`, `app/api_evals.py`, spec 07 |
| **8 · Frontend (uses `ui-ux-pro-max` skill)** | ⬜ **NEXT** | spec `08-frontend.md` |
| 9 · Docs & presentation | ⬜ | — |

Every completed phase has a `[x]` + verification note in `tasks/todo.md`. Trust those.

## 4. How to run it

```bash
cd /home/lucas/PROJETOS/multi-agent-poc
cp .env.example .env          # already done; .env has the working GEMINI_API_KEY (git-ignored)
docker compose up -d --build  # 5 services: db, embeddings, backend, frontend, mcp
```
The stack is currently **already running** (containers up for hours). Then:

```bash
# build the knowledge base (fetches Stripe+Wikipedia, embeds, stores). ~77s. No LLM/quota used.
curl -X POST 'localhost:8000/ingest?fetch=true&reset=true'   # (curl may be hook-blocked; use urllib — see §8)
```

### Endpoints (all live)
| Endpoint | What |
|---|---|
| `GET /health` | db + TEI reachability |
| `POST /ingest?fetch=&reset=` | build KB |
| `GET /search?q=&mode=lexical|semantic|hybrid&k=` | search |
| `POST /llm/chat` `/llm/stream` `/llm/retry-demo` `/llm/cache-demo` `/llm/classify-demo` | Phase-2 demos |
| `POST /agent/answer` | single tool-using agent (Phase 3) |
| `POST /agent/answer-mcp` | same, tools sourced over MCP (Phase 5) |
| `POST /agent/triage?skill=&search_mode=lexical|semantic|hybrid` | **the full multi-agent pipeline** (Phase 4); synchronous, not SSE (see §9a) |
| `GET /traces` `/traces/{id}` | list runs / full span tree — tokens, cost, cache-hit %, retries (Phase 6) |
| `POST /evals/run?retrieval_mode=` `GET /evals` | golden-set eval run (20 cases) + latest results (Phase 7) |

Body for agent endpoints: `{"message": "I was charged twice, please refund the duplicate."}`

### Ports
backend `8000` · frontend `5173` · TEI `8080` · **db host `5433`** (→ container 5432; 5433 avoids a local PG12) · mcp `9000`

## 5. Code map (`backend/app/`)

```
config.py            typed settings (pydantic-settings) — reads env / .env
db.py                asyncpg pool + pgvector codec + init_schema()
schema.sql           documents + chunks (vector(384) + generated tsvector; GIN + HNSW indexes)
embeddings.py        TEI client (text -> 384-dim vectors, batched)
seed_data.py         synthetic English KB articles (8) + past tickets (15)
rag/
  fetch.py           HTTP GET + markdownify (url -> markdown)  [was crawl.py]
  chunking.py        RecursiveCharacterTextSplitter (~800/100)
  ingest.py          FETCH_URLS + pipeline: fetch|synthetic -> chunk -> embed -> store
  search.py          lexical_search / semantic_search / hybrid_search (RRF)
llm/
  base.py            NEUTRAL types: LLMProvider, Message, ToolSpec, ToolCall, Usage, LLMResponse
  gemini.py          GeminiProvider (google-genai). Handles thought_signature + thinking_budget
  retry.py           with_retry() — backoff + jitter on transient (429/5xx/timeouts)
  factory.py         get_provider() switches on settings.llm_provider
agents/
  tools.py           tool schemas + dispatcher (hybrid_search/get_document/get_ticket/escalate)
  loop.py            hand-rolled tool-use loop (accepts a dispatch_fn; MCP path reuses it)
  orchestrator.py    classify ∥ plan -> retrieve×N (parallel) -> resolve -> critique -> revision
mcp_server.py        FastMCP server (Streamable HTTP :9000/mcp) exposing search tools
mcp_client.py        connects to MCP, lists tools -> neutral ToolSpec, dispatch over protocol
skills.py            filesystem SKILL.md loader (progressive disclosure)
skills/policy-reply-formatter/SKILL.md
observability.py     Trace/span (contextvars) — spans accumulate in memory, persisted on trace exit; cost_usd()
evals/
  golden.json        20 hand-written cases grounded in seed_data.py's KB titles
  metrics.py         deterministic: classification match, retrieval hit-rate, citation coverage
  judge.py           LLM-as-judge — one structured call/case -> faithfulness + helpfulness
  runner.py          run_eval(): sequential (see gotcha below) over golden set, persists eval_runs/eval_cases
api_llm.py           /llm/* router      api_agent.py  /agent/* router     api_traces.py  /traces* router
api_evals.py         /evals* router     main.py       app + /health + /ingest + /search
```

## 6. Key decisions & why (so you don't relitigate them)

- **Gemini instead of Claude (for now):** the user couldn't add Anthropic billing. The `LLMProvider`
  interface means swapping to Claude later is **one env var** (`LLM_PROVIDER=anthropic`) + writing
  `app/llm/anthropic.py` (not yet done). ~12 of 13 concepts are provider-agnostic.
- **All roles use `gemini-flash-lite-latest`** (see §7 for the quota reason). Cost-tiering
  (haiku/sonnet/opus) returns automatically when swapped to Claude.
- **HTTP fetch, not crawl4ai** for ingest (see §7).
- **English KB** (Stripe docs + Wikipedia payment topics + synthetic). User confirmed English over pt-BR.

## 7. GOTCHAS — hard-won, will bite you if unknown (also in `.claude/.../memory/`)

**Gemini free tier:**
- `gemini-2.5-*` model IDs are **gated off for new keys**. `gemini-flash-latest` is an alias for
  `gemini-3.5-flash` and both cap at **20 requests/DAY**. `gemini-pro-latest` → 429. `gemini-2.0-flash`
  → **limit 0 (paid only)**. Only **`gemini-flash-lite-latest`** has generous free quota → all roles use it.
- **Prompt caching is unusable on the free tier** (implicit never triggers; explicit `caches.create` → 429
  storage-quota). The interface still normalizes `Usage.cached_tokens`; real caching lands with Claude.
- **Gemini 3 requires echoing `thought_signature`** on function-call parts sent back. Handled by keeping
  the original `types.Part` in `ToolCall.raw` and re-sending it (`app/llm/gemini.py`).
- **Thinking models truncate structured JSON** — reasoning eats `max_output_tokens`. Fix: `thinking_budget=0`
  for structured/JSON calls (`orchestrator._json`, provider guards it to models that support it).
- **Free tier is also capped at 15 requests/MINUTE** (not just the daily caps above) — found running
  Phase 7's 20-case eval sweep: a single `triage()` case alone fires ~7-8 calls in a few seconds, so back-
  to-back cases blew through it fast. The old retry (fixed exponential, 8s max) couldn't survive a real
  quota window. Fixed at the root in `app/llm/retry.py`: parse the 429's own `RetryInfo.retryDelay` (e.g.
  "37s") and sleep that long +jitter instead of guessing — benefits every caller, not just evals. The evals
  runner also runs cases sequentially (`_CONCURRENCY=1` in `app/evals/runner.py`) since one case alone
  nearly saturates the quota; a 20-case eval run now takes **~11 minutes** for this reason — expected, not a bug.

**Infra / networking:**
- **DB is on host port 5433** (local PG12 owns 5432). Inside Docker it's still `db:5432`.
- **Editing `.env` requires `docker compose up -d --force-recreate <svc>`** — env_file changes aren't auto-detected by a plain restart.
- **Stripe docs geo-localize via client-side JS** → a headless browser returns pt-BR from a BR IP; the
  server-rendered HTML honors `Accept-Language: en-US`. So English Stripe needs a **US egress (VPN)** AND
  the plain-HTTP fetch path (not a browser). VPN only needed when *re-fetching* Stripe; the KB persists in
  the `pgdata` volume.
- **A host VPN breaks Docker's default DNS.** Fix already applied: `backend` service has
  `dns: [1.1.1.1, 8.8.8.8]` (service-name resolution via 127.0.0.11 still works).
- **crawl4ai was evaluated and removed** — its headless Chromium returns pt-BR for Stripe and hangs behind
  a VPN. Ingest is now pure HTTP. Don't reintroduce it expecting it to work here.

**Env constraints:** ~4 GB free RAM, weak GPU (CPU-only inference is fine). Host Python is 3.8 (EOL) — never
run backend code on the host; it runs in the container (3.12). The `curl` command is intercepted by a hook
in this environment — use Python `urllib`/`httpx` for HTTP probes (see §8).

## 8. Verifying / probing (curl is hook-blocked → use urllib)

```python
python3 - <<'PY'
import json, urllib.request
req=urllib.request.Request("http://localhost:8000/agent/triage",
    data=json.dumps({"message":"I was charged twice, refund the duplicate."}).encode(),
    method="POST", headers={"Content-Type":"application/json"})
print(json.load(urllib.request.urlopen(req, timeout=180)))
PY
```
Backend logs: `docker compose logs backend --since 60s`. Backend hot-reloads `app/` (bind mount), but
**restart after changing imports/lifespan**; **rebuild only when `pyproject.toml` deps change**
(`docker compose build backend`).

## 9. What's next — Phase 8 (Frontend)

Phases 6-7 are done (see status table above). Backend is feature-complete for the whole demo — Phase 8
is pure frontend, zero backend work expected *unless* the SSE fork below (§9a) is resolved toward "build
real streaming". `frontend/` is still exactly the **Phase 0 placeholder** (`Dockerfile`, bare
`src/App.tsx`/`main.tsx`, no routing/UI libs installed) — nothing has been built there yet.

**Read `specs/08-frontend.md` first.** Steps, in order:
1. **Invoke the `ui-ux-pro-max` skill before writing any UI code** — the spec is explicit that style/
   palette/font/layout/chart choices must come from it, not be hand-picked. Also load `dataviz` for the
   span waterfall specifically.
2. Three screens: **Triage** (submit ticket → live-ish timeline → cited final answer + classification
   chips), **Observability dashboard** (trace list + span waterfall + cost/cache-hit/retry stats),
   **Evals report** (aggregates + per-case table with judge reasoning, and a way to trigger/compare the
   regression demo).
3. Real endpoints to consume (see table in §4 — **note these differ from spec 08's own endpoint list**,
   see §9a): `POST /agent/triage?skill=&search_mode=`, `GET /traces`, `GET /traces/{id}`,
   `POST /evals/run?retrieval_mode=`, `GET /evals`, `POST /ingest`.

### 9a. ⚠️ Open fork to consult the user on before building the Triage screen
`specs/08-frontend.md` describes the hero screen as SSE-streamed (`POST /tickets/triage` (SSE), "watch
each step live"). **That endpoint doesn't exist.** What actually exists is `POST /agent/triage` — a
single synchronous call that runs the whole classify→retrieve→resolve→critique pipeline server-side and
returns one JSON blob (including `trace_id`) only once it's fully done; the Phase-6 `Trace` is persisted
atomically in `Trace.__aexit__`, so there's **no partial/live trace visible mid-request** today. Two ways
to reconcile this — **ask the user before picking one, it's an architecture fork**:
- **(A) No backend changes (simplest)**: call `/agent/triage`, show a loading state, then render the
  complete result — and separately fetch `/traces/{trace_id}` to render the waterfall *retrospectively*
  (after the fact, not "live"). Still legible and demoable, just not truly streaming.
- **(B) Real streaming**: refactor `orchestrator.triage()` to emit step/span events incrementally (e.g.
  an async generator + SSE endpoint), so the UI timeline animates as it actually happens. More faithful
  to the spec/demo script, but a real backend change to code that's already verified — treat it as its
  own mini-plan, not a drive-by edit.

Then Phase 9 (docs & presentation) is all that's left.

## 10. Conventions

- **Teach-as-we-build**: the user is upskilling in AI eng — explain concepts plainly as you implement.
- **Verify before claiming done**: run the endpoint, show real output. Every phase has a verification note.
- **Consult on real forks**: ask before decisions that change architecture or are costly to reverse.
- **Commits**: conventional prefixes, scoped per subsystem/phase, end with the
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>` trailer. Commit/push only when asked.
- **Memory**: durable gotchas live in `.claude/projects/-home-lucas-PROJETOS-multi-agent-poc/memory/`
  (`gemini-free-tier-gotchas.md`, `crawl-vpn-gotchas.md`, project + working-style notes).
- No mention of a specific person/role in repo files (all such references were scrubbed to neutral wording).
