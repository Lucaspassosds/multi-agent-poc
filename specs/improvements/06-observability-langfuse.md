# 06 — Observability + Langfuse (Cloud, augment)

## Purpose
Give observability a professional, market-standard face by **augmenting** the hand-rolled trace store
with **Langfuse Cloud** — adding persistent history, dashboards/charts, prompt logs, and scores — while
**keeping the live SSE timeline + in-app waterfall** as the signature "watch it run" demo moment. Also
land the depth upgrades (cost/latency budgets, per-role breakdown, percentiles). Decision basis:
Langfuse Cloud free tier (Hobby), augment-not-replace, provider-agnostic instrumentation.

## 🎓 Framing (protect the thesis)
Langfuse is **telemetry tooling** (an OpenTelemetry consumer), **not an agent framework**. We still
hand-roll the orchestrator. The story to a reviewer is *"framework-free pipeline, industry-standard
observability"* — a sophisticated combination, not a contradiction.

## Contract

### A. Langfuse Cloud wiring
- `pip install langfuse` (**SDK v3, OpenTelemetry-based**). Env: `LANGFUSE_SECRET_KEY`,
  `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_BASE_URL=https://cloud.langfuse.com` — one env block, **no new
  containers** (sidesteps ClickHouse footprint, the UTC footgun, and the VPN/DNS risk).
- Singleton `get_client()`; `auth_check()` on startup; **`flush()` on request teardown** (short-lived
  FastAPI requests must flush before exit).

### B. Provider-agnostic instrumentation (survives the Gemini→Claude swap)
- Wrap each provider call in a Langfuse **`generation` context manager** manually — do **not** rely on
  auto-patching (Langfuse v3 does not auto-instrument `google-genai`/`anthropic`). No instrumentor lock-in.
- Map the trace tree onto nested observations:
  `orchestrator (span) → classify/plan/retrieve×N/resolve/critique/revise (spans) → llm (generation)`.
  Because OTel context propagates through `asyncio.gather`, the parallel retrievers inherit the
  orchestrator as parent — **verify the parents** on the first run.
- Attach on each generation: `model`, `usage_details` (input/output/**`cache_read_input_tokens`**),
  `cost_details`. Provider cache/token fields are mapped **explicitly** (no auto-cost on free tier).
- Group each ticket run as a Langfuse **session**; **tag** eval-run traces vs live triage (mirrors the
  existing tagging in the current codebase).

### C. Depth upgrades on the existing store (kept in Postgres)
- **Cost & latency budgets** with per-run breach flags (e.g. `> $X` or `> N ms` → flagged in the UI).
- **Per-role / per-span** cost + tokens + cache-hit breakdown.
- **p50 / p95** latency across runs; **run-compare** diff (two runs side by side).
- Retry/error events shown in the waterfall (pairs with the retry chaos-toggle, spec 07).

### D. Scores (evals → Langfuse)
- After `POST /evals/run`, emit `langfuse.create_score(trace_id, name=..., value=...)` per case
  (accuracy, citation, judge score, and the failure-taxonomy label from spec 07). Each eval case
  becomes a Langfuse trace with attached scores → the scoring dashboard comes essentially free.

### E. Prompt management (light — optional)
- Keep subagent prompts in code by default. Optionally register them in Langfuse's prompt registry to
  demo prompt *versioning* + link each generation to the exact prompt version. Adopt only if time allows.

### F. Surfacing in our app (dual audience)
- **Per-trace prompt logs** → **deep-link** "View full trace in Langfuse" per ticket (prompt logs live
  in Langfuse's trace view; no need to rebuild them).
- **Charts** the manager asked for → **embed a Langfuse public/shared dashboard** in the Observability
  page's "Analytics" section (cost over time, latency percentiles, token trends). *Caveat:* iframes can
  be brittle behind auth/CSP — fallback is pulling aggregates via the Langfuse public API into our own
  Recharts panels. Recommend embed first, API-pull as fallback.
- Keep the in-app KPI cards + waterfall + live SSE timeline (the differentiated view).

## Acceptance
- [ ] A triaged ticket produces a Langfuse trace with the full orchestrator→subagent→generation tree,
      correct parents across the parallel retrievers, and token/cost/cache fields populated.
- [ ] `LLM_PROVIDER=anthropic` swap produces equivalent traces with **no instrumentation code change**
      beyond the provider call site (verify cache-read tokens populate on Claude).
- [ ] Eval run pushes scores; they appear on the Langfuse scoring dashboard.
- [ ] Observability page shows: in-app waterfall + KPIs, an embedded Langfuse chart/dashboard, and a
      working per-ticket "View in Langfuse" deep link.
- [ ] Budget breach flags fire on a deliberately over-budget run.
- [ ] `flush()` verified — no dropped traces on fast requests.

## Cross-refs
- Charts/deep-link surfaced by **spec 08** (Observability "Run Inspector" screen).
- Failure-taxonomy scores come from **spec 07** (evals).
- Cache-read token field originates in `llm/base.py` (spec 02 signpost; spec 07 caching-correctness).

## Open questions
- Embed vs API-pull for charts — decide at build time against Langfuse's current public-dashboard
  embedding support + our CSP. Recommend embed, API-pull fallback.
- Retention: Hobby tier is 30 days — fine for a demo; note it so no one expects long history.
