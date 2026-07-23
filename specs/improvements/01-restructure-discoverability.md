# 01 — Restructure & Discoverability

## Purpose
Fix the manager's #1 complaint — *"I couldn't find each concept in the code."* Make **folder =
concept** literally true for the real modules, give the cross-cutting techniques a named home + a
greppable signpost (not a fake folder), and add a discoverability layer that sits where a reviewer
actually looks. Zero behavior change: this spec only moves, renames, and documents.

## Root cause (what's wrong today)
`backend/app/` root is a flat bag that mixes three kinds of file, so the eye can't separate a
concept-module from plumbing from an HTTP demo route:
- **Skills** — `skills.py` (the loader code) sits beside `skills/` (the data dir). Works today only
  because `skills/` has no `__init__.py` and Python resolves `skills.py` first — fragile and confusing.
- **MCP** — split across two loose siblings `mcp_client.py` + `mcp_server.py`, no obvious home.
- **Tools** — the function-calling registry is buried at `agents/tools.py`; "where are the tools?"
  has no top-level answer.
- Five loose `api_*.py` route modules and four loose infra files (`embeddings.py`, `seed_data.py`,
  `db.py`, `config.py`) clutter the root further.

`agents/`, `llm/`, `rag/`, `evals/`, `observability.py` are **already clean** and must NOT be churned.

## Contract — target tree (`backend/app/`)
```
backend/app/
├── main.py  config.py  db.py  schema.sql        # entrypoint + plumbing (unchanged; schema.sql STAYS by db.py)
├── llm/        base.py factory.py gemini.py retry.py      # CONCEPT: Claude/Gemini API + retry home
├── rag/        fetch chunking ingest search + embeddings.py + seed_data.py   # (last two MOVED in)
├── agents/     orchestrator.py loop.py                    # CONCEPT: orchestration / subagents / parallelism
├── tools/      registry.py (+__init__.py)                 # ← PROMOTED from agents/tools.py
├── mcp/        client.py server.py (+__init__.py)         # ← two loose files → one package
├── skills/     loader.py + definitions/<name>/SKILL.md (+__init__.py)   # collision resolved: code vs data
├── observability/  (or keep observability.py)             # OPTIONAL file→package — recommend SKIP
├── evals/      golden.json judge.py metrics.py runner.py  # unchanged
└── api/        llm.py agent.py traces.py tickets.py evals.py (+__init__.py)   # ← api_*.py grouped
```

### Move / rename table
| # | Current | New | Why |
|---|---|---|---|
| 1 | `app/mcp_client.py` | `app/mcp/client.py` | MCP gets one package |
| 2 | `app/mcp_server.py` | `app/mcp/server.py` | run via `python -m app.mcp.server` |
| 3 | `app/skills.py` | `app/skills/loader.py` (+`__init__.py`) | resolve code/data collision |
| 4 | `app/skills/policy-reply-formatter/` | `app/skills/definitions/policy-reply-formatter/` | separate data from loader |
| 5 | `app/agents/tools.py` | `app/tools/registry.py` (+`__init__.py`) | promote the Tools concept |
| 6 | `app/embeddings.py` | `app/rag/embeddings.py` | TEI client is RAG-only |
| 7 | `app/seed_data.py` | `app/rag/seed_data.py` | synthetic KB is RAG-only |
| 8–12 | `app/api_*.py` | `app/api/*.py` | de-clutter root; group HTTP surface |

**Deliberately NOT moved:** `agents/orchestrator.py`, `agents/loop.py`, all `llm/`, all `evals/`,
`db.py`, `config.py`, `schema.sql`, `main.py`. `schema.sql` is loaded via
`Path(__file__).parent / "schema.sql"` and holds *all* tables (shared infra, not RAG-specific).

## Behavior — concept → home map (all 13 must be unambiguous)
| # | Concept | Home | Type |
|---|---|---|---|
| 1 | Orchestration without a framework | `agents/orchestrator.py` | module |
| 2 | MCP | `mcp/` (server + client) | module |
| 3 | RAG | `rag/` | module |
| 4 | Observability | `observability(.py)` + `api/traces.py` | module |
| 5 | Evals | `evals/` + `api/evals.py` | module |
| 6 | Skills | `skills/loader.py` + `skills/definitions/*/SKILL.md` | module |
| 7 | Tools (function calling) | `tools/registry.py` + `agents/loop.py` | module |
| 8 | Lexical + semantic search in pgvector | `rag/search.py` + `schema.sql` | module |
| 9 | Claude/Gemini API + provider abstraction | `llm/` | module |
| 10 | Context management via subagents | `agents/orchestrator.py` (`_classify/_plan/_retrieve/_resolve/_critique`) | cross-cutting |
| 11 | Retry / backoff | `llm/retry.py` → `with_retry()` | cross-cutting (dedicated file) |
| 12 | Parallelism | `agents/orchestrator.py` → `asyncio.gather(...)` | cross-cutting |
| 13 | Prompt caching | `llm/base.py` `Usage.cached_tokens` → `observability` → `api/traces.py` | cross-cutting |

