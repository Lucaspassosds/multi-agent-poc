# Ticket History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist each successful triage run server-side and let a visitor revisit past tickets (timeline + final reply) from a ChatGPT-style sidebar on the Triage page.

**Architecture:** Add one `tickets` table to the existing Postgres schema. The stream endpoint persists a row after each successful run (the agent timeline is already stored as `spans`, joined via `trace_id`). Two read endpoints (`GET /tickets`, `GET /tickets/{id}`) feed a new sidebar; clicking an item restores the final reply from the stored result and rebuilds the timeline from the existing `GET /traces/{trace_id}` via the existing `spanTreeToRows` helper. Visitors are separated by an anonymous `session_id` kept in localStorage. Revisiting is read-only.

**Tech Stack:** FastAPI + asyncpg + Postgres (backend), React 18 + TypeScript + Vite + Tailwind (frontend). No agent-pipeline changes.

## Global Constraints

- **No test framework exists in this repo** (no pytest/vitest config, zero test files). Introducing one is out of scope. Each task is verified by **concrete manual checks**: `curl` against the running backend, `docker compose exec frontend npm run build` for a TypeScript typecheck, and browser checks at `http://localhost:5173`. This is a deliberate, stated deviation from strict TDD, matching the project's spec-driven / verify-by-running convention.
- **Reuse existing patterns.** Backend routers mirror `backend/app/api_traces.py` (APIRouter with prefix, asyncpg pool, `.isoformat()` on timestamps). Frontend API calls mirror `frontend/src/lib/api.ts`; types are hand-mirrored in `frontend/src/lib/types.ts` (no codegen).
- **ID types:** `traces.id` is `BIGSERIAL` (int). `tickets.id` is `BIGSERIAL`; `tickets.trace_id` is `BIGINT` referencing `traces(id)`. Frontend treats these ids as `number`.
- **Run/verify commands** (from README):
  - Backend picks up `schema.sql` + Python changes on restart: `docker compose restart backend` (schema init runs in the lifespan startup).
  - Backend reachable at `http://localhost:8000`; frontend at `http://localhost:5173` (Vite HMR live-reloads `.tsx` edits).
  - Frontend typecheck/build: `docker compose exec frontend npm run build` (runs `tsc -b && vite build`).
- **No auth.** `session_id` is an opaque client-generated string; the backend trusts and filters by it.
- **Only persist successful runs.** A run that errors before a `final` event writes nothing.

---

## File Structure

**Backend**
- `backend/app/schema.sql` — add `tickets` table + index (Modify).
- `backend/app/api_tickets.py` — new router: `save_ticket()` helper, `GET /tickets`, `GET /tickets/{id}` (Create).
- `backend/app/api_agent.py` — add `session_id` to `AgentIn`; persist in the stream handler (Modify).
- `backend/app/main.py` — register the tickets router (Modify).

**Frontend**
- `frontend/src/lib/session.ts` — `getOrCreateSessionId()` (Create).
- `frontend/src/lib/types.ts` — add `TicketListItem` (Modify).
- `frontend/src/lib/api.ts` — add `getTickets()`, `getTicket()` (Modify).
- `frontend/src/lib/sse.ts` — send `session_id` in the stream body (Modify).
- `frontend/src/components/TicketSidebar.tsx` — the history sidebar (Create).
- `frontend/src/pages/TriagePage.tsx` — two-column layout, clear-on-submit, viewing mode, "New ticket" (Modify).

---

## Task 1: `tickets` table

**Files:**
- Modify: `backend/app/schema.sql` (append after the `spans` block, ~line 65)

**Interfaces:**
- Produces: table `tickets(id BIGSERIAL pk, session_id TEXT, ticket_text TEXT, category TEXT, final_reply TEXT, result JSONB, trace_id BIGINT→traces(id), created_at TIMESTAMPTZ)` + index `tickets_session_created_idx`.

- [ ] **Step 1: Append the table + index to `schema.sql`**

Add after the `spans` index lines (after line 65), before the Phase 7 `eval_runs` block:

