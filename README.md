# Multi-Agent Support Triage POC

A **framework-free** multi-agent system that triages support tickets and drafts cited resolutions —
built to demonstrate a set of AI-engineering concepts (orchestration, RAG, hybrid search, MCP, Skills,
observability, evals, retry, parallelism, caching).

- **Specs** (source of truth): [`specs/`](specs/) — read `specs/00-overview.md` first.
- **Task tracker**: [`tasks/todo.md`](tasks/todo.md).
- **Stack**: FastAPI (Python 3.12) · React + Vite · Postgres 16 + pgvector · TEI embeddings · LLM behind a
  provider interface (**Gemini free tier** now, **Claude** later).

## Prerequisites
- Docker + Docker Compose
- A free **Gemini API key** — https://aistudio.google.com → *Get API key* (no credit card). Needed from Phase 2.

## Setup
```bash
cp .env.example .env        # then paste your GEMINI_API_KEY into .env
docker compose up -d --build
```
This starts four services: `db`, `embeddings`, `backend`, `frontend`.
(The `crawler` is **on-demand** — see below.)

## Verify (Phase 0)
```bash
curl localhost:8000/health          # {"status":"ok","db":true,"tei":true,...}
curl localhost:8080/health          # TEI health (once the model finishes loading)
open http://localhost:5173          # UI placeholder showing live backend health
```
> On first boot, `embeddings` downloads the model (~130 MB), so `tei` may report `false`
> for a minute — `/health` will flip to `true` once it's ready.

## On-demand crawler (Phase 1)
The crawler runs Chromium and is memory-heavy, so it is **not** started by default:
```bash
docker compose --profile crawl up crawler
```

## Services & ports
| Service | URL | Purpose |
|---|---|---|
| backend | http://localhost:8000 | FastAPI + agent layer |
| frontend | http://localhost:5173 | React UI |
| embeddings (TEI) | http://localhost:8080 | bge-small-en-v1.5 (384-dim) |
| db | localhost:5433 | Postgres 16 + pgvector (host 5433 to avoid a local Postgres on 5432) |
| crawler | http://localhost:11235 | Crawl4AI (on-demand) |
