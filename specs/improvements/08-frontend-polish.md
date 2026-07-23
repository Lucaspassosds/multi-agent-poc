# 08 — Frontend Polish (dual audience: client + technical)

## Purpose
Fix the manager's *"doesn't present pleasantly from a client's perspective"* while keeping every
concept legible to a technical reviewer. The unifying move is a single **"Client view / Under-the-hood"
toggle** that resolves the dual-audience requirement in one control, plus a focused redesign of the
three screens. Frontend stays React + Vite + Tailwind; the HTTP contract is unchanged (spec 01).

## Contract

### Global
- **Client view / Under-the-hood toggle** (persisted): *Client* hides debug/internal surfacing and
  leads with product framing; *Under-the-hood* reveals traces, tokens, costs, span internals, concept
  signposts. Same screens, two densities.
- Consistent visual system (spacing, type scale, color) — apply the `ui-ux-pro-max` / `frontend-design`
  guidance at build time.

### Triage (the hero screen)
- Cleaner intake; **keep the live streaming SSE timeline** (the signature "watch it run" moment).
- **Clickable citation chips** → open the exact source span (uses char-offset grounding, spec 07) or the
  `kb://doc/{id}` resource (spec 03).
- **Category / priority / sentiment badges** on the classified ticket.
- A **reply card** with **Send / Edit / Escalate**; **Escalate** opens the human-in-the-loop
  **approval gate** (spec 05) — approve to commit the write.
- **Skill-loaded badge** ("`refund-policy` loaded; `refund_eligibility.py` → eligible=false", spec 04).
- Keep the "How it works" explainer (concept legibility for reviewers).
- Optional: MCP **prompt** quick-actions (`/triage-refund`, spec 03) as one-click starters.

### Observability → "Run Inspector"
- **KPI cards**: cost · latency · cache-hit · tokens · budget (breach-flagged, spec 06).
- **Waterfall** as the centerpiece; **per-role cost** breakdown; **run-compare** diff; filters.
- **Analytics section**: embedded **Langfuse chart/dashboard** + per-ticket **"View in Langfuse"**
  deep link (spec 06).
- Sequential-vs-parallel speedup number + retry/error events in the waterfall (spec 07).
- A **KB-browse panel** reading MCP `kb://index` / `kb://doc/{id}` resources (spec 03) — shows MCP
  resources are real.

### Evals → "Quality Dashboard"
- **Score cards**; **per-metric + per-category bars** (failure taxonomy, spec 07).
- **Regression vs baseline** indicator; **"Run evals"** button (with the honest ~11-min free-tier note).
- **Drill into a failing case** → show retrieved context + the **judge's reasoning** (spec 07).

## 🎓 Teaching note
A demo that a client enjoys and a reviewer can dissect are usually treated as opposing goals; the toggle
makes them the same artifact at two altitudes. The live timeline sells the product; one click reveals
the spans, tokens, and costs underneath it.

## Acceptance
- [ ] The toggle switches all three screens between client and under-the-hood density; choice persists.
- [ ] Citation chips are clickable and resolve to the correct source span/resource.
- [ ] Escalate triggers the approval gate; approving commits the write, cancelling does not.
- [ ] Observability shows in-app waterfall + KPIs, embedded Langfuse charts, and a working deep link.
- [ ] Evals dashboard renders per-category taxonomy bars and drills into a failing case with judge reasoning.
- [ ] No backend URL/path changes required (frontend still talks to the same prefixes).

## Cross-refs & sequencing
- **Last phase** — depends on 03 (resources/prompts), 04 (skill badge), 05 (approval gate, typed
  outputs), 06 (Langfuse charts/deep-link), 07 (citations, taxonomy, graph diagram).
- Reuse existing components (`CitationBadge`, `ClassificationChips`, `SpanWaterfall`, `StatTile`,
  `MetricBar`, `HowItWorks`) — extend, don't rewrite, where they already work.

## Open questions
- Design language: adopt a light shadcn/ui + Tailwind system, or restyle the current bespoke components?
  Recommend a light design-token pass over the existing components first; full shadcn migration only if
  the client-view bar demands it.
- Toggle default: Client or Under-the-hood on first load? Recommend **Client** (best first impression),
  with under-the-hood one click away.