```sql
-- Ticket history: one row per SUCCESSFUL triage run, linking the submitted ticket + final
-- reply to its already-persisted trace (spans = the timeline). Scoped per anonymous session_id.
-- Runs idempotently on startup like the tables above.
CREATE TABLE IF NOT EXISTS tickets (
    id           BIGSERIAL   PRIMARY KEY,
    session_id   TEXT        NOT NULL,
    ticket_text  TEXT        NOT NULL,
    category     TEXT,                                  -- from classification, for the sidebar chip
    final_reply  TEXT        NOT NULL,                  -- denormalized for list preview
    result       JSONB       NOT NULL,                  -- full TriageResult → restores the final-reply view
    trace_id     BIGINT      REFERENCES traces(id) ON DELETE SET NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS tickets_session_created_idx ON tickets (session_id, created_at DESC);
```

- [ ] **Step 2: Apply the schema (restart runs `init_schema`)**

Run: `docker compose restart backend`

- [ ] **Step 3: Verify the table exists**

Run:
```bash
docker compose exec db psql -U postgres -d postgres -c "\d tickets"
```
Expected: the table prints with columns `id, session_id, ticket_text, category, final_reply, result, trace_id, created_at` and the `tickets_session_created_idx` index listed.

> If the psql user/db differ, read them from `docker-compose.yml`'s `db` service env and adjust the `-U`/`-d` flags.

- [ ] **Step 4: Commit**

```bash
git add backend/app/schema.sql
git commit -m "feat(db): add tickets table for ticket history"
```

---

## Task 2: tickets router (persist helper + read endpoints)

**Files:**
- Create: `backend/app/api_tickets.py`
- Modify: `backend/app/main.py` (import + `include_router`)

**Interfaces:**
- Consumes: `app.db.get_pool`; the `tickets` table from Task 1.
- Produces:
  - `async def save_ticket(session_id: str, result: dict) -> int` — inserts one row from a `TriageResult` dict, returns the new `tickets.id`. (Used by Task 3.)
  - `GET /tickets?session_id=&limit=&offset=` → `{ "tickets": [ {id, ticket_text, category, trace_id, created_at} ], "total": int }`.
  - `GET /tickets/{ticket_id}` → the stored `TriageResult` dict (404 if missing).

- [ ] **Step 1: Create `backend/app/api_tickets.py`**

```python
"""Ticket history — persist each successful triage run and list/read past runs per session.

Mirrors the read-side conventions of api_traces.py (APIRouter + asyncpg pool + .isoformat()).
The agent timeline is NOT stored here: it already lives in `spans`, reachable via GET
/traces/{trace_id}; a ticket only links to it through `trace_id`.
"""
import json

from fastapi import APIRouter, HTTPException, Query

from app.db import get_pool

router = APIRouter(prefix="/tickets", tags=["tickets"])


async def save_ticket(session_id: str, result: dict) -> int:
    """Persist one successful triage run. `result` is the TriageResult dict the pipeline
    returns (see agents/orchestrator.py). Returns the new tickets.id."""
    pool = await get_pool()
    return await pool.fetchval(
        """
        INSERT INTO tickets (session_id, ticket_text, category, final_reply, result, trace_id)
        VALUES ($1, $2, $3, $4, $5::jsonb, $6)
        RETURNING id
        """,
        session_id,
        result["ticket"],
        (result.get("classification") or {}).get("category"),
        result["final_reply"],
        json.dumps(result),        # asyncpg has no dict->jsonb codec here; send text + ::jsonb cast
        result.get("trace_id"),
    )


@router.get("")
async def list_tickets(
    session_id: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT id, ticket_text, category, trace_id, created_at
        FROM tickets
        WHERE session_id = $1
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        session_id, limit, offset,
    )
    total = await pool.fetchval(
        "SELECT count(*) FROM tickets WHERE session_id = $1", session_id
    )
    return {
        "tickets": [
            {
                "id": r["id"],
                "ticket_text": r["ticket_text"],
                "category": r["category"],
                "trace_id": r["trace_id"],
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ],
        "total": total,
    }


@router.get("/{ticket_id}")
async def get_ticket(ticket_id: int):
    pool = await get_pool()
    row = await pool.fetchrow("SELECT result FROM tickets WHERE id = $1", ticket_id)
    if row is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    result = row["result"]
    # asyncpg returns JSONB as a str (no decoder registered on this pool); normalize to a dict.
    return json.loads(result) if isinstance(result, str) else result
```

