# 08 — Frontend (Phase 8)

## Purpose
A React (Vite + TypeScript) UI that makes the whole system demoable and the agent internals legible.
Three screens.

## Stack
- Vite + React + TypeScript (no Next.js needed for a POC).
- Data fetching: plain `fetch` + a light state layer (TanStack Query optional).
- Streaming: consume the backend's SSE endpoint with `EventSource` / `fetch`-stream.
- Styling: driven by the `ui-ux-pro-max` skill (see Design approach below).

## Design approach — use the `ui-ux-pro-max` skill
Before building any screen in this phase, **invoke the `ui-ux-pro-max` skill** (via the Skill tool)
to drive all UI/UX decisions. Do not hand-pick styling ad hoc.
- Use it to select a **style**, **color palette**, **font pairing**, **layout**, and **chart** patterns
  from its searchable database (67 styles / 161 palettes / 57 font pairings / 25 charts / React stack).
- Apply its recommendations for the three screens below — especially the observability **waterfall/charts**
  (align with the `dataviz` guidance too) and accessibility.
- Rationale: a polished, coherent UI makes the agent internals legible and materially improves how the
  POC lands with reviewers. This overrides the earlier "clarity over polish / minimal styling" note.

## Screens

### 1. Triage (the hero screen)
- Textarea to submit a ticket (+ a few preset examples, incl. the "charged twice" demo).
- **Live agent timeline** streamed via SSE: classify → retrieve (parallel, shown as concurrent rows) →
  draft → critique → final. Each step shows status + timing as it happens.
- **Final answer** card: the drafted reply with inline **citations** (click → source chunk).
- Classification chips (category / priority / sentiment).

### 2. Observability dashboard  → spec 06
- Trace list (ticket, status, tokens, cost, duration).
- Trace detail: span **waterfall** (parallelism visible), per-run totals (tokens, cost, **cache-hit %**,
  retries), drill into any span.

### 3. Evals report  → spec 07
- Run button + latest results.
- Per-metric aggregates (accuracy, hit-rate, coverage, faithfulness, helpfulness) and a per-case table
  with pass/fail and judge reasoning.

## Backend endpoints consumed
`POST /tickets/triage` (SSE) · `GET /traces` · `GET /traces/{id}` · `POST /evals/run` · `GET /evals` · `POST /ingest`.

## 🎓 Concepts
- Streaming UX for agents: users tolerate latency when they can see progress — surface each step live.
- Making internals legible (timeline, citations, cost) is what turns a black-box demo into something an
  reviewers can evaluate.

## Behavior / acceptance
- [ ] Submit the demo ticket → watch the live timeline → see a cited answer.
- [ ] Dashboard shows the run's trace with visible parallelism and cost/cache stats.
- [ ] Evals screen shows scores; the regression demo is visible.
- [ ] Full demo script (spec 00) runs cleanly end-to-end.

## Open questions
- Tailwind vs plain CSS — defer to the `ui-ux-pro-max` skill's stack/style recommendation at build time.
