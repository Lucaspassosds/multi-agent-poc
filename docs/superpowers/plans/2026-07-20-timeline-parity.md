# Agent Timeline Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a restored (past-ticket) Agent Timeline render identically to the live timeline shown during the original submit — same labels, same row order/depth, same legend, retrieve rows carrying their subquestion text — without touching the shared raw-tree renderer the Observability page depends on.

**Architecture:** Add one new pure function, `triageRestoreRows(trace, evidence)`, to `frontend/src/lib/waterfall.ts`. It builds `WaterfallRow[]` from a trace's span tree using the SAME label/depth vocabulary the live SSE path already uses, dropping the synthetic root row and filling retrieve-row subquestion text from the ticket's already-persisted `evidence[]`. `TriagePage.selectTicket` switches from `spanTreeToRows` to this new function. `spanTreeToRows` and `TraceDetailPage` (Observability) are untouched.

**Tech Stack:** React 18 + TypeScript + Vite + Tailwind (frontend-only change).

## Global Constraints

- **No backend changes.** This is purely a frontend row-construction fix; no schema, API, or `observability.py` changes.
- **Do not modify `spanTreeToRows`** (`frontend/src/lib/waterfall.ts:54-82`) or anything Observability's `TraceDetailPage` depends on — it correctly shows the raw span tree including the root, and must keep doing so.
- **Label/depth vocabulary must match `TriagePage.tsx`'s existing `STEP_DISPLAY_LABEL`/`STEP_SERIES_NAME` exactly:** `classifier`→`Classify` (depth 0), `planner`→`Plan` (depth 0), `retriever`→`Retrieve — <subquestion>` (depth 1), `resolver`→`Resolve` (depth 0), `critic`→`Critique` (depth 0), `resolver:revision`→`Resolve (revision)` (depth 0).
- **Retriever↔evidence matching is positional**, in the order both lists already exist — no new backend field, no span-name suffixing.
- **Keep real server-side span timings** (`duration_seconds`, and `startOffset` computed the same way `spanTreeToRows` already computes it — relative to `trace.started_at`). Do not substitute client-side timing.
- **No test framework exists in this repo** (documented, pre-existing convention). Verification is manual: `docker compose exec frontend npm run build` for the typecheck, plus a live-browser side-by-side comparison of a submitted ticket vs. reopening it from history.
- **Run/verify commands:** backend at `http://localhost:8000`, frontend (Vite dev server) at `http://localhost:5173`; `docker compose exec frontend npm run build` for typecheck/build.

---

## File Structure

- `frontend/src/lib/waterfall.ts` — add `triageRestoreRows(trace: TraceDetail, evidence: Evidence[]): WaterfallRow[]` (Modify — additive only, no existing export changes).
- `frontend/src/pages/TriagePage.tsx` — `selectTicket` calls the new function instead of `spanTreeToRows` (Modify).

---

## Task 1: `triageRestoreRows` + wire it into `selectTicket`

**Files:**
- Modify: `frontend/src/lib/waterfall.ts`
- Modify: `frontend/src/pages/TriagePage.tsx`

**Interfaces:**
- Consumes: existing `SpanNode`, `TraceDetail` types (`frontend/src/lib/types.ts`); existing `Evidence` type (same file, `{ subquestion: string; summary: string; cited: CitedChunk[]; seconds: number }`); existing `seriesKeyForName` (`frontend/src/lib/waterfall.ts:22`).
- Produces: `export function triageRestoreRows(trace: TraceDetail, evidence: Evidence[]): WaterfallRow[]` — used by `TriagePage.selectTicket` in place of `spanTreeToRows`.

- [ ] **Step 1: Add `triageRestoreRows` to `frontend/src/lib/waterfall.ts`**

Add the `Evidence` type to the import on line 1, and append the new function after `spanTreeToRows` (after line 82):

```ts
import type { Evidence, SpanNode, TraceDetail } from './types'
```

```ts
// Maps a raw backend span name to the same plain-language vocabulary the live SSE timeline
// uses (TriagePage's STEP_DISPLAY_LABEL) — kept here, not there, since this is span-tree input,
// not step input. 'retriever' is handled separately below (it needs the subquestion text).
const RESTORE_LABEL: Record<string, string> = {
  classifier: 'Classify',
  planner: 'Plan',
  resolver: 'Resolve',
  critic: 'Critique',
  'resolver:revision': 'Resolve (revision)',
}

/** Rebuilds a restored ticket's Agent Timeline to look exactly like the live SSE view instead of
 * the raw span tree spanTreeToRows() renders for Observability (which correctly keeps the root
 * orchestrator span and raw span names — that view is unrelated and unaffected by this one).
 *
 * - Drops the root `triage` span entirely (live has no top-level row).
 * - Relabels each child through the same vocabulary the live view uses.
 * - `retriever` children get their subquestion text back from `evidence`, matched positionally —
 *   spans are recorded in the same execution, in the same order, as the evidence array that
 *   produced them (see backend/app/observability.py: spans append at span-entry time; the
 *   retriever coroutines are gathered in subquestion order, same as `evidence`).
 * - Keeps real server-side timings (duration, and startOffset relative to the trace's own start).
 */
export function triageRestoreRows(trace: TraceDetail, evidence: Evidence[]): WaterfallRow[] {
  const traceStart = new Date(trace.started_at).getTime()
  const root = trace.spans[0]
  const children = root ? root.children : trace.spans
  let retrieveIndex = 0

  return children.map((s: SpanNode) => {
    const startOffset = (new Date(s.started_at).getTime() - traceStart) / 1000
    const isRetriever = s.name === 'retriever'
    const label = isRetriever
      ? `Retrieve — ${evidence[retrieveIndex]?.subquestion ?? `#${retrieveIndex}`}`
      : RESTORE_LABEL[s.name] ?? s.name
    if (isRetriever) retrieveIndex += 1

    return {
      id: String(s.id),
      label,
      seriesKey: seriesKeyForName(s.name),
      status: s.error ? 'error' : 'ok',
      depth: isRetriever ? 1 : 0,
      startOffset,
      duration: s.duration_seconds,
      model: s.model,
      inputTokens: s.input_tokens,
      outputTokens: s.output_tokens,
      cacheReadTokens: s.cache_read_tokens,
      retries: s.retries,
      error: s.error,
    }
  })
}
```

