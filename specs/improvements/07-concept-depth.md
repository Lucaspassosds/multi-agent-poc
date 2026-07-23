# 07 — Concept Depth (the remaining concepts, made substantial)

## Purpose
Answer the manager's *"scope too small to explore each concept deeply"* for the concepts **not** owned
by specs 03–06. Constraint held throughout: **deepen the existing agents — do NOT add new agents to the
orchestration graph.** The graph stays `classify → retrieve×N (parallel) → resolve → critique → revise`;
we make those nodes smarter, and we make each technique *visible*.

## Contract — per concept

### Orchestration without a framework `(topic: orchestration)`
- **Bounded conditional revise loop** *inside the existing critique node*: `max_revisions`, re-critique
  after each revision, exit on pass-or-limit. This is the control flow a framework (LangGraph) would
  hand you — hand-rolled, no new node.
- Render the pipeline as a **typed nodes+edges diagram** (declared graph → diagram) so the structure is
  legible at a glance (feeds spec 08).

### RAG `(topic: RAG)` + lexical+semantic search `(topic: pgvector)`
- **Reranker over the fused top-k** (LLM-rerank or a small cross-encoder) — the single biggest RAG
  quality win. *Not* a training pipeline.
- **Query decomposition / HyDE** feeding the existing parallel retrievers (ties to parallelism).
- **A 3rd source type** (e.g. Stripe API reference / changelog) added to the KB.
- **Fusion transparency**: surface each result's lexical rank · semantic rank · fused RRF score, and a
  "why this result" explanation — all still in **pgvector, no external vector DB**.
- **Char-offset citation grounding** so citations point at exact spans (feeds clickable chips, spec 08).

### Parallelism `(topic: parallelism)`
- Wider fan-out (pairs with query decomposition).
- **Sequential-vs-parallel wall-clock comparison** surfaced in the trace (the waterfall already proves
  overlap on timestamps; make the speedup a number).

### Context management via subagents `(topic: context-mgmt)`
- **Context ledger**: quantify the orchestrator's context (isolated per-subagent windows + the compact
  summary each returns) vs a naive single-growing-context baseline — as a KPI. This was already an
  acceptance goal; make it a visible metric.

### Retry / backoff `(topic: retry)`
- **Chaos toggle** that forces a 429 so backoff + recovery is *seen* in a real trace.
- Show retry count / delay / jitter and retryable-vs-non-retryable classification.

### Claude/Gemini API `(topic: llm-api)`
- **A/B the same run on both providers** side by side (once Claude is unblocked).
- Visible **per-role model tiering**; structured outputs everywhere; document the one-flag swap.

### Prompt caching `(topic: caching)`
- Keep the **honest free-Gemini disclosure** (`/llm/cache-demo` explains 0% on free tier).
- Make the prompt **cache-correct**: stable KB+system prefix *before* the volatile ticket; **no
  timestamps/UUIDs in the cached prefix** — so the Claude swap is a deterministic win.
- On the Claude swap: show `cache_read_input_tokens` + $ saved live + a cache-warming step.

### Evals `(topic: evals)`
- Expand the golden set **20 → ~45**, including **adversarial** cases.
- **Failure taxonomy**: hallucinated policy · missed citation · wrong category · over/under-escalation —
  per-category breakdown.
- **Regression gating** vs a stored baseline (fail the run if quality drops).
- Surface the **judge's reasoning** per case.
- Push all of the above into Langfuse as **scores** (spec 06).

## 🎓 Teaching note
Depth ≠ breadth. Each upgrade makes an *existing* concept observably substantial — a reranked retrieval,
a caching win you can measure, a retry you can watch fail-and-recover, an eval that gates regressions —
rather than adding surface area. That is exactly the "explore each concept deeply" the manager asked for.

## Acceptance
- [ ] Revise loop is bounded (`max_revisions`) and re-critiques; no new orchestration node added.
- [ ] Reranker measurably reorders results on ≥1 golden case; fusion scores are inspectable.
- [ ] Chaos toggle produces a trace showing backoff and eventual success.
- [ ] Context ledger reports a real token delta vs the naive baseline.
- [ ] Golden set ≥45 cases; failure taxonomy + regression gate operational; scores in Langfuse.
- [ ] Cached prefix contains no volatile tokens (verified); caching KPI is honest per provider.

## Cross-refs & scope discipline
- Reranker = LLM-rerank or small cross-encoder, **not** a training pipeline.
- Mock data stays seeded fixtures (spec 05); no real Stripe integration.
- Provider A/B + real cache numbers **depend on the Claude/paid swap** — don't block the core on them
  (see the scope-creep review in `00-overview.md`).
- Feeds spec 08 (graph diagram, fusion transparency UI, judge-reasoning drill-down) and spec 06 (scores).