### Signpost banner convention
Every concept home gets one uniform, greppable header line:
```python
# ── Concept: PARALLELISM ── fan-out retrieval; overlap is provable on span timestamps.
```
So `grep -rn "── Concept:" backend/app` yields a table of contents. The 4 cross-cutting techniques
live in just two places (`agents/orchestrator.py` and `llm/`), so they're findable without folders.

### Discoverability layer (do this even if the moves are deferred)
1. **NEW `backend/app/README.md`** *(highest leverage — sits where the reviewer got lost)*: a
   "folder = concept" table (one row per top-level folder → concept → start-here symbol) + a
   **Cross-cutting techniques** section listing the 4 homes and the `grep` command.
2. **UPGRADE `docs/CONCEPTS.md`**: split into two tables — *Concept modules* (folder) and
   *Cross-cutting techniques* (file + signpost); add a **Signpost** column; update moved paths.
3. **Top `README.md`**: add a short **Repo map** fenced tree under the existing concept-map link.

## Blast radius (grepped — this is the entire edit surface)
| Move | Files to update | Change |
|---|---|---|
| mcp package | `api_agent.py`, `docker-compose.yml` (mcp `command`) | import path + `python -m app.mcp.server` |
| tools promote | `agents/loop.py`, `mcp/server.py` | import from `app.tools`; `tools/__init__.py` re-exports `TOOL_SPECS, dispatch, get_document` |
| skills collision | (orchestrator import unchanged) | `skills/__init__.py` re-exports; loader constant `_SKILLS_DIR → "definitions"` — **only logic change** |
| embeddings/seed → rag | `rag/ingest.py`, `rag/search.py` | import paths |
| api group | `main.py` (5 router imports), `api_agent.py` | import paths; every `prefix=`/`tags=` **unchanged** |

**Untouched by design:** HTTP contract (all prefixes identical), DB schema, and the **entire
frontend** (it references the backend only by URL path, never by Python module). Only
`docker-compose.yml`'s mcp `command` changes; the `backend` bind-mount and Dockerfile `COPY` are
directory-level, so intra-`app/` moves need no Dockerfile change.

## Sequencing (safest → riskiest; each step independently committable + runnable)
1. Discoverability layer (pure additions).
2. Signpost banners (comments only).
3. `embeddings.py` + `seed_data.py` → `rag/` (verify `POST /ingest`).
4. `agents/tools.py` → `tools/registry.py` + re-export (verify `POST /agent/answer`).
5. `skills.py` → `skills/loader.py` + `definitions/` + `_SKILLS_DIR` fix (verify `POST /agent/triage` still injects the skill). **Coordinate with spec 04** — the Skills rework lands new code here.
6. `mcp/` package + docker-compose command, same commit (verify `mcp` boots on `:9000/mcp` and `POST /agent/answer-mcp`). **Coordinate with spec 03**.
7. `api/` package — last; touches `main.py` wiring (verify all 5 prefixes + frontend end-to-end).

> **Sequencing note (cross-spec):** steps 5 and 6 move code that specs 04 (Skills) and 03 (MCP)
> also rewrite. Do the *move* first (this spec), then land the *rework* in the new location — do
> not polish the old code that is about to be replaced. See `00-overview.md` § "Order of operations."

## Acceptance
- [ ] `grep -rn "── Concept:" backend/app` prints one line per concept, all 13 covered.
- [ ] `backend/app/README.md` exists; every top-level folder maps to a concept.
- [ ] `docker compose up` → `/health` green; all 5 API prefixes respond; frontend loads end-to-end.
- [ ] No import errors; `skills/` no longer collides with a `skills.py`.
- [ ] Frontend and DB schema demonstrably unchanged (no diff outside `backend/app/` structure + docs + one compose line).

## Open questions
- Promote `observability.py` to a package? **Recommend skip** unless it grows (spec 06 may grow it).
- Keep re-export shims (`tools/__init__.py`, `skills/__init__.py`) permanently, or update call sites
  directly? Recommend shims — smaller blast radius, and they read as intentional public surfaces.
