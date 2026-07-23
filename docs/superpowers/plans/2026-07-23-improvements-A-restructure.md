# Phase A — Restructure & Discoverability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the manager's #1 complaint — *"I couldn't find each concept in the code."* Make **folder = concept** literally true for the real modules, give the four cross-cutting techniques a named home + a greppable signpost, and add a discoverability layer (`backend/app/README.md`, upgraded `docs/CONCEPTS.md`, a repo-map in the top `README.md`) where a reviewer actually looks. This is spec `specs/improvements/01-restructure-discoverability.md`. **Zero behavior change** — only moves, renames, comments, and docs.

**Architecture:** Seven independently-committable, independently-runnable tasks ordered safest→riskiest: (1) discoverability docs, (2) `── Concept:` signpost banners, (3) `embeddings.py`+`seed_data.py`→`rag/`, (4) `agents/tools.py`→`tools/registry.py`, (5) resolve the `skills.py`/`skills/` collision, (6) `mcp_*.py`→`mcp/` package + the one `docker-compose.yml` command line, (7) `api_*.py`→`api/` package + `main.py` wiring. Every module move preserves the file's existing signposts and docstrings (moved via `git mv`), and keeps the blast radius tiny with re-export shims (`tools/__init__.py`, `skills/__init__.py`).

**Tech Stack:** FastAPI (Python 3.12) backend, run under Docker Compose (`db`, `embeddings`, `mcp`, `backend`, `frontend`). React + Vite frontend (**untouched** in this phase — it references the backend only by URL path). Postgres 16 + pgvector. No test framework (see Global Constraints).

## Global Constraints