- [ ] **Step 2: Register the router in `main.py`**

Add the import alongside the other router imports (after line 16, `from app.api_traces import router as traces_router`):

```python
from app.api_tickets import router as tickets_router
```

Add the registration after `app.include_router(traces_router)` (line 52):

```python
app.include_router(tickets_router)
```

- [ ] **Step 3: Restart the backend**

Run: `docker compose restart backend`

- [ ] **Step 4: Verify empty list + 404 detail**

Run:
```bash
curl -s 'localhost:8000/tickets?session_id=plan-test' ; echo
curl -s -o /dev/null -w '%{http_code}\n' localhost:8000/tickets/999999
```
Expected: first prints `{"tickets":[],"total":0}`; second prints `404`.

- [ ] **Step 5: Verify a real run persists + reads back**

Run (submits one ticket through the stream endpoint with a session_id, then lists it — Task 3 wires the write; if run before Task 3 this list stays empty, which is expected):
```bash
curl -s 'localhost:8000/tickets?session_id=plan-test' | python3 -m json.tool
```
Expected after Task 3: one ticket with `ticket_text`, a `category`, a numeric `trace_id`, and an ISO `created_at`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api_tickets.py backend/app/main.py
git commit -m "feat(api): tickets router — save_ticket + list/detail endpoints"
```

---

## Task 3: persist successful runs in the stream endpoint

**Files:**
- Modify: `backend/app/api_agent.py` (`AgentIn`, `triage_stream_endpoint`)

**Interfaces:**
- Consumes: `save_ticket` from Task 2; `triage_events` (already imported) whose `final` event carries `{"type": "final", "result": <TriageResult dict>}`.
- Produces: after a successful stream, one `tickets` row per run when a `session_id` was supplied. Stream output/framing is unchanged.

- [ ] **Step 1: Add `session_id` to `AgentIn` and import `save_ticket`**

Add the import near the other app imports (after line 11):

```python
from app.api_tickets import save_ticket
```

Change `AgentIn` (lines 24-25) to:

```python
class AgentIn(BaseModel):
    message: str
    session_id: str | None = None  # anonymous per-visitor history key; None → don't persist
```

- [ ] **Step 2: Capture the final result and persist after the stream completes**

Replace the body of `triage_stream_endpoint` (the `gen()` function + return, lines 57-65) with:

```python
    async def gen():
        final_result = None
        errored = False
        try:
            async for event in triage_events(body.message, use_skill=skill, search_mode=search_mode):
                if event.get("type") == "final":
                    final_result = event.get("result")
                yield f"data: {json.dumps(event, default=str)}\n\n"
        except Exception as exc:  # noqa: BLE001 - surfaced to the client as an SSE event
            errored = True
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

        # Persist only a completed, successful run — never on error, never without a session.
        if not errored and final_result is not None and body.session_id:
            try:
                await save_ticket(body.session_id, final_result)
            except Exception as exc:  # noqa: BLE001 - persistence must not break the stream
                print(f"[tickets] failed to persist ticket: {exc}")

        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
```

- [ ] **Step 3: Restart the backend**

Run: `docker compose restart backend`

- [ ] **Step 4: Verify a streamed run persists exactly one ticket**

Run (streams one ticket, then lists the session):
```bash
curl -s -X POST 'localhost:8000/agent/triage/stream' \
  -H 'Content-Type: application/json' \
  -d '{"message":"I was charged twice for my subscription, please refund the duplicate.","session_id":"plan-test"}' \
  -o /dev/null
curl -s 'localhost:8000/tickets?session_id=plan-test' | python3 -m json.tool
```
Expected: `total` is `1`; the ticket has `category` (e.g. `"refund"` or `"billing"`), a numeric `trace_id`, and `ticket_text` matching the message.

- [ ] **Step 5: Verify the stored detail is a full TriageResult**

Run (grab the id from Step 4's output, then fetch detail):
```bash
TID=$(curl -s 'localhost:8000/tickets?session_id=plan-test' | python3 -c "import sys,json;print(json.load(sys.stdin)['tickets'][0]['id'])")
curl -s "localhost:8000/tickets/$TID" | python3 -c "import sys,json;d=json.load(sys.stdin);print(sorted(d.keys()))"
```
Expected: the key list includes `classification`, `final_reply`, `evidence`, `parallelism`, `trace_id`, `total_seconds`, `cost_usd`.

- [ ] **Step 6: Verify no-session and error runs persist nothing**

Run (no `session_id` → must not persist):
```bash
curl -s -X POST 'localhost:8000/agent/triage/stream' \
  -H 'Content-Type: application/json' \
  -d '{"message":"card declined but money left my account"}' -o /dev/null
