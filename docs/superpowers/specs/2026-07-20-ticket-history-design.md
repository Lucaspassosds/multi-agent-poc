# Ticket History — Design Spec

**Date:** 2026-07-20
**Status:** Approved for planning
**Topic:** Persist submitted tickets and let users revisit past runs (timeline + final reply) from a sidebar.

## Problem

Two related product gaps on the Triage page:

1. After submitting a ticket, the textarea keeps its text — there is nowhere for a submitted ticket to "go," so clearing it would feel like losing work.
2. Submitted tickets are not saved. Every run's agent timeline and final reply are lost on reload. The backend already persists a `traces` row + nested `spans` tree per run, but the **ticket text and final reply are computed and returned to the browser, never persisted**, so a run cannot be reopened.

These are one problem: once tickets are saved and browsable, revisiting a past run restores the page, and clearing the composer on send becomes the correct, expected behavior.

## Decision Summary

- **Storage:** reuse the existing Postgres backend. Do **not** add localStorage/IndexedDB for history data (device-bound, wiped by "clear site data", string-only ~5 MB, a second source of truth). localStorage is used **only** for an anonymous `session_id`.
- **UI:** ChatGPT-style history sidebar on the Triage page. Click a past ticket → main panel restores its timeline + final reply.
- **Scope of visitors:** per-visitor isolation via an anonymous `session_id` (random id in localStorage, sent with requests). No real auth.
- **Revisiting is read-only** — no edit/resubmit from history in this POC.
- **The timeline is not duplicated** — it is already stored as `spans` and fetched via `trace_id`.

## Non-Goals

- No authentication / user accounts.
- No edit, resubmit, delete, rename, or search of past tickets.
- No cross-device history (session_id is per-browser by design).
- No persistence of failed/errored runs.
- No changes to the agent pipeline, RAG, or observability internals beyond adding one write.

## Data Model

One new table. Timeline data is intentionally excluded (it lives in `spans`, joined via `trace_id`).

```sql
CREATE TABLE IF NOT EXISTS tickets (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id   TEXT NOT NULL,
    ticket_text  TEXT NOT NULL,
    category     TEXT,                      -- from classification, for sidebar chip
    final_reply  TEXT NOT NULL,             -- denormalized for list preview
    result       JSONB NOT NULL,            -- full TriageResult, restores final-reply section
    trace_id     UUID REFERENCES traces(id),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_tickets_session_created
    ON tickets (session_id, created_at DESC);
```

Notes:
- `result` (JSONB) holds the full `TriageResult` so restore can render classification, cost, speedup, and citations without future schema changes.
- `category` and `final_reply` are denormalized from `result` purely so the list query avoids parsing JSONB.
- Match the id type actually used by `traces.id` in `schema.sql` (UUID assumed above — confirm at implementation time and keep consistent). If `traces.id` is not UUID, align `trace_id` and the `tickets.id` strategy accordingly.
- Added to `backend/app/schema.sql`, created idempotently by the existing `init_schema` startup path.

## Backend

Persist server-side (not from the client) so history is saved even if the user closes the tab mid/after a run.

### Write — inside the existing stream handler
- Endpoint: existing `POST /agent/triage/stream` in `backend/app/api_agent.py`.
- Accept a `session_id` (query param or added to the `AgentIn` body — pick whichever is least intrusive to the existing signature; body is preferred for parity with `message`).
- After the pipeline completes and the trace has flushed (i.e., once the final `TriageResult` exists with its `trace_id`), insert one `tickets` row: `session_id`, `ticket_text = message`, `category = classification.category`, `final_reply`, `result = <full TriageResult>`, `trace_id`.
- **Only persist on success.** If the run errors before a final result, insert nothing.
- Persistence must not break the stream: the insert happens after the `final` event is produced; a failed insert is logged, not surfaced to the client as a stream error.

### Read — two endpoints (copy the existing `/traces` pattern)
- `GET /tickets?session_id=&limit=&offset=` → `{ tickets: [...], total }`, ordered `created_at DESC`. Each list item: `id, ticket_text, category, created_at, trace_id`. `limit` bounded like `/traces` (1–200, default e.g. 20); `offset >= 0`. `session_id` required; results filtered to it.
- `GET /tickets/{id}` → the stored `result` (full `TriageResult`). Returns 404 if not found. Timeline is fetched separately by the client via the existing `GET /traces/{trace_id}`.

New router file `backend/app/api_tickets.py` (prefix `/tickets`), registered in `main.py` alongside the existing routers. Pydantic response models mirror the list item and detail shapes.

## Frontend

All changes on the Triage screen and its libs.

### Session id
- New helper `getOrCreateSessionId()` (e.g. in `lib/session.ts`): read `session_id` from localStorage; if absent, generate a random id (`crypto.randomUUID()`), store it, return it.
- Sent with the stream request (`streamTriage`) and with `getTickets` list calls.