- **No behavior change.** The HTTP contract is byte-identical: every router `prefix=`/`tags=` and every route path is unchanged; `include_router(...)` order in `main.py` is unchanged. DB schema is unchanged. `schema.sql` **stays beside `db.py`** at the `app/` root (it is loaded via `Path(__file__).parent / "schema.sql"` and holds *all* tables — shared infra, not RAG-specific).
- **Frontend is untouched.** No file under `frontend/` changes. The only cross-service edit is a **single line** in `docker-compose.yml` (the `mcp` service `command`, Task 6). The `./backend/app:/app/app` bind-mount and the Dockerfile `COPY` are directory-level, so intra-`app/` moves need **no Dockerfile change**.
- **Re-export shims keep the blast radius small.** `tools/__init__.py` and `skills/__init__.py` re-export the public names so call sites (`orchestrator.py`'s skills import in particular) do not change.
- **Deliberately NOT moved / churned:** `agents/orchestrator.py`, `agents/loop.py`, everything in `llm/`, everything in `evals/`, `observability.py`, `db.py`, `config.py`, `schema.sql`, `main.py` (edited only for the api-import rewire in Task 7). `rag/`, `agents/`, `llm/`, `evals/` are already clean.
- **Cross-spec coordination (do the *move* now, the *rework* later).** Task 5 (Skills) and Task 6 (MCP) move code that specs 04 (Skills) and 03 (MCP) will rewrite in **Phase C**. Move it into the new location now; do **not** polish the old code that is about to be replaced (see `specs/improvements/00-overview.md` § "Order of operations"). These are flagged inline as **[coordinate with Phase C]**.
- **Docs describe the destination.** Task 1's discoverability docs reference the *post-restructure* paths (`tools/registry.py`, `mcp/server.py`, `skills/loader.py`, `rag/embeddings.py`). They become fully accurate as Tasks 3–7 land; by the end of Phase A everything is consistent. This is intentional (spec: "do this even if the moves are deferred").
- **`app/mcp/` vs the third-party `mcp` package.** Python 3 imports are absolute by default, so inside `app/mcp/server.py` the line `from mcp.server.fastmcp import FastMCP` resolves to the **installed** `mcp` library, not the sibling package — but this is verified explicitly in Task 6.
- **NO test framework exists in this repo — this is a deliberate, documented convention. Do NOT add pytest/vitest/TDD.** Verification is **manual**, using these real commands:
  - `docker compose up -d --build` — bring the stack up.
  - `curl -s localhost:8000/health` — expect `{"status":"ok", ...}`.
  - `docker compose exec backend python -c "import app.main"` — whole-app import-graph smoke test (imports every router, orchestrator, tools, rag, skills, mcp client — a broken import anywhere fails here).
  - `curl` the moved/affected endpoints (paths listed per task).
  - `docker compose exec frontend npm run build` — frontend typecheck (Task 7, to confirm the frontend is unaffected).
  - `docker compose logs backend --since 2m` / `docker compose logs mcp --since 2m` — check for import/boot errors.
  - `grep -rn "── Concept:" backend/app` — the table-of-contents check (Task 2).
- **One commit per task**, at the end of the task, after its verification passes. Use `git mv` for every move (preserves history). Co-author trailer per repo convention.

---

## File Structure

Target tree after Phase A (`backend/app/`):

```
backend/app/
├── README.md                       # NEW (Task 1) — folder=concept table + cross-cutting section
├── main.py  config.py  db.py  schema.sql   # entrypoint + plumbing (schema.sql STAYS here)
├── observability.py                # OBSERVABILITY signpost (Task 2); file→package deliberately SKIPPED
├── llm/     base.py factory.py gemini.py retry.py         # LLM API + retry + caching signposts
├── rag/     fetch.py chunking.py ingest.py search.py + embeddings.py + seed_data.py   # last two MOVED IN (Task 3)
├── agents/  orchestrator.py loop.py        # orchestration/subagents/parallelism + tools-loop signposts
├── tools/   registry.py + __init__.py      # ← PROMOTED from agents/tools.py (Task 4)
├── skills/  loader.py + __init__.py + definitions/policy-reply-formatter/SKILL.md   # collision resolved (Task 5)
├── mcp/     server.py client.py + __init__.py     # ← two loose files → one package (Task 6)
├── evals/   golden.json judge.py metrics.py runner.py   # unchanged (EVALS signpost added Task 2)
└── api/     agent.py evals.py llm.py tickets.py traces.py + __init__.py   # ← api_*.py grouped (Task 7)
```

Docs touched (Task 1): `backend/app/README.md` (new), `docs/CONCEPTS.md` (upgraded), `README.md` (repo map added).
Config touched (Task 6): `docker-compose.yml` — one line (`mcp` service `command`).

**Blast-radius import edits (the entire code edit surface, from the spec's table):**

| Move | Files whose imports change | Change |
|---|---|---|
| embeddings/seed → rag (T3) | `rag/search.py:14`, `rag/ingest.py:9`, `rag/ingest.py:12` | `app.embeddings`→`app.rag.embeddings`; `app.seed_data`→`app.rag.seed_data` |
| tools promote (T4) | `agents/loop.py:7`, `mcp_server.py:12` | import from `app.tools`; `tools/__init__.py` re-exports `TOOL_SPECS, dispatch, _get_document` |
| skills collision (T5) | (orchestrator import **unchanged** via shim) | `skills/__init__.py` re-exports `list_skills, load_skill`; loader `_SKILLS_DIR` → `"definitions"` (**only logic change in Phase A**) |
| mcp package (T6) | `api_agent.py:12`, `docker-compose.yml` mcp `command` | `app.mcp_client`→`app.mcp.client`; `python -m app.mcp_server`→`python -m app.mcp.server` |
| api group (T7) | `main.py:13-17` (5 router imports), `api/agent.py` (`app.api_tickets`→`app.api.tickets`) | import paths; every `prefix=`/`tags=` **unchanged** |

---

## Task 1: Discoverability layer (pure additions — new `app/README.md`, upgraded `CONCEPTS.md`, repo map)

**Files:**
- Create: `backend/app/README.md`
- Modify: `docs/CONCEPTS.md`
- Modify: `README.md`

**Interfaces:** None (documentation only). No code, no imports, no runtime impact.

- [ ] **Step 1: Create `backend/app/README.md`** (the highest-leverage artifact — it sits exactly where the reviewer got lost). Write:

```markdown
# `backend/app/` — folder = concept

This POC deliberately maps **one top-level folder (or file) to one AI-engineering concept**, so a
reviewer can locate any concept in seconds. The four *cross-cutting* techniques don't get an
artificial folder — they live in a named home with a greppable signpost (see below).

Domain: every concept is demonstrated *through* **Stripe payments support triage**, not in the abstract.

## Concept modules

| Folder / file | Concept | Start here |
|---|---|---|
| `agents/orchestrator.py` | Orchestration without a framework | `triage()` / `_run_pipeline()` — hand-rolled classify→retrieve→resolve→critique→revision |
| `agents/loop.py` | Tools — the hand-rolled tool-use loop | `run_agent()` |
| `tools/registry.py` | Tools — function-calling registry | `TOOL_SPECS`, `dispatch()` |
| `mcp/` | MCP (Model Context Protocol) | `server.py` (FastMCP, `:9000/mcp`), `client.py` `mcp_session()` |
| `rag/` | RAG (retrieval-augmented generation) | `ingest.py` `ingest_all()`; `fetch.py`, `chunking.py`, `embeddings.py`, `seed_data.py` |
| `rag/search.py` + `schema.sql` | Lexical + semantic search in pgvector | `hybrid_search()` (RRF of `tsvector` lexical + `vector` cosine) |
| `skills/` | Skills (progressive disclosure) | `loader.py` `load_skill()` + `definitions/<name>/SKILL.md` |
| `llm/` | LLM API + provider abstraction | `base.py` (neutral types), `factory.py` `get_provider()` |
| `observability.py` | Observability (spans / traces / cost) | `Trace`, `span()` (contextvars); surfaced via `api/traces.py` |
| `evals/` | Evals (golden set + LLM-as-judge) | `runner.py` `run_eval()`; `golden.json`, `metrics.py`, `judge.py` |
| `api/` | HTTP surface (thin routers only) | `agent.py`, `traces.py`, `tickets.py`, `evals.py`, `llm.py` |
| `main.py` `config.py` `db.py` `schema.sql` | Entrypoint + plumbing (not a concept) | `main.py` |

## Cross-cutting techniques (no folder — a named home + a signpost)

| Technique | Home | Symbol |
|---|---|---|
| Context management via subagents | `agents/orchestrator.py` | each `_classify/_plan/_retrieve/_resolve/_critique` is a fresh isolated call |
| Retry / backoff | `llm/retry.py` | `with_retry()` |
| Parallelism | `agents/orchestrator.py` | `asyncio.gather(...)` in `_run_pipeline()` |
| Prompt caching | `llm/base.py` → `observability.py` → `api/traces.py` | `Usage.cached_tokens` → span `cache_read_tokens` → `/traces` `cache_hit_pct` |

Every concept home carries a uniform, greppable header. To print the table of contents:

    grep -rn "── Concept:" backend/app
```

- [ ] **Step 2: Upgrade `docs/CONCEPTS.md`** — split the single table into two (Concept modules / Cross-cutting techniques), add a **Signpost** column, and update the paths that Tasks 3–7 move. Replace the whole file with:

```markdown
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
```

- [ ] **Step 3: Add a Repo map to the top `README.md`.** The concept-map link is at line 16 (`- **Concept → code map** ...`). Insert a repo-map bullet immediately after it. Edit:

Replace:

```markdown
- **Concept → code map** (for reviewers): [`docs/CONCEPTS.md`](docs/CONCEPTS.md).
- **Demo talking track**: [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md).
```

with:

```markdown
- **Concept → code map** (for reviewers): [`docs/CONCEPTS.md`](docs/CONCEPTS.md).
- **Repo map** — every backend folder is one concept (details in [`backend/app/README.md`](backend/app/README.md)):
  ```
  backend/app/
  ├── agents/         orchestration (framework-free) · subagent context · parallelism
  ├── tools/          function-calling registry (+ the tool-use loop in agents/loop.py)
  ├── mcp/            MCP server + client
  ├── rag/            RAG · lexical+semantic search in pgvector · embeddings · seed data
  ├── skills/         SKILL.md loader + definitions/ (progressive disclosure)
  ├── llm/            provider abstraction · retry/backoff · prompt caching
  ├── evals/          golden set + LLM-as-judge
  ├── observability.py  spans / traces / cost
  ├── api/            thin HTTP routers
  └── main.py config.py db.py schema.sql   entrypoint + plumbing
  ```
- **Demo talking track**: [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md).
```

- [ ] **Step 4: Verify (docs render + no accidental code touch).**

Run:
```bash
git status --porcelain           # expect ONLY: backend/app/README.md (new), docs/CONCEPTS.md, README.md
grep -c "── Concept:" docs/CONCEPTS.md   # expect >= 13 (the signpost column references)
```
Expected: exactly those three doc paths changed, no `.py` files. (The actual banners land in Task 2; here they only appear as text inside `CONCEPTS.md`.)

- [ ] **Step 5: Commit.**

```bash
git add backend/app/README.md docs/CONCEPTS.md README.md
git commit -m "docs(structure): folder=concept README, two-table CONCEPTS map, repo map

Adds backend/app/README.md (folder->concept table + cross-cutting homes +
grep command), splits docs/CONCEPTS.md into Concept-modules and
Cross-cutting-techniques tables with a Signpost column and destination
paths, and adds a Repo map tree to the top README. Docs describe the
post-restructure layout that Tasks 2-7 realize. No code changes.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: `── Concept:` signpost banners (comments only, 15 placements)

**Files (all edited in place at their *current* paths; banners travel with the files during the later `git mv` moves):**
- Modify: `backend/app/agents/orchestrator.py` (3 banners)
- Modify: `backend/app/agents/loop.py` (1)
- Modify: `backend/app/agents/tools.py` (1)
- Modify: `backend/app/mcp_server.py` (1)
- Modify: `backend/app/mcp_client.py` (1)
- Modify: `backend/app/rag/ingest.py` (1)
- Modify: `backend/app/rag/search.py` (1)
- Modify: `backend/app/llm/base.py` (2)
- Modify: `backend/app/llm/retry.py` (1)
- Modify: `backend/app/skills.py` (1)
- Modify: `backend/app/observability.py` (1)
- Modify: `backend/app/evals/runner.py` (1)

**Interfaces:** None — every banner is a `#` comment. No import, signature, or runtime change. Convention (from the spec): one uniform line per concept home, `# ── Concept: <NAME> ── <one-line why>`. All 13 concepts are covered across these 15 lines (orchestrator hosts 3: orchestration, subagent-context, parallelism; `llm/base.py` hosts 2: LLM API, prompt caching; MCP has server + client; Tools has registry + loop).

- [ ] **Step 1: `agents/orchestrator.py` — 3 banners.** Insert each as an Edit (text-anchored, so insertion order doesn't shift the others).

Banner 1 (top, after docstring). Replace:
```python
"""
import asyncio
```
with:
```python
"""
# ── Concept: ORCHESTRATION (FRAMEWORK-FREE) ── hand-rolled classify→retrieve→resolve→critique→revision; no LangChain/CrewAI/LangGraph.
import asyncio
```

Banner 2 (subagent context, before `_classify`). Replace:
```python
async def _classify(ticket: str):
```
with:
```python
# ── Concept: CONTEXT MANAGEMENT (SUBAGENTS) ── each step is a fresh, isolated LLM call; only a compact result returns, never a growing transcript.
async def _classify(ticket: str):
```

Banner 3 (parallelism, at the fan-out `gather`). Replace:
```python
        (classification, u1), (subqs, u2) = await asyncio.gather(_classify_emit(), _plan_emit())
```
with:
```python
        # ── Concept: PARALLELISM ── classify + plan (and below, all retrievers) run concurrently via asyncio.gather; overlap is provable on span timestamps.
        (classification, u1), (subqs, u2) = await asyncio.gather(_classify_emit(), _plan_emit())
```

- [ ] **Step 2: `agents/loop.py` — Tools (loop).** Replace:
```python
"""
from app.agents.tools import TOOL_SPECS, dispatch
```
with:
```python
"""
# ── Concept: TOOLS (THE HAND-ROLLED LOOP) ── call model → run requested tools → feed results back → repeat until final. No framework.
from app.agents.tools import TOOL_SPECS, dispatch
```

- [ ] **Step 3: `agents/tools.py` — Tools (registry).** Replace:
```python
"""
import json
```
with:
```python
"""
# ── Concept: TOOLS (FUNCTION CALLING) ── JSON-schema tool specs + a dispatcher: hybrid_search / get_document / get_ticket / escalate.
import json
```

- [ ] **Step 4: `mcp_server.py` — MCP (server).** Replace:
```python
"""
from mcp.server.fastmcp import FastMCP
```
with:
```python
"""
# ── Concept: MCP (SERVER) ── the same search tools exposed over Model Context Protocol (Streamable HTTP :9000/mcp) for any MCP client.
from mcp.server.fastmcp import FastMCP
```

- [ ] **Step 5: `mcp_client.py` — MCP (client).** Replace:
```python
"""
import json
from contextlib import asynccontextmanager
```
with:
```python
"""
# ── Concept: MCP (CLIENT) ── converts MCP tool defs into our neutral ToolSpec + a dispatch that calls them over the protocol.
import json
from contextlib import asynccontextmanager
```

- [ ] **Step 6: `rag/ingest.py` — RAG.** Replace:
```python
"""
import json
```
with:
```python
"""
# ── Concept: RAG ── ingest pipeline: (fetch | synthetic) → chunk → embed → store into pgvector.
import json
```

- [ ] **Step 7: `rag/search.py` — Lexical + semantic search.** Replace:
```python
"""
import asyncio
```
with:
```python
"""
# ── Concept: LEXICAL + SEMANTIC SEARCH (PGVECTOR) ── tsvector lexical + vector cosine, fused with Reciprocal Rank Fusion in hybrid_search().
import asyncio
```

- [ ] **Step 8: `llm/base.py` — 2 banners.**

Banner A (LLM API, after docstring, before the `__future__` import — a comment before `from __future__` is valid Python). Replace:
```python
"""
from __future__ import annotations
```
with:
```python
"""
# ── Concept: LLM API + PROVIDER ABSTRACTION ── neutral LLMProvider/Message/ToolSpec/Usage; swap Gemini→Claude behind get_provider().
from __future__ import annotations
```

Banner B (prompt caching, at the `cached_tokens` field). Replace:
```python
    cached_tokens: int = 0   # normalized across providers (Gemini implicit cache / Claude cache read)
```
with:
```python
    # ── Concept: PROMPT CACHING ── cached_tokens flows to spans (cache_read_tokens) → /traces cache_hit_pct; honest 0% on Gemini free tier.
    cached_tokens: int = 0   # normalized across providers (Gemini implicit cache / Claude cache read)
```

- [ ] **Step 9: `llm/retry.py` — Retry / backoff (at `with_retry`).** Replace:
```python
def with_retry(max_attempts: int = 6, base_delay: float = 0.5, max_delay: float = 45.0):
```
with:
```python
# ── Concept: RETRY / BACKOFF ── exponential backoff + jitter on 429/5xx/timeouts; honors Gemini's RetryInfo.retryDelay.
def with_retry(max_attempts: int = 6, base_delay: float = 0.5, max_delay: float = 45.0):
```

- [ ] **Step 10: `skills.py` — Skills.** Replace:
```python
"""
from pathlib import Path
```
with:
```python
"""
# ── Concept: SKILLS ── filesystem SKILL.md, progressive disclosure: one-line descriptions in context, full body loaded on demand.
from pathlib import Path
```

- [ ] **Step 11: `observability.py` — Observability.** Replace:
```python
"""
import contextvars
```
with:
```python
"""
# ── Concept: OBSERVABILITY ── framework-free Trace/span() via contextvars; nested + concurrent spans parent correctly; cost attribution.
import contextvars
```

- [ ] **Step 12: `evals/runner.py` — Evals.** Replace:
```python
"""
import asyncio
```
with:
```python
"""
# ── Concept: EVALS ── run the golden set through the full pipeline; deterministic metrics + LLM-as-judge scoring.
import asyncio
```

- [ ] **Step 13: Verify — the table of contents.**

Run:
```bash
grep -rn "── Concept:" backend/app
```
Expected: **15 lines** across the files above, covering all 13 concepts (ORCHESTRATION, CONTEXT MANAGEMENT (SUBAGENTS), PARALLELISM, TOOLS (THE HAND-ROLLED LOOP), TOOLS (FUNCTION CALLING), MCP (SERVER), MCP (CLIENT), RAG, LEXICAL + SEMANTIC SEARCH (PGVECTOR), LLM API + PROVIDER ABSTRACTION, PROMPT CACHING, RETRY / BACKOFF, SKILLS, OBSERVABILITY, EVALS). Then confirm nothing broke:
```bash
docker compose up -d --build
curl -s localhost:8000/health          # expect {"status":"ok", ...}
docker compose exec backend python -c "import app.main"   # expect no output, exit 0
```
Expected: `/health` green, clean import (banners are comments — they cannot change behavior).

- [ ] **Step 14: Commit.**

```bash
git add backend/app
git commit -m "docs(structure): add greppable '── Concept:' signpost banners (15 placements)

One uniform header line per concept home so 'grep -rn \"── Concept:\"
backend/app' yields a table of contents covering all 13 concepts.
Comments only — no behavior change. Banners are placed at current file
paths and will travel with the files during the Task 3-7 moves.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Move `embeddings.py` + `seed_data.py` → `rag/`

**Files:**
- Move: `backend/app/embeddings.py` → `backend/app/rag/embeddings.py`
- Move: `backend/app/seed_data.py` → `backend/app/rag/seed_data.py`
- Modify: `backend/app/rag/search.py` (line 14 import)
- Modify: `backend/app/rag/ingest.py` (lines 9, 12 imports)

**Interfaces:** `embed`, `embed_one` (from `embeddings`) and `KB_ARTICLES`, `PAST_TICKETS` (from `seed_data`) become `app.rag.embeddings` / `app.rag.seed_data`. `embeddings.py`'s own import (`from app.config import settings`) is an absolute import to an unmoved module — unchanged. `seed_data.py` has no imports. No external callers exist outside `rag/` (grep-confirmed: only `rag/search.py` and `rag/ingest.py` import them).

- [ ] **Step 1: Move the two files with history preserved.**
```bash
git mv backend/app/embeddings.py backend/app/rag/embeddings.py
git mv backend/app/seed_data.py backend/app/rag/seed_data.py
```

- [ ] **Step 2: Update `rag/search.py` (line 14).** Replace:
```python
from app.embeddings import embed_one
```
with:
```python
from app.rag.embeddings import embed_one
```

- [ ] **Step 3: Update `rag/ingest.py` (lines 9 and 12).** Replace:
```python
from app.embeddings import embed
```
with:
```python
from app.rag.embeddings import embed
```
and replace:
```python
from app.seed_data import KB_ARTICLES, PAST_TICKETS
```
with:
```python
from app.rag.seed_data import KB_ARTICLES, PAST_TICKETS
```

- [ ] **Step 4: Verify.**
```bash
docker compose up -d --build
curl -s localhost:8000/health                          # expect {"status":"ok", ...}
docker compose exec backend python -c "import app.main; from app.rag.ingest import ingest_all; from app.rag.search import hybrid_search"   # exit 0
curl -s -X POST "localhost:8000/ingest?fetch=false&reset=true" | head -c 400   # synthetic-only ingest; expect a JSON summary (counts), no import error
docker compose logs backend --since 2m | grep -i "error\|traceback" || echo "no errors"
```
Expected: `/health` green; the import line succeeds; `POST /ingest` returns its normal JSON summary (this exercises both `seed_data` and `embeddings` through their new paths). `fetch=false` keeps it fast/offline (synthetic KB only).

- [ ] **Step 5: Commit.**
```bash
git add backend/app
git commit -m "refactor(rag): move embeddings.py and seed_data.py into rag/

The TEI client and the synthetic KB are RAG-only; grouping them under
rag/ makes folder=concept literal. Updates the two importers
(rag/search.py, rag/ingest.py). No behavior change.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Promote `agents/tools.py` → `tools/registry.py` (+ `tools/__init__.py` re-export)

**Files:**
- Move: `backend/app/agents/tools.py` → `backend/app/tools/registry.py`
- Create: `backend/app/tools/__init__.py`
- Modify: `backend/app/agents/loop.py` (line 7 import)
- Modify: `backend/app/mcp_server.py` (line 12 import — still at its current path; it moves in Task 6)

**Interfaces:** The Tools concept gets a top-level folder. `tools/__init__.py` re-exports the three names call sites use: `TOOL_SPECS`, `dispatch` (used by `agents/loop.py`), `_get_document` (used by `mcp_server.py`). `registry.py`'s own imports (`app.db`, `app.llm.base`, `app.rag.search`) are absolute to unmoved modules — unchanged.

- [ ] **Step 1: Create the package dir and move the module.**
```bash
mkdir -p backend/app/tools
git mv backend/app/agents/tools.py backend/app/tools/registry.py
```

- [ ] **Step 2: Create `backend/app/tools/__init__.py`** (re-export shim — keeps the public surface small and intentional):
```python
"""Tools (function calling) — the public surface for the registry.

Re-exports so call sites import `from app.tools import ...` rather than reaching
into `app.tools.registry`. See registry.py for the specs + dispatcher.
"""
from app.tools.registry import TOOL_SPECS, _get_document, dispatch  # noqa: F401

__all__ = ["TOOL_SPECS", "dispatch", "_get_document"]
```

- [ ] **Step 3: Update `agents/loop.py` (line 7).** Replace:
```python
from app.agents.tools import TOOL_SPECS, dispatch
```
with:
```python
from app.tools import TOOL_SPECS, dispatch
```

- [ ] **Step 4: Update `mcp_server.py` (line 12).** Replace:
```python
from app.agents.tools import _get_document
```
with:
```python
from app.tools import _get_document
```

- [ ] **Step 5: Verify.**
```bash
docker compose up -d --build
curl -s localhost:8000/health                     # expect {"status":"ok", ...}
docker compose exec backend python -c "import app.main; from app.tools import TOOL_SPECS, dispatch, _get_document"   # exit 0
curl -s -X POST localhost:8000/agent/answer -H 'content-type: application/json' \
  -d '{"question":"How do I issue a refund on a charge?"}' | head -c 400
docker compose logs backend --since 2m | grep -i "error\|traceback" || echo "no errors"
```
Expected: `/health` green; the re-export import succeeds; `POST /agent/answer` runs the tool loop and returns its normal JSON (this exercises `TOOL_SPECS` + `dispatch` through the new `app.tools` path). *(Note: the `mcp` container also imports `app.tools` via `mcp_server.py`; it is re-verified in Task 6 after the mcp move.)*

- [ ] **Step 6: Commit.**
```bash
git add backend/app
git commit -m "refactor(tools): promote agents/tools.py to tools/registry.py

Gives the Tools concept a top-level folder so 'where are the tools?' has
an obvious answer. tools/__init__.py re-exports TOOL_SPECS, dispatch,
_get_document, so agents/loop.py and mcp_server.py import from app.tools.
No behavior change.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Resolve the Skills collision — `skills.py` → `skills/loader.py` + `definitions/` + `_SKILLS_DIR` fix

**[coordinate with Phase C / spec 04]** — spec 04 reworks Skills. Do the *move* here; the rework lands later in the new location. Do not polish the loader beyond the one required constant change.

**Files:**
- Move: `backend/app/skills/policy-reply-formatter/` → `backend/app/skills/definitions/policy-reply-formatter/`
- Move: `backend/app/skills.py` → `backend/app/skills/loader.py`
- Create: `backend/app/skills/__init__.py`
- Modify: `backend/app/skills/loader.py` (`_SKILLS_DIR` constant — the **only** logic change in Phase A)

**Interfaces:** Today `skills.py` (code) sits beside `skills/` (data) and only works because `skills/` has no `__init__.py` so Python resolves `skills.py` first — fragile. After this task, `skills/` is a proper package: `loader.py` holds the code, `definitions/<name>/SKILL.md` holds the data, and `skills/__init__.py` re-exports `list_skills`, `load_skill`. The sole importer, `agents/orchestrator.py:25` (`from app.skills import load_skill`), is **unchanged** because the shim re-exports it. The `_SKILLS_DIR` constant must be repointed: before the move `Path(__file__).parent` is `app/` so `/ "skills"` is correct; after the move `loader.py` lives in `app/skills/` so `Path(__file__).parent` is `app/skills/` and the data now lives in `app/skills/definitions/` — hence `/ "definitions"`.

- [ ] **Step 1: Move the data into `definitions/` first, then move the loader in.** (Order matters: relocate the data subdir before turning `skills/` into a code package.)
```bash
mkdir -p backend/app/skills/definitions
git mv backend/app/skills/policy-reply-formatter backend/app/skills/definitions/policy-reply-formatter
git mv backend/app/skills.py backend/app/skills/loader.py
```

- [ ] **Step 2: Fix the `_SKILLS_DIR` constant in `skills/loader.py`.** Replace:
```python
_SKILLS_DIR = Path(__file__).parent / "skills"
```
with:
```python
# loader.py now lives inside app/skills/, so the SKILL.md data sits in the sibling definitions/ dir.
_SKILLS_DIR = Path(__file__).parent / "definitions"
```

- [ ] **Step 3: Create `backend/app/skills/__init__.py`** (re-export shim so `from app.skills import load_skill` in the orchestrator keeps working unchanged):
```python
"""Skills (progressive disclosure) — public surface for the SKILL.md loader.

Re-exports the loader so call sites keep `from app.skills import ...`.
Skill *data* lives in definitions/<name>/SKILL.md; the loader lives in loader.py.
"""
from app.skills.loader import list_skills, load_skill  # noqa: F401

__all__ = ["list_skills", "load_skill"]
```

- [ ] **Step 4: Verify.**
```bash
docker compose up -d --build
curl -s localhost:8000/health                    # expect {"status":"ok", ...}
docker compose exec backend python -c "import app.main; from app.skills import load_skill, list_skills; print(list_skills())"
```
Expected: the `print(list_skills())` line prints a non-empty list containing `policy-reply-formatter` (proving `_SKILLS_DIR` now resolves the moved `definitions/` data). Then confirm the skill is still injected end-to-end:
```bash
curl -s -X POST localhost:8000/agent/triage -H 'content-type: application/json' \
  -d '{"ticket":"My customer wants a refund on a duplicate charge — how should I respond?"}' | head -c 600
docker compose logs backend --since 2m | grep -i "error\|traceback" || echo "no errors"
```
Expected: `POST /agent/triage` returns its normal JSON draft (the resolver still loads `policy-reply-formatter`); no `skills` import error; `skills/` no longer collides with a `skills.py`.

- [ ] **Step 5: Commit.**
```bash
git add backend/app
git commit -m "refactor(skills): resolve skills.py/skills-dir collision into a package

skills.py -> skills/loader.py; skills/policy-reply-formatter ->
skills/definitions/policy-reply-formatter; skills/__init__.py re-exports
list_skills/load_skill so the orchestrator import is unchanged. Repoints
_SKILLS_DIR to the sibling definitions/ dir (the only logic change).
Move-only; the Skills rework (spec 04) lands here in Phase C.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: `mcp/` package + `docker-compose.yml` command (same commit)

**[coordinate with Phase C / spec 03]** — spec 03 reworks MCP (all three primitives). Do the *move* here; the rework lands later in `mcp/server.py`. Do not polish the server/client beyond the import path + the docstring run-command reference.

**Files:**
- Move: `backend/app/mcp_server.py` → `backend/app/mcp/server.py`
- Move: `backend/app/mcp_client.py` → `backend/app/mcp/client.py`
- Create: `backend/app/mcp/__init__.py`
- Modify: `backend/app/mcp/server.py` (docstring run-command reference)
- Modify: `backend/app/api_agent.py` (line 12 import — still at its current path; it moves in Task 7)
- Modify: `docker-compose.yml` (`mcp` service `command`) — **same commit**

**Interfaces:** Two loose siblings become one package. `mcp/server.py` runs via `python -m app.mcp.server` (its `if __name__ == "__main__": mcp.run(transport="streamable-http")` block is unchanged). `mcp/client.py` still exposes `mcp_session`, `list_tool_specs`, `make_dispatch`, consumed by `api_agent.py`. **Third-party-vs-local import note:** `server.py`'s `from mcp.server.fastmcp import FastMCP` and `client.py`'s `from mcp import ClientSession` / `from mcp.client.streamable_http import streamablehttp_client` are Python-3 absolute imports and resolve to the **installed** `mcp` library, not the new `app.mcp` package — verified in Step 6. Server's other imports (`from app.tools import _get_document` — already updated in Task 4 — and `from app.rag.search import hybrid_search`) and client's (`from app.config import settings`, `from app.llm.base import ToolSpec`) are unchanged. The compose service name stays `mcp`, so `settings.mcp_url` (`http://mcp:9000/mcp`) is unchanged.

- [ ] **Step 1: Create the package and move both files.**
```bash
mkdir -p backend/app/mcp
git mv backend/app/mcp_server.py backend/app/mcp/server.py
git mv backend/app/mcp_client.py backend/app/mcp/client.py
```

- [ ] **Step 2: Create `backend/app/mcp/__init__.py`** (empty package marker — no re-export needed; callers use the full submodule path):
```python
"""MCP (Model Context Protocol) — server + client as one package.

server.py runs as its own container (`python -m app.mcp.server`, :9000/mcp);
client.py adapts MCP tools into the neutral ToolSpec/dispatch the agent loop uses.
"""
```

- [ ] **Step 3: Update the run-command reference in `mcp/server.py`'s docstring.** Replace:
```python
Run as its own container: `python -m app.mcp_server` (see docker-compose `mcp` service).
```
with:
```python
Run as its own container: `python -m app.mcp.server` (see docker-compose `mcp` service).
```

- [ ] **Step 4: Update `api_agent.py` (line 12).** Replace:
```python
from app.mcp_client import list_tool_specs, make_dispatch, mcp_session
```
with:
```python
from app.mcp.client import list_tool_specs, make_dispatch, mcp_session
```

- [ ] **Step 5: Update the `mcp` service command in `docker-compose.yml`** (same commit). Replace:
```yaml
    command: ["python", "-m", "app.mcp_server"]
```
with:
```yaml
    command: ["python", "-m", "app.mcp.server"]
```

- [ ] **Step 6: Verify (recreate the `mcp` container so the new command takes effect).**
```bash
docker compose up -d --build
docker compose ps                        # expect mcp container Up (not restarting/exited)
docker compose logs mcp --since 2m | grep -i "error\|traceback\|no module" || echo "no errors"
# Prove the local package does NOT shadow the installed mcp library, and the module loads:
docker compose exec mcp python -c "from mcp.server.fastmcp import FastMCP; import app.mcp.server, app.mcp.client; print('mcp ok')"
curl -s localhost:8000/health            # expect {"status":"ok", ...}
docker compose exec backend python -c "import app.main; from app.mcp.client import mcp_session"   # exit 0
# End-to-end MCP path (backend calls the mcp server over the protocol):
curl -s -X POST localhost:8000/agent/answer-mcp -H 'content-type: application/json' \
  -d '{"question":"How do I issue a refund on a charge?"}' | head -c 400
```
Expected: `mcp` container is Up and boots `Streamable HTTP` on `:9000/mcp`; the shadow-check prints `mcp ok`; `POST /agent/answer-mcp` returns its normal JSON (the loop ran against tools discovered over MCP).

- [ ] **Step 7: Commit** (code move + the one compose line together, so the running command never points at a missing module).
```bash
git add backend/app docker-compose.yml
git commit -m "refactor(mcp): move mcp_server/mcp_client into an mcp/ package

Two loose siblings -> app/mcp/{server,client}.py with __init__. Updates
api_agent's client import and the docker-compose mcp command in the SAME
commit (python -m app.mcp_server -> app.mcp.server) so the container's
command never points at a missing module. Absolute imports still resolve
to the installed 'mcp' library (verified). Move-only; the 3-primitive
rework (spec 03) lands here in Phase C.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Group `api_*.py` → `api/` package (+ `main.py` wiring) — last, touches routing

**Files:**
- Move: `backend/app/api_agent.py` → `backend/app/api/agent.py`
- Move: `backend/app/api_evals.py` → `backend/app/api/evals.py`
- Move: `backend/app/api_llm.py` → `backend/app/api/llm.py`
- Move: `backend/app/api_tickets.py` → `backend/app/api/tickets.py`
- Move: `backend/app/api_traces.py` → `backend/app/api/traces.py`
- Create: `backend/app/api/__init__.py`
- Modify: `backend/app/main.py` (lines 13–17, the 5 router imports)
- Modify: `backend/app/api/agent.py` (line 10 import of `save_ticket`; and its line-3 docstring reference)

**Interfaces:** The five loose HTTP modules become one `api/` package. **Every router `prefix=`/`tags=` is unchanged** (`/agent`, `/evals`, `/llm`, `/tickets`, `/traces`), so the HTTP contract is byte-identical and the frontend (URL-only) is unaffected. `include_router(...)` order in `main.py` is unchanged. No name collision: `app.api.evals` / `app.api.llm` are distinct from the existing `app.evals` / `app.llm` packages. `api/agent.py`'s other imports (`app.agents.loop`, `app.agents.orchestrator`, `app.config`, and `app.mcp.client` — already updated in Task 6) are unchanged.

- [ ] **Step 1: Create the package and move all five modules.**
```bash
mkdir -p backend/app/api
git mv backend/app/api_agent.py   backend/app/api/agent.py
git mv backend/app/api_evals.py   backend/app/api/evals.py
git mv backend/app/api_llm.py     backend/app/api/llm.py
git mv backend/app/api_tickets.py backend/app/api/tickets.py
git mv backend/app/api_traces.py  backend/app/api/traces.py
```

- [ ] **Step 2: Create `backend/app/api/__init__.py`** (empty package marker):
```python
"""HTTP surface — thin FastAPI routers, one module per resource.

agent.py (/agent) · traces.py (/traces) · tickets.py (/tickets) ·
evals.py (/evals) · llm.py (/llm). Prefixes are the public contract — unchanged.
"""
```

- [ ] **Step 3: Rewire the 5 router imports in `main.py` (lines 13–17).** Replace:
```python
from app.api_agent import router as agent_router
from app.api_evals import router as evals_router
from app.api_llm import router as llm_router
from app.api_tickets import router as tickets_router
from app.api_traces import router as traces_router
```
with:
```python
from app.api.agent import router as agent_router
from app.api.evals import router as evals_router
from app.api.llm import router as llm_router
from app.api.tickets import router as tickets_router
from app.api.traces import router as traces_router
```

- [ ] **Step 4: Update the intra-package import in `api/agent.py` (line 10).** Replace:
```python
from app.api_tickets import save_ticket
```
with:
```python
from app.api.tickets import save_ticket
```

- [ ] **Step 5: Update the stale docstring reference in `api/tickets.py` (line 3)** (comment accuracy only). Replace:
```python
Mirrors the read-side conventions of api_traces.py (APIRouter + asyncpg pool + .isoformat()).
```
with:
```python
Mirrors the read-side conventions of api/traces.py (APIRouter + asyncpg pool + .isoformat()).
```

- [ ] **Step 6: Verify — all 5 prefixes + import graph + frontend unaffected.**
```bash
docker compose up -d --build
curl -s localhost:8000/health                                  # expect {"status":"ok", ...}
docker compose exec backend python -c "import app.main"        # imports all 5 routers; exit 0
# All 5 prefixes still mounted (paths byte-identical):
curl -s localhost:8000/openapi.json | python3 -c "import sys,json; p=json.load(sys.stdin)['paths']; print(sorted({k.split('/')[1] for k in p}))"
curl -s localhost:8000/traces?limit=1 | head -c 200            # /traces
curl -s localhost:8000/tickets?limit=1 | head -c 200           # /tickets
curl -s localhost:8000/evals | head -c 200                     # /evals
# Frontend is untouched and still typechecks/builds:
docker compose exec frontend npm run build
git diff --name-only HEAD~7 -- frontend/ | head             # expect EMPTY (no frontend file changed across Phase A)
```
Expected: `/health` green; the openapi path set includes `agent`, `evals`, `llm`, `tickets`, `traces` (all prefixes present); each `curl` returns its normal JSON; `npm run build` succeeds; the frontend diff across all seven Phase-A commits is empty.

- [ ] **Step 7: Commit.**
```bash
git add backend/app
git commit -m "refactor(api): group api_*.py into an api/ package

Five loose route modules -> app/api/{agent,evals,llm,tickets,traces}.py
with __init__. main.py's 5 router imports and agent.py's save_ticket
import repointed. Every prefix/tags and the include_router order are
unchanged, so the HTTP contract is byte-identical and the frontend
(URL-only) is untouched.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage (spec 01 requirements → task):**
- Discoverability: new `backend/app/README.md` folder=concept table + cross-cutting section + grep command → Task 1 Step 1. ✅
- Discoverability: `docs/CONCEPTS.md` split into two tables (Concept modules / Cross-cutting) with a Signpost column + updated moved paths → Task 1 Step 2. ✅
- Discoverability: top `README.md` repo-map fenced tree under the concept-map link → Task 1 Step 3. ✅
- Signpost banners at 15 placements covering all 13 concepts → Task 2 Steps 1–12; grep verification Step 13. ✅ (orchestrator ×3, base ×2, MCP server+client, Tools registry+loop → 15 lines / 13 concepts.)
- `embeddings.py` + `seed_data.py` → `rag/` with the 3 importer edits → Task 3. ✅ (spec verify `POST /ingest` → Step 4.)
- `agents/tools.py` → `tools/registry.py` + `tools/__init__.py` re-export (`TOOL_SPECS, dispatch, _get_document`) → Task 4. ✅ (spec verify `POST /agent/answer`.)
- Skills collision: `skills.py`→`skills/loader.py`, data→`skills/definitions/`, `skills/__init__.py` re-export, `_SKILLS_DIR`→`"definitions"` (only logic change) → Task 5. ✅ (spec verify `POST /agent/triage`; [coordinate Phase C/spec 04] flagged.)
- `mcp_*.py`→`mcp/` package + `docker-compose.yml` command in the SAME commit → Task 6. ✅ (spec verify mcp boots + `POST /agent/answer-mcp`; [coordinate Phase C/spec 03] flagged; third-party-`mcp`-shadow check included.)
- `api_*.py`→`api/` package + `main.py` 5 router imports, every `prefix=` unchanged → Task 7. ✅ (spec verify all 5 prefixes + frontend end-to-end.)
- Exact blast-radius import-edit list from the spec table reproduced (File Structure table) and each edit is a concrete Modify step with exact line + old→new string. ✅
- Sequencing safest→riskiest (docs → banners → rag → tools → skills → mcp → api) matches spec §Sequencing 1–7. ✅

**Global-constraint coverage:** No behavior change (comments/moves/shims only). HTTP contract byte-identical — prefixes/tags/order unchanged, asserted + verified via openapi in Task 7. DB schema untouched. `schema.sql` explicitly stays beside `db.py`. Frontend untouched — asserted, and verified by `git diff --name-only HEAD~7 -- frontend/` (empty) + `npm run build`. Only one `docker-compose.yml` line changes (Task 6). Re-export shims (`tools/__init__.py`, `skills/__init__.py`) keep the orchestrator/loop imports minimal. ✅

**Type / path consistency:** All move sources verified to exist (`find backend/app`); all import lines verified against the live grep (e.g., `rag/search.py:14`, `rag/ingest.py:9,12`, `agents/loop.py:7`, `mcp_server.py:12`, `api_agent.py:10,12`, `main.py:13-17`, `skills.py:10` `_SKILLS_DIR`). `tools/__init__.py` re-exports the exact names call sites use (`_get_document` is the real symbol `mcp_server.py` imports, not `get_document`). `skills/__init__.py` re-exports `list_skills, load_skill` (both real, per `skills.py`). Compose service name stays `mcp` so `settings.mcp_url` is untouched. Banner anchor strings taken verbatim from file reads (docstring-close `"""` + first import line per file; the `cached_tokens`, `with_retry`, `_classify`, and `asyncio.gather` lines quoted exactly). ✅

**Placeholder scan:** No TBD/TODO/"handle errors"/placeholder steps. Every step gives complete code or an exact command; every task ends with concrete manual verification (expected output stated) + a `git commit`. ✅

**No test framework:** Confirmed — verification is entirely manual via `docker compose`, `curl`, `python -c "import app.main"`, `grep`, and `npm run build`. No pytest/vitest/TDD anywhere. ✅
