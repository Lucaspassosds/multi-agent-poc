# 00 — Overview

## Purpose
A framework-free, multi-agent system that **triages incoming support tickets** and **drafts cited
resolutions**, built to demonstrate every AI-engineering concept in the requirements. Domain:
**payments support** (knowledge base = crawled Stripe public docs).

## Non-goals
- Not a production support desk. No auth, no multi-tenancy, no real ticket system integration.
- Not a demonstration of *a* framework (LangChain/CrewAI/LangGraph are deliberately avoided for
  orchestration). We only use LangChain's **text-splitter utility** — a string helper, not orchestration.

## Locked decisions
| # | Decision | Choice | Rationale |
|---|---|---|---|
| 1 | Runtime isolation | **Docker for all architectural deps** (fallback: `uv` for backend) | Reproducible, matches user preference |
| 2 | Embedding model | **`bge-small-en-v1.5`** (384-dim, English, 512-token) | Light/fast on CPU, TEI-native, no prefix footguns; English KB makes multilingual moot. Upgrade path: `nomic-embed-text-v1.5` |
| 3 | Embedding serving | **TEI** (HuggingFace Text Embeddings Inference) container | Keeps backend light; HTTP contract |
| 4 | KB source | **Crawl Stripe public docs** via Crawl4AI → markdown | Realistic billing/refund tickets |
| 5 | Chunking | **`RecursiveCharacterTextSplitter`** (`langchain-text-splitters`) | User request; standalone, no full framework |
| 6 | Past-ticket corpus | **~30 synthetic resolved tickets** | Richer retrieval (KB + precedent) |
| 7 | Language | **English** | Easiest to source docs + demo; English-only KB is why `bge-small` (not a multilingual model) suffices |
| 8 | LLM | **Provider abstraction** (`LLMProvider` iface). Now: **Gemini free tier** (all roles on `flash-lite-latest` — only model with generous free quota). Target: **Claude** (haiku/sonnet/opus) via one `LLM_PROVIDER` swap | Anthropic credits blocked; ~11/13 concepts are provider-agnostic. Same cost-tiering either way. See spec 03 |
| 9 | Vector store | **Postgres 16 + pgvector** (no other vector DB) | requirement |
| 10 | Lexical search | **Postgres full-text (`tsvector`/`ts_rank`)** | requirement (léxica in pg) |

## Architecture
```
React (Vite) ──HTTP/SSE──▶ FastAPI ──▶ Agent layer (pure Python, no framework)
 Triage / Observability      /ingest      orchestrator loop
 / Evals screens             /triage(SSE) ├─ classifier (cheap tier)
                             /traces      ├─ retriever ×N (parallel)
                             /evals       ├─ resolver (mid tier)
                                          └─ critic (top tier)
                                               │ tools: hybrid_search, get_doc, get_ticket, escalate
   docker services:                            │ (also exposed via MCP server)
   postgres+pgvector ─ TEI(bge-small-en-v1.5) ─ Crawl4AI ─ backend ─ frontend
```

Ingest pipeline: **Crawl4AI (url→md) → RecursiveCharacterTextSplitter (md→chunks) → TEI (chunk→vector) → Postgres (embedding + tsvector)**.

## Demo script (for the review)
1. Submit: *"I was charged twice for my subscription this month, please refund the duplicate."*
2. Live timeline: classify → retrieve (parallel) → draft → critic → final cited answer.
3. Observability dashboard: per-step latency, tokens, **prompt-cache savings**, retries.
4. Force an API error → watch **retry/backoff** recover.
5. Run **evals** → accuracy + LLM-as-judge scores.

## Concept → phase coverage
| Topic | Phase | Topic | Phase |
|---|---|---|---|
| Orquestração sem framework | 4 | Claude API | 2 |
| Subagentes / gestão de contexto | 4 | Retry | 2 |
| Paralelismo | 4 | Prompt caching | 2 |
| RAG | 1 | Tools | 3 |
| Pesquisa léxica + semântica (pgvector) | 1 | MCP | 5 |
| Observabilidade | 6 | Skills | 5 |
| Evals | 7 | | |

## 🎓 Glossary (plain-English, for the walkthrough)
- **Embedding / vector**: a list of numbers (here, 384 of them) representing the *meaning* of text. Similar meanings → nearby vectors.
- **Semantic search**: find text by *meaning* (compare embeddings). Handles synonyms/paraphrase.
- **Lexical search**: find text by *matching words* (Postgres full-text). Great for exact terms/IDs.
- **Hybrid search (RRF)**: run both, then merge the two ranked lists with Reciprocal Rank Fusion so the best of each wins.
- **RAG**: Retrieval-Augmented Generation — fetch relevant text first, then let the model answer *grounded* in it (fewer hallucinations, citations).
- **Tool (function calling)**: a Python function the model can choose to call, described by a JSON schema.
- **Agent**: a loop where the model calls tools, reads results, and decides the next step until done.
- **Subagent**: a *child* agent with its own fresh context window, given one focused job; only its short summary returns to the parent — keeps the parent's context small.
- **Orchestrator**: the parent agent that plans and delegates to subagents.
- **MCP**: Model Context Protocol — a standard way to expose tools/data so *any* MCP-aware client can use them.
- **Skill**: a packaged, reusable capability (instructions + assets) the model can invoke.
- **Prompt caching**: mark stable prompt parts as cacheable so repeated calls are cheaper/faster.
- **Eval**: an automated test of answer/agent quality (deterministic metrics + LLM-as-judge).
- **Observability / trace / span**: recording each step (a span) of a run (a trace) — latency, tokens, cost, errors.
- **Retry / backoff**: on transient failures (rate limits, overload), wait a growing interval (+jitter) and try again.