### API client (`lib/api.ts`, `lib/sse.ts`)
- `streamTriage(message)` → include `session_id`.
- Add `getTickets(sessionId, limit, offset)` and `getTicket(id)`; reuse the existing `getTrace(traceId)`.
- Add `Ticket` / `TicketListItem` types to `lib/types.ts` (hand-mirrored, matching the backend response shapes, consistent with the existing convention).

### Sidebar — `components/TicketSidebar.tsx`
- Left column on `TriagePage`, ChatGPT-style list of past tickets for the current `session_id`.
- Each item: truncated `ticket_text`, a category chip (reuse `ClassificationChips` styling if practical), relative `created_at`.
- Empty state: "No past tickets yet."
- Fetches `/tickets` on mount and after each **successful** submit (new ticket appears at top).
- Clicks are **disabled while a run is streaming**.

### Compose behavior (`pages/TriagePage.tsx`)
- **On successful submit** (`final` received): `setMessage('')` to clear the textarea.
- **On error:** keep the textarea text so the user can retry.

### Restore ("viewing past ticket" mode)
- Clicking a sidebar item enters a read-only viewing mode:
  1. `getTicket(id)` → stored `result` → render the **Final reply** section (reply text + citations, `total_seconds`, `cost_usd`, `parallelism.speedup`) and `ClassificationChips`, exactly like a live final.
  2. `getTrace(result.trace_id)` → span tree → map to `WaterfallRow[]` and render through the **existing `SpanWaterfall`** component.
- A **"New ticket"** button exits viewing mode and returns to the empty compose state.
- Viewing mode is read-only: no resubmit/edit.

### Span → WaterfallRow mapping (`lib/waterfall.ts` or a new helper)
- The one genuinely new piece of logic. Convert the stored span tree into the `WaterfallRow[]` shape `SpanWaterfall` expects:
  - `startOffset = span.started_at - trace.started_at`
  - `duration = span.ended_at - span.started_at`
  - `label` / `seriesKey` from the existing `STEP_DISPLAY_LABEL` / `STEP_SERIES_NAME` maps, keyed off span name/type; `status: 'ok'`.
  - Preserve nesting `depth` (retrieve sub-steps at depth 1, matching the live view).
- **Before writing this fresh, check `pages/TraceDetailPage.tsx`** — it already renders the span tree and may have reusable mapping logic to lift or share.

## Data Flow

```
Submit ticket
  → POST /agent/triage/stream { message, session_id }
  → SSE: step_start / step_done ... final
  → server persists tickets row (session_id, text, category, final_reply, result, trace_id)
  → client clears textarea, refreshes sidebar

Click past ticket
  → GET /tickets/{id}        → result (final reply + classification)
  → GET /traces/{trace_id}   → spans → WaterfallRow[] → SpanWaterfall
  → render read-only view; "New ticket" resets to compose
```

## Edge Cases

- **Errored run:** nothing persisted; textarea text retained.
- **Empty history:** sidebar empty state.
- **Click during active run:** sidebar clicks disabled.
- **Missing/failed ticket fetch:** show an inline error in the main panel; sidebar stays usable.
- **Ticket persisted but trace missing/failed to fetch:** still render the final reply; show a small "timeline unavailable" note instead of the waterfall.
- **New browser / cleared localStorage:** new `session_id` → empty history (expected, documented behavior).

## Testing

- **Backend:** insert-on-success writes exactly the expected row; no row on errored run; `GET /tickets` filters by `session_id`, orders `DESC`, paginates; `GET /tickets/{id}` returns stored result and 404s on unknown id.
- **Frontend:** `getOrCreateSessionId` persists and reuses an id; textarea clears on success and persists on error; sidebar refreshes after submit; clicking a ticket renders final reply + a waterfall equivalent to the live one; "New ticket" resets state; span→row mapper produces correct offsets/durations/depths from a sample trace.

## Files Touched

- `backend/app/schema.sql` — add `tickets` table + index.
- `backend/app/api_tickets.py` — new router (`GET /tickets`, `GET /tickets/{id}`).
- `backend/app/api_agent.py` — accept `session_id`, persist ticket on success in the stream handler.
- `backend/app/main.py` — register the tickets router.
- `backend/app/db.py` — insert/select helpers if that matches existing structure.
- `frontend/src/lib/session.ts` — new `getOrCreateSessionId`.
- `frontend/src/lib/api.ts`, `frontend/src/lib/sse.ts` — `session_id` on stream, `getTickets`, `getTicket`.
- `frontend/src/lib/types.ts` — `Ticket` / `TicketListItem`.
- `frontend/src/lib/waterfall.ts` (or helper) — `spans → WaterfallRow[]` mapping.
- `frontend/src/components/TicketSidebar.tsx` — new sidebar.
- `frontend/src/pages/TriagePage.tsx` — sidebar layout, clear-on-submit, viewing mode, "New ticket".