curl -s 'localhost:8000/tickets?session_id=plan-test' | python3 -c "import sys,json;print('total',json.load(sys.stdin)['total'])"
```
Expected: `total` is still `1` (the no-session run added nothing).

- [ ] **Step 7: Commit**

```bash
git add backend/app/api_agent.py
git commit -m "feat(api): persist successful triage runs to ticket history"
```

---

## Task 4: frontend data layer (session id, types, api, sse)

**Files:**
- Create: `frontend/src/lib/session.ts`
- Modify: `frontend/src/lib/types.ts` (add `TicketListItem`)
- Modify: `frontend/src/lib/api.ts` (add `getTickets`, `getTicket`)
- Modify: `frontend/src/lib/sse.ts` (send `session_id`)

**Interfaces:**
- Produces:
  - `getOrCreateSessionId(): string`
  - `interface TicketListItem { id: number; ticket_text: string; category: string | null; trace_id: number | null; created_at: string }`
  - `getTickets(sessionId: string, limit?: number, offset?: number): Promise<{ tickets: TicketListItem[]; total: number }>`
  - `getTicket(id: number): Promise<TriageResult>`
  - `streamTriage(message, opts)` now accepts `opts.sessionId` and sends it as `session_id` in the POST body.

- [ ] **Step 1: Create `frontend/src/lib/session.ts`**

```ts
// Anonymous per-visitor history key. No auth — just a stable random id in localStorage so a
// browser sees only its own past tickets (server filters by it). Cleared with site data by design.
const KEY = 'triage_session_id'

export function getOrCreateSessionId(): string {
  let id = localStorage.getItem(KEY)
  if (!id) {
    id = crypto.randomUUID()
    localStorage.setItem(KEY, id)
  }
  return id
}
```

- [ ] **Step 2: Add `TicketListItem` to `frontend/src/lib/types.ts`**

Append at the end of the file:

```ts
export interface TicketListItem {
  id: number
  ticket_text: string
  category: string | null
  trace_id: number | null
  created_at: string
}
```

- [ ] **Step 3: Add `getTickets` / `getTicket` to `frontend/src/lib/api.ts`**

Change the type import on line 1 to include the new types:

```ts
import type { EvalRun, RetrievalMode, TicketListItem, TraceDetail, TraceListItem, TriageResult } from './types'
```

Add after `getTrace` (after line 27):

```ts
export function getTickets(
  sessionId: string,
  limit = 30,
  offset = 0,
): Promise<{ tickets: TicketListItem[]; total: number }> {
  return getJSON(`/tickets?session_id=${encodeURIComponent(sessionId)}&limit=${limit}&offset=${offset}`)
}

export function getTicket(id: number): Promise<TriageResult> {
  return getJSON(`/tickets/${id}`)
}
```

- [ ] **Step 4: Send `session_id` from `streamTriage` in `frontend/src/lib/sse.ts`**

Change the `opts` param type (line 9) to add `sessionId`:

```ts
  opts: { skill?: boolean; searchMode?: RetrievalMode; sessionId?: string } = {},
```

Change the request body (line 18) to include it:

```ts
    body: JSON.stringify({ message, session_id: opts.sessionId }),
```

- [ ] **Step 5: Typecheck**

Run: `docker compose exec frontend npm run build`
Expected: build succeeds, no TypeScript errors. (`session_id: undefined` serializes away when no session is passed, matching the backend's optional field.)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/session.ts frontend/src/lib/types.ts frontend/src/lib/api.ts frontend/src/lib/sse.ts
git commit -m "feat(frontend): session id + tickets api client + session_id on stream"
```

---

## Task 5: `TicketSidebar` component

**Files:**
- Create: `frontend/src/components/TicketSidebar.tsx`

