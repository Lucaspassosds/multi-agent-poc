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
`POST /agent/triage/stream` (SSE, added in Phase 8 — see Implementation note) · `GET /traces` ·
`GET /traces/{id}` · `POST /evals/run` · `GET /evals` · `POST /ingest`.

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
  **Resolved: Tailwind** (see Implementation note).

## Implementation note (post-build)
This spec originally named the streaming endpoint `POST /tickets/triage`, but no such route (or
any streaming route) existed when Phase 8 started — the only pipeline endpoint was the
synchronous `POST /agent/triage`, and the Phase-6 `Trace` is persisted atomically at the end of a
run with no partial state exposed mid-request. This was surfaced to the user as an explicit
architecture fork before building the Triage screen: (A) no backend changes — render the finished
result, fetch the trace retrospectively for the waterfall, or (B) refactor the orchestrator for
real streaming. **The user chose (B).**

`backend/app/agents/orchestrator.py` was refactored into `_run_pipeline(emit=...)` (the same
pipeline, with an `await emit(...)` bracket around each phase) + `triage_events()` (an async
generator that runs the pipeline as a background task and fans in events from concurrently
running phases via an `asyncio.Queue`) + a thin `triage()` wrapper that drains it — so the
existing synchronous `/agent/triage` and the Phase-7 evals runner are behaviorally unchanged. The
new `POST /agent/triage/stream` mirrors the existing `GET /llm/stream` SSE convention. Verified
directly (Python `urllib` probe): all concurrent retriever `step_start` events land at the
identical timestamp, proving genuine concurrency rather than a client-side animation.

Stack landed on **Tailwind CSS** + **react-router-dom** + plain `fetch` (no TanStack Query — only
~5 endpoints, no cross-screen cache invalidation needed). No charting library — the span waterfall
isn't a standard chart-library type (it's a Gantt/trace timeline); it and the eval score meters
are hand-rolled per the `dataviz` skill's mark specs, using a categorical/status color palette
validated against the app's dark surface (`ui-ux-pro-max`'s "Modern Dark" style recommendation).

## Post-launch enhancement: Triage page "how it works" section (2026-07-20)

### Why
The shipped Triage page (above) is purely functional — textarea, presets, live timeline, answer
card, chips — with no explanation of what the agent actually does for a first-time viewer (e.g. a
reviewer landing on the page cold, before ever submitting a ticket). Researched current (2026)
market patterns for AI-agent-product main screens before designing this — two credible sources
converged on the same core ideas, both directly applicable here:
- **Plan-and-execute / "Intent Preview"** ([Smashing Magazine](https://www.smashingmagazine.com/2026/02/designing-agentic-ai-practical-ux-patterns/),
  [Fuselab](https://fuselabcreative.com/ui-design-for-ai-agents/)): show the agent's intended steps
  in plain language *before* it acts — plain language specifically (their example: "Cancel flight
  AA123", not "Executing API call cancel_booking(id: 4A7B)").
- **Transparency over silence**: proactive status communication beats a bare spinner; users
  disengage when an interface is a black box with nothing shown between input and output.
- **Evidence-forward trust** (NNGroup, cited by Fuselab): users rarely click citations, but seeing
  that reasoning/evidence exists is itself what builds trust — supports keeping the citation/RAG
  framing prominent rather than treating it as incidental plumbing.

### Content contract
A dismissible "How it works" section above the ticket form:
- **4 step cards** (Classify → Retrieve → Resolve → Critique), each: an icon (Phosphor), a short
  title matching the live timeline's row labels exactly, one plain-language sentence (no
  "subagent"/"span"/internal jargon):
  1. **Classify** — "Figures out what kind of issue this is: category, priority, and how the
     customer's feeling."
  2. **Retrieve** (badge: *parallel*) — "Searches the knowledge base and past tickets at once, from
     a few different angles."
  3. **Resolve** — "Drafts a reply grounded in what it found — no invented policy, every claim
     traceable."
  4. **Critique** — "A second pass checks the draft for unsupported claims or gaps, and revises if
     needed."
- **4 capability badges** below the cards (icon + short label): Grounded answers (RAG + citations)
  · Parallel retrieval · Self-critiques & revises · Every run fully traced (links to
  `/observability`).

### Mechanics
- A small header row ("How it works" + chevron) toggles the section open/closed.
- Expanded by default; collapsed state persists in `localStorage` (survives refresh) — a viewer who
  collapses it once doesn't have to re-collapse it every demo run.
- Icons: **`@phosphor-icons/react`** (new dependency) — the icon set `ui-ux-pro-max` recommends as
  this project's default; used here for the first time (no other screen has icons yet).
- The live timeline's row labels (`STEP_LABEL` in `TriagePage.tsx`, `SERIES_LABEL` in
  `lib/waterfall.ts`) are relabeled to match the card titles exactly (Classify/Retrieve/Resolve/
  Critique, not classifier/retriever/resolver/critic) — same words in the static preview and the
  live view, per the "avoid jargon" principle above.
- Light visual polish pass on the existing form/timeline/answer card (spacing, hierarchy, icons on
  section headers) so the new section doesn't look bolted onto an otherwise plainer page —
  functional behavior of those parts is unchanged.

### Acceptance
- [x] Section renders above the form, expanded by default, on a fresh visit (no localStorage entry).
- [x] Collapsing it and refreshing the page keeps it collapsed (localStorage-backed `useState`
      initializer + effect in `HowItWorks.tsx`, guarded with try/catch for private-mode browsers).
- [x] "Every run fully traced" badge navigates to `/observability` (verified via rendered DOM `href`).
- [x] Timeline row labels read Classify/Retrieve/Resolve/Critique, matching the card titles
      (`STEP_DISPLAY_LABEL` in `TriagePage.tsx`, kept separate from `STEP_SERIES_NAME` which still
      feeds `seriesKeyForName()` the original backend vocabulary for color lookup — relabeling the
      display text doesn't touch how colors are chosen).
- [x] No regression to existing submit/stream/citation/chip behavior (`tsc -b` clean; headless
      render shows the form, presets, and submit button all working as before, just restyled into
      a bordered card with an icon).

Verified 2026-07-20: `docker compose exec frontend npx tsc -b --noEmit` clean; headless-Chrome
screenshot of `/` shows the 4 step cards + 4 capability badges rendering correctly with Phosphor
icons; no console errors beyond Chrome's own internal telemetry noise.
