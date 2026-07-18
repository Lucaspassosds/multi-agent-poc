# 01 — Infrastructure (Phase 0)

## Purpose
Reproducible, Docker-first environment. `docker compose up` must bring the whole stack online.

## Services (docker-compose)
| Service | Image | Host port | Notes |
|---|---|---|---|
| `db` | `pgvector/pgvector:pg16` | 5432 | Postgres 16 + pgvector extension |
| `embeddings` | `ghcr.io/huggingface/text-embeddings-inference:cpu-latest` | 8080→80 | `--model-id BAAI/bge-small-en-v1.5`; model cached in a named volume. Pin tag once working |
| `crawler` | `unclecode/crawl4ai:latest` | 11235 | Crawl4AI REST API. ⚠️ verify exact endpoint/payload at Phase 1 |
| `backend` | local `Dockerfile` (`python:3.12-slim` + `uv`) | 8000 | FastAPI + agent layer; volume-mount source for reload |
| `frontend` | local `Dockerfile` (`node:24-slim`) | 5173 | Vite dev server; volume-mount source for HMR |

## Contract
- `.env` (git-ignored) provides secrets/config; `.env.example` documents them:
  ```
  LLM_PROVIDER=gemini                     # gemini (now) | anthropic (once credits unblock)
  GEMINI_API_KEY=...                      # free key from aistudio.google.com (no card) — active now
  ANTHROPIC_API_KEY=sk-ant-...            # deferred until credits unblock
  DATABASE_URL=postgresql://poc:poc@db:5432/poc
  TEI_URL=http://embeddings:80
  CRAWL4AI_URL=http://crawler:11235
  # Model IDs per role — the set matching LLM_PROVIDER is the active one
  MODEL_CLASSIFY=gemini-flash-lite-latest
  MODEL_RESOLVE=gemini-flash-latest
  MODEL_CRITIC=gemini-3.5-flash
  # anthropic set (swap in after LLM_PROVIDER=anthropic):
  #   MODEL_CLASSIFY=claude-haiku-4-5-20251001
  #   MODEL_RESOLVE=claude-sonnet-5
  #   MODEL_CRITIC=claude-opus-4-8
  EMBED_DIM=384
  ```
- Backend exposes `GET /health` → `{"status":"ok","db":true,"tei":true}` (checks DB + TEI reachability).
- All services share a compose network; backend reaches others by service name (`db`, `embeddings`, `crawler`).

## Behavior / acceptance
- [ ] `docker compose up` starts all 5 services without error.
- [ ] `curl localhost:8000/health` → `db:true, tei:true`.
- [ ] `curl localhost:8080/health` (TEI) responds; a test `POST /embed` returns a 384-length vector.
- [ ] Frontend loads a placeholder page at `localhost:5173`.
- [ ] `.env` is git-ignored; `.env.example` committed.

## 🎓 Teaching notes
- Why containers per concern: the embedding model and browser-based crawler have heavy, conflicting
  dependencies (PyTorch, Chromium). Isolating them keeps the backend image small and startup fast.
- Service-name networking: inside compose, `http://embeddings:80` resolves via Docker DNS — no localhost.

## Open questions
- Confirm TEI `cpu-latest` tag pulls cleanly and serves `bge-small-en-v1.5` (~130 MB model). Expected trivial on CPU.
- Upgrade path if we want more quality later: `nomic-embed-text-v1.5` (768-dim, 8192 ctx, Matryoshka) — requires `search_query:`/`search_document:` prefixes; would change `EMBED_DIM=768`.