**Interfaces:**
- Consumes: `TicketListItem` (Task 4).
- Produces: default export
  `TicketSidebar(props: { tickets: TicketListItem[]; selectedId: number | null; disabled: boolean; onSelect: (id: number) => void; onNew: () => void })`.

- [ ] **Step 1: Create `frontend/src/components/TicketSidebar.tsx`**

```tsx
import { ClockCounterClockwise, Plus } from '@phosphor-icons/react'
import type { TicketListItem } from '../lib/types'

function timeAgo(iso: string): string {
  const secs = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000)
  if (secs < 60) return 'just now'
  const mins = Math.floor(secs / 60)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

export default function TicketSidebar({
  tickets,
  selectedId,
  disabled,
  onSelect,
  onNew,
}: {
  tickets: TicketListItem[]
  selectedId: number | null
  disabled: boolean
  onSelect: (id: number) => void
  onNew: () => void
}) {
  return (
    <aside className="w-64 shrink-0 space-y-3">
      <button
        type="button"
        onClick={onNew}
        disabled={disabled}
        className="flex w-full items-center gap-2 rounded-md border border-border px-3 py-2 text-sm font-medium text-foreground hover:border-accent/50 disabled:cursor-not-allowed disabled:opacity-40"
      >
        <Plus size={16} weight="bold" />
        New ticket
      </button>

      <div className="flex items-center gap-2 px-1 text-xs font-semibold uppercase tracking-wide text-mutedForeground">
        <ClockCounterClockwise size={14} weight="regular" />
        History
      </div>

      {tickets.length === 0 ? (
        <p className="px-1 text-xs text-mutedForeground">No past tickets yet.</p>
      ) : (
        <ul className="space-y-1">
          {tickets.map((t) => {
            const isSelected = t.id === selectedId
            return (
              <li key={t.id}>
                <button
                  type="button"
                  onClick={() => onSelect(t.id)}
                  disabled={disabled}
                  aria-pressed={isSelected}
                  className={`w-full rounded-md border px-3 py-2 text-left text-xs transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
                    isSelected
                      ? 'border-accent/60 bg-primary'
                      : 'border-transparent hover:border-border hover:bg-primary/40'
                  }`}
                >
                  <span className="line-clamp-2 text-foreground/90">{t.ticket_text}</span>
                  <span className="mt-1 flex items-center justify-between text-[10px] text-mutedForeground">
                    <span className="truncate">{t.category ?? 'uncategorized'}</span>
                    <span className="tabular-nums">{timeAgo(t.created_at)}</span>
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </aside>
  )
}
```

> `line-clamp-2` ships with Tailwind 3 core. If the build flags it as unknown, replace the `<span className="line-clamp-2 ...">` with `truncate` (single line) — no config change needed.

- [ ] **Step 2: Typecheck**

Run: `docker compose exec frontend npm run build`
Expected: build succeeds (the component is not yet imported anywhere; this only proves it compiles).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/TicketSidebar.tsx
git commit -m "feat(frontend): TicketSidebar history component"
```

---

## Task 6: wire the sidebar into TriagePage (layout, clear-on-submit, viewing mode)

**Files:**
- Modify: `frontend/src/pages/TriagePage.tsx`

**Interfaces:**
- Consumes: `getOrCreateSessionId` (Task 4), `getTickets`/`getTicket` (Task 4), `getTrace` + `spanTreeToRows` (existing), `TicketSidebar` (Task 5).
- Produces: the full Triage screen with a history sidebar. On successful submit → textarea clears, sidebar refreshes, new ticket appears on top. Clicking a past ticket → read-only restore of final reply + timeline. "New ticket" → empty compose state. Sidebar disabled while a run streams. On error → textarea text retained.

- [ ] **Step 1: Replace `frontend/src/pages/TriagePage.tsx` with the integrated version**

Replace the entire file with:

```tsx
import { CheckCircle, PaperPlaneTilt, Waveform } from '@phosphor-icons/react'
import { Fragment, useEffect, useRef, useState } from 'react'
import ClassificationChips from '../components/ClassificationChips'
import CitationBadge from '../components/CitationBadge'
import HowItWorks from '../components/HowItWorks'
import SpanWaterfall from '../components/SpanWaterfall'
import TicketSidebar from '../components/TicketSidebar'
import { getTicket, getTickets, getTrace } from '../lib/api'
import { getOrCreateSessionId } from '../lib/session'
import { streamTriage } from '../lib/sse'
import type { CitedChunk, Classification, TicketListItem, TriageResult } from '../lib/types'
import { seriesKeyForName, spanTreeToRows, type WaterfallRow } from '../lib/waterfall'

