# Agent Timeline Parity — Design Spec

**Date:** 2026-07-20
**Status:** Approved for planning
**Topic:** Make a restored (past-ticket) Agent Timeline render identically to the live timeline shown during the original submit.

## Problem

Reported by the user with side-by-side screenshots. Submitting a ticket live shows:

```
Classify              1.12s
Plan                  1.32s
  Retrieve — ho...    0.87s
  Retrieve — ste...   0.88s
  Retrieve — poli...   1.11s
Resolve               0.99s
Critique              1.26s
Resolve (revision)    1.25s
```

Reopening the same ticket from history shows:

```
triage (Orchestrator)          5.98s
  classifier                   1.13s
  planner                      1.32s
  retriever                    0.91s
  retriever                    0.92s
  retriever                    1.15s
  resolver                     0.99s
  critic                       1.26s
  resolver:revision            1.25s
```

Same run, same durations — but different labels, an extra top-level row, different legend, and the per-subquestion text on the retrieve rows is gone. This reads as a bug, not a deliberate design choice, and undermines the credibility of a POC meant to demo timeline observability.

### Root cause

Two independent code paths build these rows and were never reconciled:

- **Live** — `frontend/src/pages/TriagePage.tsx`'s `submit()` builds rows by hand from SSE `step_start`/`step_done` events, using the hand-written `STEP_DISPLAY_LABEL` vocabulary (`Classify`, `Plan`, `Retrieve — <subquestion>`, `Resolve`, `Critique`, `Resolve (revision)`). No top-level row exists in this path — the SSE stream never emits one.
- **Restored** — `frontend/src/lib/waterfall.ts`'s `spanTreeToRows()` walks the *raw* persisted span tree from `GET /traces/{id}` and uses the backend's raw span names verbatim, including the root `triage` span (which is a real, correct thing to show on the **Observability** page's `TraceDetailPage` — that view is *supposed* to show the full raw trace, root included).

`spanTreeToRows` is shared by `TraceDetailPage`; it cannot simply be changed without altering Observability's own (correct, desired) behavior. The subquestion text needed for retrieve-row labels was never stored on the span at all — but it already exists in the persisted ticket's own `result.evidence[].subquestion` (the same JSONB blob `GET /tickets/{id}` returns), in the same order the retriever spans were created.

## Decision

Add a **new, dedicated** row-builder for the Triage-revisit context — do not modify `spanTreeToRows` (Observability keeps its current, correct behavior unchanged). The new function:

1. Takes the root `triage` span's **children only** — drops the root row entirely, matching live's absence of a top-level row.
2. Relabels each child span through the same vocabulary the live view uses (`classifier`→`Classify`, `planner`→`Plan`, `retriever`→`Retrieve — <subquestion>`, `resolver`→`Resolve`, `critic`→`Critique`, `resolver:revision`→`Resolve (revision)`).
3. Sets `depth: 0` for everything except retriever rows, which get `depth: 1` — matching live's visual nesting.
4. Fills the missing subquestion text on each retriever row from the persisted ticket's `result.evidence[i].subquestion`, matched **positionally** (both the span list and the evidence array are populated in the same subquestion order — spans are appended to the trace's list at `span(...)` entry time, which happens in the same single execution that produced the SSE events and the evidence array; order is fixed at execution time and is the same data being read twice).
5. Keeps the real server-side span timings (`duration_seconds`, `startOffset` relative to trace start) — these are already more accurate than the live view's client-measured timings, and timing was never the reported problem.

Legend and color-per-series output automatically become correct with no separate change: `SpanWaterfall`'s `Legend` only renders series actually present in the row set, so once the synthetic root row (series `agent`/"Orchestrator") is excluded, the legend naturally matches the live view's five series.

## Non-Goals

- No backend changes. No new columns, no changes to `observability.py`'s span recording, no changes to the `tickets`/`traces`/`spans` schema.
- No change to `spanTreeToRows` or to `TraceDetailPage`/the Observability page — their raw-tree view is correct as-is and stays that way.
- No change to live-timeline behavior (`submit()`'s row-building logic) — only the restored path changes to match it.
- Does not address the pre-existing, already-documented Minor note that selecting a past ticket doesn't clear a partially-typed compose message — out of scope for this fix.

## Data Flow

```
selectTicket(id)
  → GET /tickets/{id}        → TriageResult (includes evidence[].subquestion)
  → GET /traces/{trace_id}   → TraceDetail (root span + children, real timings)
  → triageRestoreRows(trace, result.evidence)
      - drop root row
      - relabel children via the live vocabulary
      - depth 0 / 1 (retriever only)
      - zip retriever rows ↔ evidence[] positionally for subquestion text
  → WaterfallRow[] → <SpanWaterfall rows={...} />   (same component the live view uses)
```

## Edge Cases

- **Fewer/more retriever spans than evidence entries** (should not happen in practice, but defensively): if `evidence[i]` is missing for a given retriever index, fall back to `Retrieve — #<index>` rather than crashing (mirrors the live view's own fallback for a missing subquestion, `event.subquestion ?? #${event.index}`).
- **No `resolver:revision` span** (ticket wasn't revised): simply absent from the children list — no special-casing needed, matches live where that row only appears when `revised`.
- **Unknown/unmapped span name**: fall back to the raw span name as the label (defensive default; should not occur given the fixed set of span names the orchestrator produces).
- **Trace has no children** (e.g., trace fetch returned an empty/malformed tree): returns an empty array; `TriagePage`'s existing `rows.length > 0` guard already hides the Agent Timeline section in that case — no new handling needed.

## Testing

No test framework exists in this repo (unchanged, documented, pre-existing project convention). Verification is manual: submit a ticket live, note its exact rendered rows (labels, order, depth, legend), then open it from history and confirm the two renders are visually identical except for real timing precision (server-measured vs. client-measured seconds may differ in the last decimal).

## Files Touched

- `frontend/src/lib/waterfall.ts` — add `triageRestoreRows(trace, evidence)`; no changes to `spanTreeToRows` or existing exports.
- `frontend/src/pages/TriagePage.tsx` — `selectTicket` calls `triageRestoreRows` instead of `spanTreeToRows`.