- [ ] **Step 2: Wire it into `TriagePage.tsx`**

Change the import on line 12 to add `triageRestoreRows` alongside the existing `spanTreeToRows` import (keep `spanTreeToRows` imported only if still used elsewhere in the file — it is not, after this change, so replace it rather than adding to it):

```ts
import { seriesKeyForName, triageRestoreRows, type WaterfallRow } from '../lib/waterfall'
```

In `selectTicket` (around line 105-108), replace:

```ts
      if (res.trace_id) {
        const trace = await getTrace(res.trace_id)
        setRows(spanTreeToRows(trace))
      }
```

with:

```ts
      if (res.trace_id) {
        const trace = await getTrace(res.trace_id)
        setRows(triageRestoreRows(trace, res.evidence))
      }
```

- [ ] **Step 3: Typecheck / build**

Run: `docker compose exec frontend npm run build`
Expected: build succeeds, no TypeScript errors. (If `spanTreeToRows` is no longer referenced anywhere in `TriagePage.tsx`, removing it from the import avoids an unused-import build warning/error — confirm the import line only lists what's actually used in the file after this change.)

- [ ] **Step 4: Manual browser verification — side-by-side parity check**

With the stack running (`http://localhost:5173`, backend at `http://localhost:8000`):

1. Submit a ticket that will get revised (any of the existing presets works; a revision isn't required for the check but is a good stress case if the critic happens to request one). Note the live "Agent timeline" section's exact rows: labels (`Classify`, `Plan`, one `Retrieve — <text>` row per subquestion, `Resolve`, `Critique`, and `Resolve (revision)` if revised), their order, the indentation of the Retrieve rows relative to the others, and the legend entries shown.
2. Wait for the run to finish (final reply renders, ticket appears in the sidebar).
3. Click "New ticket", then click the ticket you just submitted in the sidebar.
4. Compare the restored "Agent timeline" section against what you noted in step 1:
   - Same labels, in the same order.
   - Retrieve rows carry the same subquestion text as the live run (not generic "retriever" x N).
   - No extra top-level "triage"/"Orchestrator" row.
   - Same legend entries (no extra "Orchestrator" swatch).
   - Retrieve rows are indented one level relative to the others, matching the live rendering.
5. Confirm the durations are close to (not necessarily byte-identical to) the live numbers — the restored view now shows real server-side span timings, which is expected and correct; only the labels/structure needed to match, not the exact decimal.

Expected: the two renderings are visually identical apart from decimal-level timing differences.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/waterfall.ts frontend/src/pages/TriagePage.tsx
git commit -m "fix(frontend): restored ticket timeline matches live SSE view exactly

Adds triageRestoreRows() so reopening a past ticket renders the same
labels, row order/depth, and legend as the original live run, with
retrieve rows carrying their subquestion text back from the ticket's
persisted evidence[]. spanTreeToRows() and the Observability page are
unchanged — they correctly keep showing the raw span tree including the
root orchestrator span."
```

---

## Self-Review

**Spec coverage:**
- Drop root row → Task 1 Step 1 (`children = root ? root.children : trace.spans`). ✅
- Relabel via live vocabulary → Task 1 Step 1 (`RESTORE_LABEL` map). ✅
- Depth 0/1 → Task 1 Step 1 (`depth: isRetriever ? 1 : 0`). ✅
- Subquestion text from `evidence[]`, positional match, with fallback → Task 1 Step 1 (`evidence[retrieveIndex]?.subquestion ?? #${retrieveIndex}`). ✅
- Real server timings kept → Task 1 Step 1 (`duration: s.duration_seconds`, `startOffset` computed identically to `spanTreeToRows`). ✅
- `spanTreeToRows`/Observability untouched → Task 1 Step 1 is purely additive; Step 2 only changes `TriagePage.tsx`. ✅
- No backend changes → confirmed, no backend files in File Structure. ✅
- Manual verification → Task 1 Step 4, explicit side-by-side checklist. ✅

**Placeholder scan:** no TBD/TODO; complete code given for every step. ✅

**Type consistency:** `triageRestoreRows(trace: TraceDetail, evidence: Evidence[])` signature matches its call site (`triageRestoreRows(trace, res.evidence)` where `res: TriageResult` has `evidence: Evidence[]` per existing `types.ts`). Return type `WaterfallRow[]` matches `setRows`'s existing state type. ✅