const PRESETS = [
  'I was charged twice for my subscription this month, please refund the duplicate.',
  'My card was declined but the money still left my account.',
  'I want to cancel my subscription and get a prorated refund.',
]

// Maps an SSE step to the backend span-name vocabulary seriesKeyForName() understands, purely
// for color lookup — kept separate from the plain-language STEP_DISPLAY_LABEL shown to the user.
const STEP_SERIES_NAME: Record<string, string> = {
  classify: 'classifier',
  plan: 'planner',
  retrieve: 'retriever',
  resolve: 'resolver',
  critique: 'critic',
  revise: 'resolver:revision',
}

// Plain-language row labels — match the "How it works" step cards' titles exactly.
const STEP_DISPLAY_LABEL: Record<string, string> = {
  classify: 'Classify',
  plan: 'Plan',
  resolve: 'Resolve',
  critique: 'Critique',
  revise: 'Resolve (revision)',
}

function upsertRow(rows: WaterfallRow[], row: WaterfallRow): WaterfallRow[] {
  const idx = rows.findIndex((r) => r.id === row.id)
  if (idx === -1) return [...rows, row]
  const next = [...rows]
  next[idx] = { ...next[idx], ...row }
  return next
}

function renderReplyWithCitations(text: string, cited: CitedChunk[]) {
  const parts = text.split(/(\[[^\]]+\])/g)
  return parts.map((part, i) => {
    const match = /^\[([^\]]+)\]$/.exec(part)
    if (!match) return <Fragment key={i}>{part}</Fragment>
    const citation = cited.find((c) => c.title.toLowerCase() === match[1].toLowerCase().trim())
    if (!citation) return <Fragment key={i}>{part}</Fragment>
    return <CitationBadge key={i} citation={citation} />
  })
}

