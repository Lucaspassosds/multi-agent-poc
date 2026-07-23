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