export default function TriagePage() {
  const [message, setMessage] = useState('')
  const [running, setRunning] = useState(false)
  const [rows, setRows] = useState<WaterfallRow[]>([])
  const [result, setResult] = useState<TriageResult | null>(null)
  const [classification, setClassification] = useState<Classification | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [tickets, setTickets] = useState<TicketListItem[]>([])
  const [viewingId, setViewingId] = useState<number | null>(null)
  const startedAt = useRef(0)
  const rowStart = useRef<Map<string, number>>(new Map())
  const sessionId = useRef<string>(getOrCreateSessionId())

  async function refreshTickets() {
    try {
      const { tickets } = await getTickets(sessionId.current)
      setTickets(tickets)
    } catch {
      // History is non-critical; a failed refresh should never block triage.
    }
  }

  useEffect(() => {
    void refreshTickets()
  }, [])

  function newTicket() {
    setViewingId(null)
    setMessage('')
    setRows([])
    setResult(null)
    setClassification(null)
    setError(null)
  }

  async function selectTicket(id: number) {
    if (running) return
    setViewingId(id)
    setError(null)
    setRows([])
    setResult(null)
    setClassification(null)
    try {
      const res = await getTicket(id)
      setResult(res)
      setClassification(res.classification)
      if (res.trace_id) {
        const trace = await getTrace(res.trace_id)
        setRows(spanTreeToRows(trace))
      }
    } catch (e) {
      setError(String(e))
    }
  }

  async function submit(msg: string) {
    setRunning(true)
    setViewingId(null)
    setRows([])
    setResult(null)
    setClassification(null)
    setError(null)
    startedAt.current = performance.now()
    rowStart.current = new Map()

    const elapsed = () => (performance.now() - startedAt.current) / 1000
    let gotFinal = false

    try {
      for await (const event of streamTriage(msg, { sessionId: sessionId.current })) {
        if (event.type === 'step_start') {
          const id = event.step === 'retrieve' ? `retrieve-${event.index}` : event.step
          const label = event.step === 'retrieve'
            ? `Retrieve — ${event.subquestion ?? `#${event.index}`}`
            : STEP_DISPLAY_LABEL[event.step]
          rowStart.current.set(id, elapsed())
          setRows((prev) => upsertRow(prev, {
            id,
            label,
            seriesKey: seriesKeyForName(event.step === 'retrieve' ? 'retriever' : STEP_SERIES_NAME[event.step]),
            status: 'running',
            depth: event.step === 'retrieve' ? 1 : 0,
            startOffset: elapsed(),
            duration: null,
          }))
        } else if (event.type === 'step_done') {
          const id = event.step === 'retrieve' ? `retrieve-${event.index}` : event.step
          const start = rowStart.current.get(id) ?? elapsed()
          setRows((prev) => upsertRow(prev, {
            id,
            label: prev.find((r) => r.id === id)?.label ?? STEP_DISPLAY_LABEL[event.step] ?? event.step,
            seriesKey: prev.find((r) => r.id === id)?.seriesKey ?? seriesKeyForName(STEP_SERIES_NAME[event.step] ?? event.step),
            status: 'ok',
            depth: event.step === 'retrieve' ? 1 : 0,
            startOffset: start,
            duration: elapsed() - start,
          }))
          if (event.step === 'classify') setClassification(event.data as Classification)
        } else if (event.type === 'final') {
          setResult(event.result)
          gotFinal = true
        } else if (event.type === 'error') {
          setError(event.message)
        }
      }
    } catch (e) {
      setError(String(e))
    } finally {
      setRunning(false)
    }

    // Clear the composer only on a clean run; keep the text on error so the user can retry.
    if (gotFinal) {
      setMessage('')
      void refreshTickets()
    }
  }

  return (
    <div className="flex gap-6">
      <TicketSidebar
        tickets={tickets}
        selectedId={viewingId}
        disabled={running}
        onSelect={selectTicket}
        onNew={newTicket}
      />

      <div className="flex-1 space-y-6">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Stripe payments support triage</h1>
          <p className="mt-1 text-sm text-mutedForeground">
            Submit a Stripe payments support ticket — refunds, disputes, failed charges, subscription
            billing — and watch a multi-agent pipeline classify, research (grounded in real Stripe
            documentation), draft, and self-check a reply in real time.
          </p>
        </div>

        <HowItWorks />

        <section className="rounded-lg border border-border bg-primary p-4">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-mutedForeground">Submit a ticket</h2>
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            rows={4}
            placeholder="Describe the customer's issue…"
            className="w-full rounded-lg border border-border bg-background p-3 text-sm text-foreground placeholder:text-mutedForeground focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
          />
          <div className="mt-2 flex flex-wrap gap-2">
            {PRESETS.map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => setMessage(p)}
                className="rounded-full border border-border px-3 py-1 text-xs text-mutedForeground hover:text-foreground hover:border-accent/50"
              >
                {p.length > 40 ? `${p.slice(0, 40)}…` : p}
              </button>
            ))}
          </div>
          <button
            type="button"
            disabled={!message.trim() || running}
            onClick={() => submit(message)}
            className="mt-4 inline-flex items-center gap-2 rounded-md bg-accent px-4 py-2 text-sm font-medium text-background disabled:cursor-not-allowed disabled:opacity-40"
          >
            <PaperPlaneTilt size={16} weight="bold" />
            {running ? 'Running…' : 'Submit ticket'}
          </button>
        </section>

        {error && (
          <p className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </p>
        )}

        {rows.length > 0 && (
          <section className="rounded-lg border border-border bg-primary/30 p-4">
            <h2 className="mb-3 flex items-center gap-2 text-sm font-medium text-foreground">
              <Waveform size={16} weight="regular" className="text-accent" />
              Agent timeline
            </h2>
            <SpanWaterfall rows={rows} />
          </section>
        )}

        {classification && !result && (
          <ClassificationChips classification={classification} />
        )}

        {result && (
          <section className="space-y-3">
            <ClassificationChips classification={result.classification} />
            <div className="rounded-lg border border-border bg-primary p-4">
              <div className="mb-2 flex items-center justify-between">
                <h2 className="flex items-center gap-2 text-sm font-medium text-foreground">
                  <CheckCircle size={16} weight="regular" className="text-accent" />
                  Final reply
                </h2>
                <span className="text-xs text-mutedForeground tabular-nums">
                  {result.total_seconds}s · ${result.cost_usd.toFixed(6)} · {result.parallelism.speedup}× parallel speedup
                </span>
              </div>
              <p className="text-sm text-foreground/90 leading-relaxed whitespace-pre-wrap">
                {renderReplyWithCitations(result.final_reply, result.evidence.flatMap((e) => e.cited))}
              </p>
              {result.revised && (
                <p className="mt-2 text-xs text-mutedForeground">Revised once after critic feedback.</p>
              )}
            </div>
          </section>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Typecheck / build**

Run: `docker compose exec frontend npm run build`
Expected: build succeeds, no TypeScript errors.

- [ ] **Step 3: Manual browser verification**

Open `http://localhost:5173` and confirm, in order:
1. **Empty state:** sidebar shows "New ticket" + "History" + "No past tickets yet."
2. **Submit clears + saves:** submit a ticket; timeline + final reply render; on completion the **textarea clears** and the ticket **appears at the top of the sidebar** (category chip + "just now").
3. **Revisit restores:** submit a second, different ticket, then click the first sidebar item → main panel shows that ticket's final reply and a rebuilt **Agent timeline** (real span durations); the item is highlighted.
4. **New ticket:** click "New ticket" → main panel returns to empty compose (no result/timeline), textarea empty, nothing highlighted.
5. **Disabled during run:** submit a ticket and while "Running…" confirm sidebar items + "New ticket" are non-clickable (dimmed).
6. **Error keeps text:** stop the backend (`docker compose stop backend`), submit → an error shows and the **textarea keeps its text**; restart with `docker compose start backend`.
7. **Persistence across reload:** reload the page → the sidebar still lists past tickets (proves server-side storage, not component state).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/TriagePage.tsx
git commit -m "feat(frontend): ticket history sidebar, clear-on-submit, read-only revisit"
```

---

## Self-Review

**Spec coverage:**
- `tickets` table (spec §Data Model) → Task 1. ✅ (UUID corrected to BIGSERIAL/BIGINT to match `traces.id`.)
- Persist server-side on success only (spec §Backend) → Task 3 (Steps 2, 6). ✅
- `GET /tickets` list + `GET /tickets/{id}` detail (spec §Backend) → Task 2. ✅
- `session_id` in localStorage, sent on stream + list (spec §Frontend) → Tasks 4 (session.ts, sse.ts) & 6 (getTickets). ✅
- Sidebar with empty state + category chip + relative time (spec §Frontend) → Task 5. ✅
- Clear textarea on success, keep on error (spec §Frontend) → Task 6 Step 1 (`gotFinal` guard). ✅
- Restore final reply + timeline via `getTicket` + `getTrace`/`spanTreeToRows` (spec §Restore) → Task 6 (`selectTicket`). ✅ (Spec's "new span→row mapper" replaced by the existing `spanTreeToRows` — noted; simpler and consistent with TraceDetailPage.)
- "New ticket" resets to compose; read-only (spec §Restore, Non-Goals) → Task 6. ✅
- Clicks disabled while streaming (spec §Edge Cases) → Task 5 (`disabled`) + Task 6. ✅
- Errored / no-session runs persist nothing (spec §Edge Cases) → Task 3 Steps 6, and `gotFinal` guard. ✅
- Ticket persisted but trace missing → final reply still renders (spec §Edge Cases) → Task 6 `selectTicket` only fetches the trace when `res.trace_id` is truthy; the timeline section simply stays hidden if rows is empty. ✅

**Placeholder scan:** No TBD/TODO; every code step shows complete code; commands have expected output. ✅

**Type consistency:** `save_ticket(session_id, result)` signature matches its call in Task 3. `TicketListItem` fields (`id, ticket_text, category, trace_id, created_at`) are identical across types.ts, the backend list response, and the sidebar. `getTicket` returns `TriageResult`, consumed as such in `selectTicket`. `getTrace(id: number)` + `spanTreeToRows(trace)` match existing signatures. ✅

**Note on the "timeline unavailable" spec edge case:** the spec suggested a small "timeline unavailable" note when a trace fails to load. This plan instead hides the timeline section (renders nothing) rather than adding a note, to keep the change minimal and reuse the existing `rows.length > 0` guard. If an explicit note is wanted, it's a one-line addition in Task 6 — flagged here rather than silently dropped.
