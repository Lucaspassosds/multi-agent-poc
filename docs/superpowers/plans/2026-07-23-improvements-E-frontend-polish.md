# Phase E — Frontend Polish (dual audience) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve the manager's *"doesn't present pleasantly from a client's perspective"* while keeping every concept legible to a technical reviewer. The unifying move is a single persisted **Client view / Under-the-hood toggle** (default Client) that switches all three screens between product-framing and technical density, plus a focused redesign of Triage (hero), Observability → "Run Inspector", and Evals → "Quality Dashboard". This is the **last** improvements phase; it consumes backend capabilities delivered in Phases C & D (MCP resources/prompts, gated escalate + approve endpoint, skill-loaded info, Langfuse deep-link/embed, per-span cost, eval failure taxonomy + judge reasoning) as **existing contracts**.

**Architecture:** A React context (`frontend/src/lib/viewMode.tsx`) holds the persisted view mode; a `<ViewModeToggle/>` in the header flips it; every screen reads `useViewMode().underTheHood` to reveal or hide debug/token/cost/span density. A light design-token pass adds three shared primitives (`Card`, `Badge`, `SectionHeading`) — **not** a full shadcn migration — that the touched screens adopt. All existing signature components (`SpanWaterfall`, `CitationBadge`, `ClassificationChips`, `StatTile`, `MetricBar`, `HowItWorks`, `TicketSidebar`) are **extended, not rewritten**. The live SSE timeline on Triage is preserved verbatim. Route paths are unchanged (`/`, `/observability`, `/observability/:traceId`, `/evals`); only display labels change ("Run Inspector", "Quality Dashboard").

**Tech Stack:** React 18 + TypeScript + Vite + Tailwind + `@phosphor-icons/react` + `react-router-dom` v6 (frontend-only change). Build/typecheck: `npm run build` = `tsc -b && vite build`.

---

## Global Constraints

- **No test framework — deliberate, pre-existing repo convention.** No vitest/jest. Every task verifies via `docker compose exec frontend npm run build` (the `tsc -b` step is the typecheck gate — it must pass with zero errors) **plus** an explicit live-browser check at `http://localhost:5173` (backend at `http://localhost:8000`), with a stated click-path and expected visual result. Each task ends with manual verification + a commit.
- **No backend URL/path changes.** The frontend talks to the same prefixes (`/agent`, `/traces`, `/tickets`, `/evals`) and to the additive Phase-C/D read endpoints listed under *Backend contracts assumed* below. This phase adds **zero** backend code.
- **Extend, don't rewrite.** Reuse the existing components; add props/branches rather than replacing working render logic. The live SSE timeline path in `TriagePage.submit()` is not to be altered except where a task explicitly says so.
- **Default view mode is `client`** (best first impression); under-the-hood is one click away and persists in `localStorage` (`triage-view-mode`), mirroring the existing `HowItWorks` collapse-persistence idiom.
- **Dark-only styling stays** (`:root { color-scheme: dark }`, `.viz` chart tokens). New color needs go through the semantic Tailwind tokens added in Task 2 or the existing `.viz` CSS vars — never hard-coded hex in components except where the codebase already does (e.g. `ClassificationChips` priority `#c98500`).
- **Graceful degradation on optional backend fields.** Every consumed Phase-C/D field is typed **optional**; when absent the UI hides that affordance (no crash, no empty box). This keeps the app runnable if a backend field lands slightly differently than assumed.

### Backend contracts assumed (from Phases C & D)

These are treated as **existing**. All are additive and optional in `types.ts`; if a real field name differs, adjust the single `types.ts`/`api.ts` definition and the consumers follow. Endpoints live under existing prefixes.

| # | Contract | Shape |
|---|---|---|
| A1 | **Skill-loaded info** (spec 04) | `TriageResult.skill_invocation?: { name: string; script: string \| null; script_result: string \| null } \| null` — e.g. `{name:"refund-policy", script:"refund_eligibility.py", script_result:"eligible=false"}`. Existing `skill_used` kept for back-compat. |
| A2 | **Gated escalate proposal** (spec 05) | `TriageResult.escalation?: { proposed: boolean; reason: string; ticket_id: number; preview: string } \| null`. |
| A3 | **Approve endpoint** (spec 05) | `POST /agent/escalate/approve` body `{ ticket_id: number; reason: string }` → `{ handle: string; status: string; committed_at: string }`. Called **only** on human approval. |
| A4 | **Per-span cost** (spec 06) | `SpanNode.cost_usd?: number`. |
| A5 | **Budgets + breach flags** (spec 06) | `TraceDetail.budgets?: { cost_usd; cost_limit_usd; cost_breach; latency_seconds; latency_limit_seconds; latency_breach }`; `TraceListItem.cost_breach?/latency_breach?: boolean`. |
| A6 | **Langfuse deep-link** (spec 06) | `TraceDetail.langfuse_url?: string \| null` and `TraceListItem.langfuse_url?: string \| null`. Embedded dashboard URL comes from Vite env `VITE_LANGFUSE_DASHBOARD_URL` (a Langfuse public/shared dashboard iframe src). |
| A7 | **Eval taxonomy + regression + retrieved context** (spec 07) | `EvalCase.failure_labels?: string[]`, `EvalCase.retrieved_context?: CitedChunk[]`; `EvalRun.failure_taxonomy?: {label; count}[]`, `EvalRun.baseline?: EvalBaseline \| null`, `EvalRun.regression_failed?: boolean`. Judge reasoning already exists (`faithfulness_reasoning`/`helpfulness_reasoning`). |
| A8 | **MCP resources/prompts over HTTP** (spec 03) | Frontend can't speak the MCP transport (server is on the private docker net at `:9000/mcp`), so Phase C exposes thin HTTP passthroughs: `GET /mcp/kb` → `{resources:{id;title;source_type}[]}` (from `kb://index`); `GET /mcp/kb/{id}` → `{id;title;source_type;markdown;uri}` (from `kb://doc/{id}`); `GET /mcp/prompts` → `{prompts:{name;description;template}[]}`. `CitedChunk` gains `doc_id?: number` so a citation resolves to its KB doc. |

**Run/verify commands:** backend at `http://localhost:8000`, frontend (Vite dev server) at `http://localhost:5173`; `docker compose exec frontend npm run build` for typecheck/build.

---

## File Structure

**New files**
- `frontend/src/lib/viewMode.tsx` — `ViewModeProvider`, `useViewMode()`, `ViewMode` type (Task 1).
- `frontend/src/components/ViewModeToggle.tsx` — header segmented control (Task 1).
- `frontend/src/components/Card.tsx` — shared surface primitive (Task 2).
- `frontend/src/components/Badge.tsx` — shared pill/label primitive (Task 2).
- `frontend/src/components/SectionHeading.tsx` — shared section title primitive (Task 2).
- `frontend/src/components/KpiCard.tsx` — breach-aware KPI tile (Task 9).
- `frontend/src/components/SkillBadge.tsx` — skill-loaded badge (Task 6).
- `frontend/src/components/ReplyCard.tsx` — reply card with Send/Edit/Escalate (Task 6).
- `frontend/src/components/EscalationGate.tsx` — human-in-the-loop approval gate (Task 6).
- `frontend/src/components/KbBrowser.tsx` — MCP KB-resource browse panel (Task 12).
- `frontend/src/components/FailureTaxonomyBars.tsx` — per-category failure bars (Task 13).

**Modified files**
- `frontend/src/main.tsx` — wrap app in `ViewModeProvider` (Task 1).
- `frontend/src/components/Layout.tsx` — mount toggle; relabel nav to "Run Inspector"/"Quality Dashboard" (Task 1).
- `frontend/tailwind.config.js` + `frontend/src/styles/index.css` — semantic tokens (Task 2).
- `frontend/src/components/StatTile.tsx` — adopt `Card` (Task 2).
- `frontend/src/lib/types.ts` — Phase-C/D contract additions (Task 3).
- `frontend/src/lib/api.ts` — approve + MCP resource/prompt clients (Task 3).
- `frontend/src/lib/waterfall.ts` — `cost` on rows, `perRoleCost`, `retrievalSpeedup` (Task 3 + Task 9).
- `frontend/src/pages/TriagePage.tsx` — reducer state grouping, view-mode branches, reply card, skill badge, quick-actions (Tasks 4–7).
- `frontend/src/components/CitationBadge.tsx` — clickable KB-doc resolution + view-mode source span (Task 5).
- `frontend/src/components/SpanWaterfall.tsx` — `dense` prop: cost column + retry/error markers (Task 8).
- `frontend/src/pages/ObservabilityPage.tsx` — Run Inspector: filters, breach flags, view-mode density (Task 8).
- `frontend/src/pages/TraceDetailPage.tsx` — KPI cards, per-role cost, speedup, analytics deep link + embed, KB panel (Tasks 9–12).
- `frontend/src/pages/EvalsPage.tsx` — score cards, taxonomy bars, regression indicator, failing-case context drill (Task 13).

---

## Task 1: View-mode context + header toggle (global foundation)

**Files:**
- Create: `frontend/src/lib/viewMode.tsx`
- Create: `frontend/src/components/ViewModeToggle.tsx`
- Modify: `frontend/src/main.tsx`
- Modify: `frontend/src/components/Layout.tsx`

**Interfaces:**
- Produces: `ViewModeProvider`, `useViewMode(): { mode: ViewMode; setMode(m): void; underTheHood: boolean }`, `type ViewMode = 'client' | 'under-the-hood'`. Consumed by every screen in later tasks.

- [ ] **Step 1: Create `frontend/src/lib/viewMode.tsx`**

```tsx
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

export type ViewMode = 'client' | 'under-the-hood'

// Persisted like HowItWorks' collapse flag — a single stable localStorage key, best-effort.
const STORAGE_KEY = 'triage-view-mode'

function readMode(): ViewMode {
  try {
    return localStorage.getItem(STORAGE_KEY) === 'under-the-hood' ? 'under-the-hood' : 'client'
  } catch {
    return 'client'
  }
}

interface ViewModeContextValue {
  mode: ViewMode
  setMode: (m: ViewMode) => void
  underTheHood: boolean
}

const ViewModeContext = createContext<ViewModeContextValue | null>(null)

export function ViewModeProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<ViewMode>(readMode)

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, mode)
    } catch {
      // localStorage unavailable (private mode) — choice just won't persist across reloads.
    }
  }, [mode])

  return (
    <ViewModeContext.Provider value={{ mode, setMode, underTheHood: mode === 'under-the-hood' }}>
      {children}
    </ViewModeContext.Provider>
  )
}

export function useViewMode(): ViewModeContextValue {
  const ctx = useContext(ViewModeContext)
  if (!ctx) throw new Error('useViewMode must be used within a ViewModeProvider')
  return ctx
}
```

- [ ] **Step 2: Create `frontend/src/components/ViewModeToggle.tsx`**

```tsx
import { Eye, Wrench } from '@phosphor-icons/react'
import { useViewMode, type ViewMode } from '../lib/viewMode'

const OPTIONS: Array<{ value: ViewMode; label: string; icon: typeof Eye }> = [
  { value: 'client', label: 'Client view', icon: Eye },
  { value: 'under-the-hood', label: 'Under the hood', icon: Wrench },
]

export default function ViewModeToggle() {
  const { mode, setMode } = useViewMode()
  return (
    <div
      role="radiogroup"
      aria-label="Presentation density"
      className="inline-flex rounded-full border border-border bg-primary/40 p-0.5 text-xs"
    >
      {OPTIONS.map((o) => {
        const active = mode === o.value
        return (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => setMode(o.value)}
            className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent ${
              active ? 'bg-accent/15 text-accent' : 'text-mutedForeground hover:text-foreground'
            }`}
          >
            <o.icon size={13} weight="regular" />
            {o.label}
          </button>
        )
      })}
    </div>
  )
}
```

- [ ] **Step 3: Wrap the app in `ViewModeProvider` (`frontend/src/main.tsx`)**

Replace the render block so the provider sits inside `BrowserRouter`:

```tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { ViewModeProvider } from './lib/viewMode'
import './styles/index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <ViewModeProvider>
        <App />
      </ViewModeProvider>
    </BrowserRouter>
  </React.StrictMode>,
)
```

- [ ] **Step 4: Mount the toggle + relabel nav (`frontend/src/components/Layout.tsx`)**

Replace the file with (adds the toggle on the right of the header; renames the two technical screens; Triage keeps its label):

```tsx
import { NavLink, Outlet } from 'react-router-dom'
import ViewModeToggle from './ViewModeToggle'

const links = [
  { to: '/', label: 'Triage', end: true },
  { to: '/observability', label: 'Run Inspector' },
  { to: '/evals', label: 'Quality Dashboard' },
]

export default function Layout() {
  return (
    <div className="min-h-dvh flex flex-col">
      <header className="border-b border-border">
        <nav className="max-w-6xl mx-auto flex items-center gap-1 px-4 py-3">
          <span className="mr-4 flex items-baseline gap-2 text-sm font-semibold tracking-wide text-foreground">
            Stripe Payments Support Triage
            <span className="text-[10px] font-normal uppercase tracking-wider text-mutedForeground">
              agent POC
            </span>
          </span>
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.end}
              className={({ isActive }) =>
                `rounded-md px-3 py-1.5 text-sm transition-colors ${
                  isActive
                    ? 'bg-accent/15 text-accent'
                    : 'text-mutedForeground hover:text-foreground hover:bg-primary'
                }`
              }
            >
              {l.label}
            </NavLink>
          ))}
          <div className="ml-auto">
            <ViewModeToggle />
          </div>
        </nav>
      </header>
      <main className="flex-1 max-w-6xl w-full mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
```

- [ ] **Step 5: Typecheck / build** — `docker compose exec frontend npm run build`. Expected: build succeeds, no TS errors.

- [ ] **Step 6: Manual browser verification**
  1. Load `http://localhost:5173`. Expected: header shows nav "Triage · Run Inspector · Quality Dashboard" and, right-aligned, a two-segment pill "Client view / Under the hood" with **Client view** highlighted.
  2. Click **Under the hood** → that segment highlights. Reload the page → **Under the hood** is still selected (persisted). Click **Client view** → reverts. (No screen content changes yet — later tasks wire consumers.)

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/viewMode.tsx frontend/src/components/ViewModeToggle.tsx frontend/src/main.tsx frontend/src/components/Layout.tsx
git commit -m "feat(frontend): persisted client/under-the-hood view-mode toggle + nav relabel

Adds a ViewModeProvider (localStorage-persisted, default client) and a
header segmented toggle. Renames the Observability/Evals nav labels to
Run Inspector / Quality Dashboard (route paths unchanged). Consumers
wired in later Phase-E tasks.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Light design-token pass + shared primitives

Deliberately light (spec open-question resolution: token pass, **not** a shadcn migration). Adds three small primitives that de-duplicate the repeated `rounded-lg border border-border bg-primary p-4` surface pattern, and semantic Tailwind aliases so later tasks name intent, not hex.

**Files:**
- Modify: `frontend/tailwind.config.js`
- Modify: `frontend/src/styles/index.css`
- Create: `frontend/src/components/Card.tsx`
- Create: `frontend/src/components/Badge.tsx`
- Create: `frontend/src/components/SectionHeading.tsx`
- Modify: `frontend/src/components/StatTile.tsx`

**Interfaces:**
- Produces: `Card({ children, className?, tone? })`, `Badge({ children, tone?, dot?, className? })`, `SectionHeading({ icon?, children, right?, className? })`. Consumed by Tasks 6, 8–13.

- [ ] **Step 1: Semantic color aliases (`frontend/tailwind.config.js`)**

Add `surface`, `surfaceMuted`, `warning`, `success` aliases (mapped to existing values + the recurring `#c98500`/`#22c55e`) under `colors` — additive, nothing removed:

```js
/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      colors: {
        background: '#0F172A',
        foreground: '#F8FAFC',
        primary: '#1E293B',
        secondary: '#334155',
        accent: '#22C55E',
        destructive: '#EF4444',
        muted: '#272F42',
        mutedForeground: '#94A3B8',
        border: '#475569',
        // Phase E semantic aliases (intent names over raw hex; values match existing usage).
        surface: '#1E293B',
        surfaceMuted: '#172033',
        success: '#22C55E',
        warning: '#C98500',
      },
    },
  },
  plugins: [],
}
```

- [ ] **Step 2: Type-scale comment anchor (`frontend/src/styles/index.css`)**

Append (documents the scale the primitives use; no behavioral change beyond the utility already present):

```css
/* Phase E type scale (documented, not enforced): screen title = text-xl font-semibold;
   section heading = text-sm font-medium; body = text-sm; meta/label = text-xs text-mutedForeground.
   Primitives (Card/Badge/SectionHeading) encode these so screens stay consistent. */
```

- [ ] **Step 3: Create `frontend/src/components/Card.tsx`**

```tsx
import type { ReactNode } from 'react'

type Tone = 'default' | 'muted' | 'breach'

const TONE: Record<Tone, string> = {
  default: 'border-border bg-surface',
  muted: 'border-border bg-surface/30',
  breach: 'border-destructive/50 bg-destructive/5',
}

export default function Card({
  children,
  tone = 'default',
  className = '',
}: {
  children: ReactNode
  tone?: Tone
  className?: string
}) {
  return <div className={`rounded-lg border p-4 ${TONE[tone]} ${className}`}>{children}</div>
}
```

- [ ] **Step 4: Create `frontend/src/components/Badge.tsx`**

```tsx
import type { ReactNode } from 'react'

type Tone = 'neutral' | 'accent' | 'success' | 'warning' | 'destructive'

const TONE: Record<Tone, string> = {
  neutral: 'border-border bg-primary text-foreground',
  accent: 'border-accent/40 bg-accent/10 text-accent',
  success: 'border-transparent bg-accent/15 text-accent',
  warning: 'border-transparent text-warning',
  destructive: 'border-destructive/40 bg-destructive/10 text-destructive',
}

export default function Badge({
  children,
  tone = 'neutral',
  dot,
  className = '',
}: {
  children: ReactNode
  tone?: Tone
  dot?: string
  className?: string
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs ${TONE[tone]} ${className}`}
    >
      {dot && <span className="inline-block h-2 w-2 rounded-full" style={{ background: dot }} />}
      {children}
    </span>
  )
}
```

- [ ] **Step 5: Create `frontend/src/components/SectionHeading.tsx`**

```tsx
import type { Icon } from '@phosphor-icons/react'
import type { ReactNode } from 'react'

export default function SectionHeading({
  icon: IconCmp,
  children,
  right,
  className = '',
}: {
  icon?: Icon
  children: ReactNode
  right?: ReactNode
  className?: string
}) {
  return (
    <div className={`mb-3 flex items-center justify-between ${className}`}>
      <h2 className="flex items-center gap-2 text-sm font-medium text-foreground">
        {IconCmp && <IconCmp size={16} weight="regular" className="text-accent" />}
        {children}
      </h2>
      {right != null && <div className="text-xs text-mutedForeground tabular-nums">{right}</div>}
    </div>
  )
}
```

- [ ] **Step 6: Adopt `Card` in `StatTile` (`frontend/src/components/StatTile.tsx`)**

```tsx
import Card from './Card'

export default function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <p className="mb-1 text-xs text-mutedForeground">{label}</p>
      <p className="text-2xl font-semibold text-foreground">{value}</p>
    </Card>
  )
}
```

- [ ] **Step 7: Typecheck / build** — `docker compose exec frontend npm run build`. Expected: succeeds.

- [ ] **Step 8: Manual browser verification**
  1. Open a trace: `http://localhost:5173/observability`, click a trace id → `/observability/:id`. Expected: the four stat tiles (Total tokens / cost / cache-hit / duration) render exactly as before (Card produces the same border/background/padding). No visual regression.

- [ ] **Step 9: Commit**

```bash
git add frontend/tailwind.config.js frontend/src/styles/index.css frontend/src/components/Card.tsx frontend/src/components/Badge.tsx frontend/src/components/SectionHeading.tsx frontend/src/components/StatTile.tsx
git commit -m "feat(frontend): light design-token pass + Card/Badge/SectionHeading primitives

Adds semantic Tailwind aliases (surface/success/warning) and three small
shared primitives that de-dupe the repeated surface/heading/pill patterns.
StatTile adopts Card as the first consumer; no visual change. Deliberately
not a shadcn migration (per spec 08 open question).

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: `types.ts` + `api.ts` + `waterfall.ts` contract additions

Land the Phase-C/D contract surface (A1–A8) in one place so every later task is type-consistent and the build stays green. All additions are optional fields / new endpoints — nothing existing changes shape.

**Files:**
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/waterfall.ts`

- [ ] **Step 1: Add contract types (`frontend/src/lib/types.ts`)**

Add `doc_id?` to `CitedChunk`:

```ts
export interface CitedChunk {
  chunk_id: number
  doc_id?: number // KB document this chunk belongs to (spec 03) — lets a citation resolve to kb://doc/{id}
  title: string
  source_type: string
  snippet: string
}
```

Add `cost_usd?` to `SpanNode` (after `cache_creation_tokens`):

```ts
  cache_creation_tokens: number
  cost_usd?: number // per-span cost (spec 06); absent on older traces
  retries: number
```

Add budget/langfuse fields to `TraceListItem` (after `retries`):

```ts
  retries: number
  langfuse_url?: string | null // spec 06 deep-link
  cost_breach?: boolean // spec 06 budget flag
  latency_breach?: boolean
}
```

Add budget/langfuse fields to `TraceDetail` (after `spans`):

```ts
  spans: SpanNode[]
  budgets?: Budgets | null // spec 06
  langfuse_url?: string | null // spec 06 deep-link
}

export interface Budgets {
  cost_usd: number
  cost_limit_usd: number
  cost_breach: boolean
  latency_seconds: number
  latency_limit_seconds: number
  latency_breach: boolean
}
```

Add skill/escalation to `TriageResult` (after `cost_usd`):

```ts
  cost_usd: number
  skill_invocation?: SkillInvocation | null // spec 04
  escalation?: EscalationProposal | null // spec 05
}

export interface SkillInvocation {
  name: string
  script: string | null
  script_result: string | null
}

export interface EscalationProposal {
  proposed: boolean
  reason: string
  ticket_id: number
  preview: string
}

export interface EscalationHandle {
  handle: string
  status: string
  committed_at: string
}
```

Add taxonomy/regression/context to evals (extend `EvalCase` and `EvalRun`, add helper interfaces):

```ts
export interface EvalCase {
  golden_id: string
  ticket: string
  trace_id: number | null
  predicted_category: string
  expected_category: string
  category_correct: boolean
  predicted_priority: string
  expected_priority: string
  priority_correct: boolean
  retrieval_hit: boolean
  citation_coverage: number
  faithfulness_score: number
  faithfulness_reasoning: string
  helpfulness_score: number
  helpfulness_reasoning: string
  final_reply: string
  failure_labels?: string[] // spec 07 taxonomy labels for this case
  retrieved_context?: CitedChunk[] // spec 07 — context shown at drill-down
}

export interface FailureTaxonomyBucket {
  label: string
  count: number
}

export interface EvalBaseline {
  classification_accuracy: number
  priority_accuracy: number
  retrieval_hit_rate: number
  citation_coverage: number
  faithfulness_avg: number
  helpfulness_avg: number
}
```

And on `EvalRun` (after `cases`):

```ts
  cases: EvalCase[]
  failure_taxonomy?: FailureTaxonomyBucket[] // spec 07 aggregate
  baseline?: EvalBaseline | null // spec 07 regression baseline
  regression_failed?: boolean // spec 07 gate result
}
```

Add MCP resource/prompt types at the end of the file:

```ts
export interface KbIndexEntry {
  id: number
  title: string
  source_type: string
}

export interface KbDocResource {
  id: number
  title: string
  source_type: string
  markdown: string
  uri: string // "kb://doc/{id}"
}

export interface McpPrompt {
  name: string // e.g. "triage-refund"
  description: string
  template: string // seed text inserted into the composer
}
```

- [ ] **Step 2: Add API clients (`frontend/src/lib/api.ts`)**

Extend the import and append the new functions:

```ts
import type {
  EscalationHandle,
  EvalRun,
  KbDocResource,
  KbIndexEntry,
  McpPrompt,
  RetrievalMode,
  TicketListItem,
  TraceDetail,
  TraceListItem,
  TriageResult,
} from './types'
```

Append after `ingest`:

```ts
// --- Phase E: gated escalate (spec 05). Called ONLY on human approval. ---
export function approveEscalation(ticketId: number, reason: string): Promise<EscalationHandle> {
  return postJSON('/agent/escalate/approve', { ticket_id: ticketId, reason })
}

// --- Phase E: MCP resources/prompts over the Phase-C HTTP passthrough (spec 03). ---
export function getKbIndex(): Promise<{ resources: KbIndexEntry[] }> {
  return getJSON('/mcp/kb')
}

export function getKbDoc(id: number): Promise<KbDocResource> {
  return getJSON(`/mcp/kb/${id}`)
}

export function getMcpPrompts(): Promise<{ prompts: McpPrompt[] }> {
  return getJSON('/mcp/prompts')
}
```

- [ ] **Step 3: Carry `cost` onto waterfall rows (`frontend/src/lib/waterfall.ts`)**

In `spanTreeToRows`, add `cost: s.cost_usd,` to the pushed row (after `retries`). In `triageRestoreRows`, add `cost: s.cost_usd,` to the returned row (after `retries`). `WaterfallRow.cost?` already exists — this is a purely additive field fill, no signature change. (`perRoleCost`/`retrievalSpeedup` land in Task 9 to keep this task minimal.)

- [ ] **Step 4: Typecheck / build** — `docker compose exec frontend npm run build`. Expected: succeeds (all additions optional; no consumer references them yet).

- [ ] **Step 5: Manual browser verification** — reload `http://localhost:5173`, click through Triage submit / a trace / evals. Expected: no behavior change, no console errors (this task only widens types + adds unused-yet clients).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/types.ts frontend/src/lib/api.ts frontend/src/lib/waterfall.ts
git commit -m "feat(frontend): Phase-C/D contract types + api clients (escalate approve, MCP resources)

Adds optional skill_invocation/escalation on TriageResult, per-span cost +
budgets + langfuse_url on traces, eval failure taxonomy/baseline/retrieved
context, and MCP kb/prompt HTTP clients. All additive/optional so the build
stays green until consumers land in later tasks.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Triage state grouping via `useReducer` (deferred from Phase B)

Collapse the run-related `useState` cluster (`running`, `rows`, `result`, `classification`, `error`, `viewingId`) into one reducer so the feature additions in Tasks 5–7 extend a single state shape. `message`, `tickets`, and the three refs (`startedAt`, `rowStart`, `sessionId`) stay as-is (they are input/IO concerns, not run state). Behavior is preserved exactly.

**Files:**
- Modify: `frontend/src/pages/TriagePage.tsx`

**Interfaces:**
- Produces (module-local): `RunState`, `runReducer`. `running` becomes `state.status === 'running'`.

- [ ] **Step 1: Replace `TriagePage.tsx` with the reducer-based version (behavior-identical to today)**

```tsx
import { CheckCircle, PaperPlaneTilt, Waveform } from '@phosphor-icons/react'
import { Fragment, useEffect, useReducer, useRef, useState } from 'react'
import ClassificationChips from '../components/ClassificationChips'
import CitationBadge from '../components/CitationBadge'
import HowItWorks from '../components/HowItWorks'
import SpanWaterfall from '../components/SpanWaterfall'
import TicketSidebar from '../components/TicketSidebar'
import { getTicket, getTickets, getTrace } from '../lib/api'
import { getOrCreateSessionId } from '../lib/session'
import { streamTriage } from '../lib/sse'
import type { CitedChunk, Classification, TicketListItem, TriageResult } from '../lib/types'
import { seriesKeyForName, triageRestoreRows, type WaterfallRow } from '../lib/waterfall'

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

// --- Grouped run state (deferred Phase-B cleanup): one reducer instead of six useState. ---
interface RunState {
  status: 'idle' | 'running' | 'done' | 'error'
  rows: WaterfallRow[]
  result: TriageResult | null
  classification: Classification | null
  error: string | null
  viewingId: number | null // non-null while revisiting a past ticket
}

const IDLE: RunState = {
  status: 'idle',
  rows: [],
  result: null,
  classification: null,
  error: null,
  viewingId: null,
}

type RunAction =
  | { type: 'reset' }
  | { type: 'start' }
  | { type: 'upsertRow'; row: WaterfallRow }
  | { type: 'classification'; value: Classification }
  | { type: 'result'; value: TriageResult }
  | { type: 'error'; message: string }
  | { type: 'finish' }
  | { type: 'viewStart'; id: number }
  | { type: 'viewLoaded'; result: TriageResult; rows: WaterfallRow[] }

function upsert(rows: WaterfallRow[], row: WaterfallRow): WaterfallRow[] {
  const idx = rows.findIndex((r) => r.id === row.id)
  if (idx === -1) return [...rows, row]
  const next = [...rows]
  next[idx] = { ...next[idx], ...row }
  return next
}

function runReducer(state: RunState, action: RunAction): RunState {
  switch (action.type) {
    case 'reset':
      return IDLE
    case 'start':
      return { ...IDLE, status: 'running' }
    case 'upsertRow':
      return { ...state, rows: upsert(state.rows, action.row) }
    case 'classification':
      return { ...state, classification: action.value }
    case 'result':
      return { ...state, result: action.value }
    case 'error':
      return { ...state, status: 'error', error: action.message }
    case 'finish':
      return state.status === 'error' ? state : { ...state, status: 'done' }
    case 'viewStart':
      return { ...IDLE, viewingId: action.id }
    case 'viewLoaded':
      return {
        ...state,
        status: 'done',
        result: action.result,
        classification: action.result.classification,
        rows: action.rows,
      }
    default:
      return state
  }
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
  const [tickets, setTickets] = useState<TicketListItem[]>([])
  const [state, dispatch] = useReducer(runReducer, IDLE)
  const running = state.status === 'running'
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
    setMessage('')
    dispatch({ type: 'reset' })
  }

  async function selectTicket(id: number) {
    if (running) return
    dispatch({ type: 'viewStart', id })
    try {
      const res = await getTicket(id)
      let rows: WaterfallRow[] = []
      if (res.trace_id) {
        const trace = await getTrace(res.trace_id)
        rows = triageRestoreRows(trace, res.evidence)
      }
      dispatch({ type: 'viewLoaded', result: res, rows })
    } catch (e) {
      dispatch({ type: 'error', message: String(e) })
    }
  }

  async function submit(msg: string) {
    dispatch({ type: 'start' })
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
          dispatch({
            type: 'upsertRow',
            row: {
              id,
              label,
              seriesKey: seriesKeyForName(event.step === 'retrieve' ? 'retriever' : STEP_SERIES_NAME[event.step]),
              status: 'running',
              depth: event.step === 'retrieve' ? 1 : 0,
              startOffset: elapsed(),
              duration: null,
            },
          })
        } else if (event.type === 'step_done') {
          const id = event.step === 'retrieve' ? `retrieve-${event.index}` : event.step
          const start = rowStart.current.get(id) ?? elapsed()
          dispatch({
            type: 'upsertRow',
            row: {
              id,
              label: event.step === 'retrieve'
                ? `Retrieve — #${event.index}`
                : STEP_DISPLAY_LABEL[event.step] ?? event.step,
              seriesKey: seriesKeyForName(event.step === 'retrieve' ? 'retriever' : STEP_SERIES_NAME[event.step] ?? event.step),
              status: 'ok',
              depth: event.step === 'retrieve' ? 1 : 0,
              startOffset: start,
              duration: elapsed() - start,
            },
          })
          if (event.step === 'classify') dispatch({ type: 'classification', value: event.data as Classification })
        } else if (event.type === 'final') {
          dispatch({ type: 'result', value: event.result })
          gotFinal = true
        } else if (event.type === 'error') {
          dispatch({ type: 'error', message: event.message })
        }
      }
    } catch (e) {
      dispatch({ type: 'error', message: String(e) })
    } finally {
      dispatch({ type: 'finish' })
    }

    // Clear the composer only on a clean run; keep the text on error so the user can retry.
    if (gotFinal) {
      setMessage('')
      void refreshTickets()
    }
  }

  const { rows, result, classification, error, viewingId } = state

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

> Note: this rewrite drops the `step_done` "read previous row's label/seriesKey from state" lookup (which relied on `prev` inside a functional `setState`) in favor of recomputing the same label/seriesKey deterministically — the values are identical, and it removes the last dependence on reading state inside the updater. The live-run visual output is unchanged; Step 3 verifies parity.

- [ ] **Step 2: Typecheck / build** — `docker compose exec frontend npm run build`. Expected: succeeds; confirm `upsertRow` old top-level helper is gone (folded into the reducer's `upsert`).

- [ ] **Step 3: Manual browser verification — behavior parity**
  1. `http://localhost:5173` → paste preset 1 → **Submit ticket**. Expected: identical to before — timeline rows stream in (`Classify`, `Plan`, `Retrieve — …` ×N indented, `Resolve`, `Critique`), classification chips appear, then the Final reply card with the `Ns · $… · N× parallel speedup` meta and citation chips.
  2. Click **New ticket** → composer + timeline + reply clear.
  3. Click the just-submitted ticket in the sidebar → restored timeline + chips + reply render (same as live).
  4. Force an error (stop the backend, submit) → red error line shows, composer text is retained.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/TriagePage.tsx
git commit -m "refactor(frontend): group TriagePage run state into a useReducer

Collapses running/rows/result/classification/error/viewingId into one
RunState reducer (deferred Phase-B cleanup); message/tickets/refs stay put.
Behavior-identical live run and restore; sets up Tasks 5-7 to extend one
state shape instead of six setters.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Clickable citation chips → KB doc / source span

Extend `CitationBadge` so the popover can open the full KB document over MCP (`kb://doc/{id}` via `getKbDoc`), and — under-the-hood only — surfaces the raw source span identity (chunk id + source type). Client view keeps the clean snippet popover with an "Open source" affordance; under-the-hood adds the technical row.

**Files:**
- Modify: `frontend/src/components/CitationBadge.tsx`

- [ ] **Step 1: Rewrite `CitationBadge.tsx`**

```tsx
import { ArrowSquareOut, X } from '@phosphor-icons/react'
import { useState } from 'react'
import { getKbDoc } from '../lib/api'
import type { CitedChunk, KbDocResource } from '../lib/types'
import { useViewMode } from '../lib/viewMode'

export default function CitationBadge({ citation }: { citation: CitedChunk }) {
  const { underTheHood } = useViewMode()
  const [open, setOpen] = useState(false)
  const [doc, setDoc] = useState<KbDocResource | null>(null)
  const [loadingDoc, setLoadingDoc] = useState(false)
  const [docError, setDocError] = useState<string | null>(null)

  async function openDoc() {
    if (citation.doc_id == null) return
    setLoadingDoc(true)
    setDocError(null)
    try {
      setDoc(await getKbDoc(citation.doc_id))
    } catch (e) {
      setDocError(String(e))
    } finally {
      setLoadingDoc(false)
    }
  }

  return (
    <span className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="inline-flex items-center rounded border border-accent/40 bg-accent/10 px-1.5 py-0.5 text-xs text-accent hover:bg-accent/20 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
      >
        [{citation.title}]
      </button>
      {open && (
        <div className="absolute z-10 mt-1 w-72 rounded-lg border border-border bg-primary p-3 text-xs shadow-lg">
          <p className="mb-1 font-medium text-foreground">{citation.title}</p>
          <p className="mb-2 text-[10px] uppercase tracking-wide text-mutedForeground">{citation.source_type}</p>
          <p className="leading-relaxed text-foreground/90">{citation.snippet}</p>

          {underTheHood && (
            <p className="mt-2 border-t border-border pt-2 text-[10px] text-mutedForeground tabular-nums">
              chunk #{citation.chunk_id}
              {citation.doc_id != null && <> · kb://doc/{citation.doc_id}</>}
            </p>
          )}

          {citation.doc_id != null && (
            <button
              type="button"
              onClick={openDoc}
              disabled={loadingDoc}
              className="mt-2 inline-flex items-center gap-1 text-accent hover:underline disabled:opacity-50"
            >
              <ArrowSquareOut size={12} weight="regular" />
              {loadingDoc ? 'Opening…' : underTheHood ? 'Open source span (kb://doc)' : 'Open source'}
            </button>
          )}
          {docError && <p className="mt-1 text-destructive">{docError}</p>}
        </div>
      )}

      {doc && (
        <div
          className="fixed inset-0 z-30 flex items-start justify-center overflow-y-auto bg-black/50 p-6"
          role="dialog"
          aria-modal="true"
          onClick={() => setDoc(null)}
        >
          <div
            className="mt-8 w-full max-w-2xl rounded-lg border border-border bg-primary p-5 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-3 flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-foreground">{doc.title}</p>
                <p className="text-[10px] uppercase tracking-wide text-mutedForeground">
                  {doc.source_type} · {doc.uri}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setDoc(null)}
                aria-label="Close"
                className="rounded p-1 text-mutedForeground hover:text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
              >
                <X size={16} weight="bold" />
              </button>
            </div>
            <pre className="max-h-[60vh] overflow-y-auto whitespace-pre-wrap text-xs leading-relaxed text-foreground/90">
              {doc.markdown}
            </pre>
          </div>
        </div>
      )}
    </span>
  )
}
```

- [ ] **Step 2: Typecheck / build** — `docker compose exec frontend npm run build`. Expected: succeeds.

- [ ] **Step 3: Manual browser verification**
  1. Submit a ticket that yields a cited reply → click a `[Citation]` chip → snippet popover opens. If `doc_id` is present, an **Open source** link shows.
  2. Click **Open source** → a modal opens with the full KB doc markdown (fetched from `/mcp/kb/{id}`), title, source_type, and `kb://doc/{id}` URI. Click the backdrop or **X** → closes.
  3. Toggle **Under the hood** (header) → reopen a chip: the popover now also shows the `chunk #… · kb://doc/…` technical line and the link reads "Open source span (kb://doc)".
  4. If the backend `/mcp/kb/{id}` isn't up yet, clicking Open source shows an inline error (no crash); chips still render.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/CitationBadge.tsx
git commit -m "feat(frontend): clickable citation chips resolve to kb://doc over MCP

Citation popover gains an Open-source link that fetches the full KB doc
via GET /mcp/kb/{id} into a modal; under-the-hood mode also reveals the
raw chunk id + kb://doc URI. Degrades gracefully when doc_id/endpoint
are absent.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Reply card (Send / Edit / Escalate) + approval gate + skill badge

Replace the plain "Final reply" block on Triage with a `ReplyCard` offering **Send / Edit / Escalate**, where **Escalate** opens an `EscalationGate` that calls `POST /agent/escalate/approve` only on human approval. Add a `SkillBadge` above the reply showing the loaded skill + script result. Client view leads with the reply; under-the-hood adds the token/cost meta.

**Files:**
- Create: `frontend/src/components/SkillBadge.tsx`
- Create: `frontend/src/components/EscalationGate.tsx`
- Create: `frontend/src/components/ReplyCard.tsx`
- Modify: `frontend/src/pages/TriagePage.tsx`

**Interfaces:**
- `SkillBadge({ skill }: { skill: SkillInvocation })`.
- `EscalationGate({ proposal, ticketText, onDone })` — `proposal: EscalationProposal | null`, calls `approveEscalation(ticketId, reason)`.
- `ReplyCard({ result, underTheHood, renderReply })` — `renderReply: (text, cited) => ReactNode` so the existing citation rendering is reused.

- [ ] **Step 1: Create `frontend/src/components/SkillBadge.tsx`**

```tsx
import { PuzzlePiece } from '@phosphor-icons/react'
import Badge from './Badge'
import type { SkillInvocation } from '../lib/types'

export default function SkillBadge({ skill }: { skill: SkillInvocation }) {
  return (
    <Badge tone="accent">
      <PuzzlePiece size={13} weight="regular" />
      <span className="font-medium">{skill.name}</span>
      {skill.script && (
        <span className="text-accent/80">
          · {skill.script}
          {skill.script_result != null && <> → {skill.script_result}</>}
        </span>
      )}
    </Badge>
  )
}
```

- [ ] **Step 2: Create `frontend/src/components/EscalationGate.tsx`**

```tsx
import { ShieldWarning, Check, X } from '@phosphor-icons/react'
import { useState } from 'react'
import { approveEscalation } from '../lib/api'
import type { EscalationHandle, EscalationProposal } from '../lib/types'
import Card from './Card'

export default function EscalationGate({
  proposal,
  ticketId,
  ticketText,
  onClose,
}: {
  proposal: EscalationProposal | null
  ticketId: number
  ticketText: string
  onClose: () => void
}) {
  const reason = proposal?.reason ?? 'Manual escalation requested by agent operator.'
  const preview = proposal?.preview ?? `Escalate ticket #${ticketId}: "${ticketText.slice(0, 80)}…"`
  const [busy, setBusy] = useState(false)
  const [handle, setHandle] = useState<EscalationHandle | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function approve() {
    setBusy(true)
    setError(null)
    try {
      setHandle(await approveEscalation(ticketId, reason))
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  if (handle) {
    return (
      <Card tone="muted" className="border-accent/40">
        <p className="flex items-center gap-2 text-sm font-medium text-accent">
          <Check size={16} weight="bold" />
          Escalated · handle {handle.handle}
        </p>
        <p className="mt-1 text-xs text-mutedForeground">
          Ticket status is now <span className="font-medium text-foreground">{handle.status}</span>.
          Committed {new Date(handle.committed_at).toLocaleString()}.
        </p>
      </Card>
    )
  }

  return (
    <Card tone="breach">
      <p className="flex items-center gap-2 text-sm font-medium text-foreground">
        <ShieldWarning size={16} weight="regular" className="text-warning" />
        Human approval required to escalate
      </p>
      <p className="mt-2 text-xs text-mutedForeground">
        <span className="font-medium text-foreground">Reason:</span> {reason}
      </p>
      <p className="mt-1 text-xs text-mutedForeground">
        <span className="font-medium text-foreground">Write preview:</span> {preview}
      </p>
      <p className="mt-2 text-[11px] text-mutedForeground">
        This is a destructive tool (writes ticket status + creates a handle). Nothing is written until you approve.
      </p>
      {error && <p className="mt-2 text-xs text-destructive">{error}</p>}
      <div className="mt-3 flex gap-2">
        <button
          type="button"
          onClick={approve}
          disabled={busy}
          className="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-background disabled:opacity-50"
        >
          <Check size={14} weight="bold" />
          {busy ? 'Committing…' : 'Approve & commit'}
        </button>
        <button
          type="button"
          onClick={onClose}
          disabled={busy}
          className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs text-foreground hover:border-accent/50 disabled:opacity-50"
        >
          <X size={14} weight="bold" />
          Cancel
        </button>
      </div>
    </Card>
  )
}
```

- [ ] **Step 3: Create `frontend/src/components/ReplyCard.tsx`**

```tsx
import { CheckCircle, PaperPlaneTilt, PencilSimple, ShieldWarning } from '@phosphor-icons/react'
import { useState, type ReactNode } from 'react'
import type { CitedChunk, TriageResult } from '../lib/types'
import EscalationGate from './EscalationGate'
import SkillBadge from './SkillBadge'

export default function ReplyCard({
  result,
  underTheHood,
  renderReply,
}: {
  result: TriageResult
  underTheHood: boolean
  renderReply: (text: string, cited: CitedChunk[]) => ReactNode
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(result.final_reply)
  const [sent, setSent] = useState(false)
  const [gateOpen, setGateOpen] = useState(false)
  const escalationRecommended = result.escalation?.proposed === true

  return (
    <section className="space-y-3">
      {result.skill_invocation && (
        <div className="flex flex-wrap gap-2">
          <SkillBadge skill={result.skill_invocation} />
        </div>
      )}

      <div className="rounded-lg border border-border bg-primary p-4">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-sm font-medium text-foreground">
            <CheckCircle size={16} weight="regular" className="text-accent" />
            {sent ? 'Reply sent' : 'Suggested reply'}
          </h2>
          {underTheHood && (
            <span className="text-xs text-mutedForeground tabular-nums">
              {result.total_seconds}s · ${result.cost_usd.toFixed(6)} ·{' '}
              {result.usage.input_tokens + result.usage.output_tokens} tok ·{' '}
              {result.parallelism.speedup ?? '—'}× parallel
            </span>
          )}
        </div>

        {editing ? (
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={6}
            className="w-full rounded-lg border border-border bg-background p-3 text-sm text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
          />
        ) : (
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground/90">
            {renderReply(draft, result.evidence.flatMap((e) => e.cited))}
          </p>
        )}

        {result.revised && !editing && (
          <p className="mt-2 text-xs text-mutedForeground">Revised once after critic feedback.</p>
        )}

        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setSent(true)}
            disabled={sent}
            className="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-background disabled:opacity-50"
          >
            <PaperPlaneTilt size={14} weight="bold" />
            {sent ? 'Sent' : 'Send'}
          </button>
          <button
            type="button"
            onClick={() => setEditing((v) => !v)}
            className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs text-foreground hover:border-accent/50"
          >
            <PencilSimple size={14} weight="regular" />
            {editing ? 'Done editing' : 'Edit'}
          </button>
          <button
            type="button"
            onClick={() => setGateOpen(true)}
            className={`inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs ${
              escalationRecommended
                ? 'border-warning/60 text-warning'
                : 'border-border text-foreground hover:border-accent/50'
            }`}
          >
            <ShieldWarning size={14} weight="regular" />
            {escalationRecommended ? 'Escalate (recommended)' : 'Escalate'}
          </button>
        </div>
      </div>

      {gateOpen && (
        <EscalationGate
          proposal={result.escalation ?? null}
          ticketId={result.escalation?.ticket_id ?? result.trace_id}
          ticketText={result.ticket}
          onClose={() => setGateOpen(false)}
        />
      )}
    </section>
  )
}
```

> Note: `Send`/`Edit` are client-side (the POC has no outbound mail); only **Escalate → Approve** performs a real backend write (spec 05). `ticketId` falls back to `trace_id` only when no escalation proposal carries its own `ticket_id`; the backend approve endpoint keys on the ticket, so a real proposal always supplies it.

- [ ] **Step 4: Use `ReplyCard` in `TriagePage.tsx`**

Add imports:

```tsx
import ReplyCard from '../components/ReplyCard'
import { useViewMode } from '../lib/viewMode'
```

In the component body, read the mode near the other hooks:

```tsx
  const { underTheHood } = useViewMode()
```

Replace the entire `{result && ( … )}` block (the `<section>` containing the Final reply div) with:

```tsx
        {result && (
          <>
            <ClassificationChips classification={result.classification} />
            <ReplyCard result={result} underTheHood={underTheHood} renderReply={renderReplyWithCitations} />
          </>
        )}
```

(The standalone `<ClassificationChips classification={result.classification} />` now lives here; the old inline reply div is fully removed. The `CheckCircle` import in TriagePage is no longer used — remove it from the phosphor import to avoid an unused-import error; keep `PaperPlaneTilt` and `Waveform`.)

- [ ] **Step 5: Typecheck / build** — `docker compose exec frontend npm run build`. Expected: succeeds (watch for the removed `CheckCircle` import).

- [ ] **Step 6: Manual browser verification**
  1. Submit a ticket → the reply now renders as a "Suggested reply" card with **Send / Edit / Escalate** buttons and the classification chips above it. If the result carries `skill_invocation`, a green skill badge shows (e.g. "refund-policy · refund_eligibility.py → eligible=false").
  2. **Edit** → reply becomes an editable textarea; **Done editing** → renders the edited text (citations re-render). **Send** → button flips to "Sent" and heading reads "Reply sent".
  3. **Escalate** → the approval gate card appears (breach-tone) with reason + write preview + "Approve & commit" / "Cancel". **Cancel** → gate closes, no write. **Escalate → Approve & commit** → calls `POST /agent/escalate/approve`; on success the gate shows "Escalated · handle …" with the new status. (Verify in the backend/DB that no escalation row exists after Cancel, and one exists after Approve.)
  4. Toggle **Under the hood** → the reply card header shows the `Ns · $… · N tok · N× parallel` meta; **Client view** hides it.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/SkillBadge.tsx frontend/src/components/EscalationGate.tsx frontend/src/components/ReplyCard.tsx frontend/src/pages/TriagePage.tsx
git commit -m "feat(frontend): reply card with Send/Edit/Escalate + human-in-the-loop approval gate

Triage reply becomes a ReplyCard; Escalate opens an EscalationGate that
commits the write only via POST /agent/escalate/approve on approval
(cancel writes nothing). Adds a skill-loaded badge and under-the-hood
token/cost meta.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: MCP prompt quick-actions (optional starter)

One-click starters on the intake that seed the composer from MCP prompts (`/triage-refund`, `/draft-reply`, `/summarize-thread`). Fetched from `GET /mcp/prompts`; if the endpoint is absent the row simply doesn't render (the existing text PRESETS remain the primary path). Shown as a distinct "MCP prompts" row so a reviewer sees the third MCP primitive is real.

**Files:**
- Modify: `frontend/src/pages/TriagePage.tsx`

- [ ] **Step 1: Add prompt fetch + render in `TriagePage.tsx`**

Add to imports:

```tsx
import { getMcpPrompts, getTicket, getTickets, getTrace } from '../lib/api'
import type { CitedChunk, Classification, McpPrompt, TicketListItem, TriageResult } from '../lib/types'
import { Command } from '@phosphor-icons/react'
```

(Merge the `getMcpPrompts` into the existing `../lib/api` import; merge `McpPrompt` into the existing `../lib/types` import; merge `Command` into the existing `@phosphor-icons/react` import.)

Add state + effect near the other hooks:

```tsx
  const [prompts, setPrompts] = useState<McpPrompt[]>([])

  useEffect(() => {
    getMcpPrompts()
      .then((r) => setPrompts(r.prompts))
      .catch(() => setPrompts([])) // MCP prompts are an optional flourish; ignore if the endpoint is down.
  }, [])
```

Inside the "Submit a ticket" `<section>`, immediately **after** the presets `<div className="mt-2 flex flex-wrap gap-2">…</div>`, add the MCP prompt row:

```tsx
          {prompts.length > 0 && (
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wide text-mutedForeground">
                <Command size={12} weight="regular" />
                MCP prompts
              </span>
              {prompts.map((p) => (
                <button
                  key={p.name}
                  type="button"
                  title={p.description}
                  onClick={() => setMessage(p.template)}
                  className="rounded-full border border-accent/40 bg-accent/10 px-3 py-1 text-xs text-accent hover:bg-accent/20"
                >
                  /{p.name}
                </button>
              ))}
            </div>
          )}
```

- [ ] **Step 2: Typecheck / build** — `docker compose exec frontend npm run build`. Expected: succeeds.

- [ ] **Step 3: Manual browser verification**
  1. With the MCP service up, load Triage. Expected: below the text presets, an "MCP prompts" row shows pills `/triage-refund`, `/draft-reply`, `/summarize-thread` (whatever the server returns).
  2. Click `/triage-refund` → the composer fills with that prompt's template text; hovering a pill shows its description as a tooltip.
  3. Stop the MCP service and reload → the row disappears; text presets and submit still work.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/TriagePage.tsx
git commit -m "feat(frontend): MCP prompt quick-actions on the triage intake

Fetches GET /mcp/prompts and renders one-click starters that seed the
composer (/triage-refund etc.), surfacing MCP's third primitive. Hidden
when the endpoint is unavailable.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Run Inspector list — filters, breach flags, `SpanWaterfall` dense prop

Reframe the Observability list as "Run Inspector": add status/name filters, surface budget-breach flags per row, and give `SpanWaterfall` a `dense` prop (used here indirectly and by Task 9) that reveals a cost column + retry/error markers under-the-hood. Client view keeps the table lean; under-the-hood reveals the cost/retry columns.

**Files:**
- Modify: `frontend/src/components/SpanWaterfall.tsx`
- Modify: `frontend/src/pages/ObservabilityPage.tsx`

- [ ] **Step 1: Add `dense` prop to `SpanWaterfall.tsx`**

Change the signature and add a cost cell + retry marker. Replace the component's opening and the trailing duration cell:

Signature:

```tsx
export default function SpanWaterfall({ rows, dense = false }: { rows: WaterfallRow[]; dense?: boolean }) {
```

Inside the row `.map`, replace the trailing duration `<span>` with a group that adds a retry marker and (dense) a cost cell:

```tsx
              <span className="flex w-14 shrink-0 items-center justify-end gap-1 text-right text-xs tabular-nums text-[var(--viz-text-muted)]">
                {row.retries != null && row.retries > 0 && (
                  <span
                    className="rounded-sm bg-[var(--status-critical)]/20 px-1 text-[10px]"
                    style={{ color: 'var(--status-critical)' }}
                    title={`${row.retries} retr${row.retries === 1 ? 'y' : 'ies'}`}
                  >
                    ↻{row.retries}
                  </span>
                )}
                {row.duration != null ? `${row.duration.toFixed(2)}s` : '…'}
              </span>
              {dense && (
                <span className="w-16 shrink-0 text-right text-xs tabular-nums text-[var(--viz-text-muted)]">
                  {row.cost != null ? `$${row.cost.toFixed(6)}` : '—'}
                </span>
              )}
```

(The existing error `borderLeft` marker and selected-row detail panel remain untouched — errors already render; this adds the retry event count + optional cost column.)

- [ ] **Step 2: Rewrite `ObservabilityPage.tsx` as the Run Inspector list**

```tsx
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Warning } from '@phosphor-icons/react'
import Badge from '../components/Badge'
import { getTraces } from '../lib/api'
import type { TraceListItem } from '../lib/types'
import { useViewMode } from '../lib/viewMode'

const PAGE_SIZE = 20

export default function ObservabilityPage() {
  const { underTheHood } = useViewMode()
  const [traces, setTraces] = useState<TraceListItem[] | null>(null)
  const [total, setTotal] = useState(0)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState<'all' | 'ok' | 'error'>('all')
  const [nameFilter, setNameFilter] = useState('')

  useEffect(() => {
    getTraces(PAGE_SIZE, 0)
      .then((r) => { setTraces(r.traces); setTotal(r.total) })
      .catch((e) => setError(String(e)))
  }, [])

  async function loadMore() {
    if (!traces) return
    setLoadingMore(true)
    try {
      const r = await getTraces(PAGE_SIZE, traces.length)
      setTraces([...traces, ...r.traces])
      setTotal(r.total)
    } catch (e) {
      setError(String(e))
    } finally {
      setLoadingMore(false)
    }
  }

  const filtered = useMemo(() => {
    if (!traces) return []
    const q = nameFilter.trim().toLowerCase()
    return traces.filter(
      (t) =>
        (statusFilter === 'all' || t.status === statusFilter) &&
        (q === '' || t.name.toLowerCase().includes(q)),
    )
  }, [traces, statusFilter, nameFilter])

  return (
    <div className="viz space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Run Inspector</h1>
        <p className="text-sm text-mutedForeground">
          Every triage run, fully traced — duration, tokens, cost, cache-hit, parallelism, retries.
          {underTheHood
            ? ' Open a run for the span waterfall, per-role cost, budget breaches, and the Langfuse deep link.'
            : ' Open a run to see how the pipeline spent its time.'}
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <label className="text-xs text-mutedForeground">
          Status
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as 'all' | 'ok' | 'error')}
            className="ml-2 rounded border border-border bg-background px-2 py-1 text-xs text-foreground"
          >
            <option value="all">all</option>
            <option value="ok">ok</option>
            <option value="error">error</option>
          </select>
        </label>
        <input
          value={nameFilter}
          onChange={(e) => setNameFilter(e.target.value)}
          placeholder="filter by name…"
          className="rounded border border-border bg-background px-2 py-1 text-xs text-foreground placeholder:text-mutedForeground focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
        />
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}
      {!traces && !error && <p className="text-sm text-mutedForeground">Loading runs…</p>}
      {traces && traces.length === 0 && (
        <p className="text-sm text-mutedForeground">No runs yet — submit a ticket on the Triage screen first.</p>
      )}
      {traces && traces.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-mutedForeground">
                <th className="px-3 py-2 font-medium">#</th>
                <th className="px-3 py-2 font-medium">Name</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2 font-medium text-right">Duration</th>
                <th className="px-3 py-2 font-medium text-right">Tokens</th>
                <th className="px-3 py-2 font-medium text-right">Cost</th>
                <th className="px-3 py-2 font-medium text-right">Cache-hit</th>
                {underTheHood && <th className="px-3 py-2 font-medium text-right">Retries</th>}
                <th className="px-3 py-2 font-medium">Budget</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((t) => {
                const breached = t.cost_breach || t.latency_breach
                return (
                  <tr key={t.id} className="border-b border-border/60 last:border-0 hover:bg-primary/40">
                    <td className="px-3 py-2">
                      <Link to={`/observability/${t.id}`} className="text-accent hover:underline">
                        {t.id}
                      </Link>
                    </td>
                    <td className="px-3 py-2">{t.name}</td>
                    <td className="px-3 py-2">
                      <span
                        className="inline-flex items-center gap-1.5 text-xs"
                        style={{ color: t.status === 'ok' ? 'var(--status-good)' : 'var(--status-critical)' }}
                      >
                        <span
                          className="inline-block h-1.5 w-1.5 rounded-full"
                          style={{ background: t.status === 'ok' ? 'var(--status-good)' : 'var(--status-critical)' }}
                        />
                        {t.status}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">{t.duration_seconds.toFixed(2)}s</td>
                    <td className="px-3 py-2 text-right tabular-nums">{t.total_tokens.toLocaleString()}</td>
                    <td className="px-3 py-2 text-right tabular-nums">${t.total_cost_usd.toFixed(6)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{t.cache_hit_pct.toFixed(1)}%</td>
                    {underTheHood && <td className="px-3 py-2 text-right tabular-nums">{t.retries}</td>}
                    <td className="px-3 py-2">
                      {breached ? (
                        <Badge tone="destructive">
                          <Warning size={12} weight="fill" />
                          {t.cost_breach && t.latency_breach ? 'cost + latency' : t.cost_breach ? 'cost' : 'latency'}
                        </Badge>
                      ) : (
                        <span className="text-xs text-mutedForeground">—</span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          <div className="flex items-center justify-between border-t border-border px-3 py-2 text-xs text-mutedForeground">
            <span>Showing {filtered.length} of {total}</span>
            {traces.length < total && (
              <button
                type="button"
                onClick={loadMore}
                disabled={loadingMore}
                className="rounded-md border border-border px-3 py-1 text-foreground hover:border-accent/50 disabled:opacity-40"
              >
                {loadingMore ? 'Loading…' : 'Load more'}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2b: Typecheck / build** — `docker compose exec frontend npm run build`. Expected: succeeds.

- [ ] **Step 3: Manual browser verification**
  1. `http://localhost:5173/observability` → title reads "Run Inspector". A Status dropdown + name filter appear above the table.
  2. Type a substring in the name filter → rows filter live; "Showing N of M" updates. Set Status = `error` → only error runs show.
  3. Toggle **Under the hood** → a "Retries" column appears; **Client view** hides it. A run with `cost_breach`/`latency_breach` shows a red "cost"/"latency"/"cost + latency" badge in the Budget column (submit a deliberately over-budget run per spec 06 to see it fire).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/SpanWaterfall.tsx frontend/src/pages/ObservabilityPage.tsx
git commit -m "feat(frontend): Run Inspector list — filters, budget-breach flags, dense waterfall

Renames Observability to Run Inspector; adds status/name filters and a
per-run budget-breach badge. SpanWaterfall gains a dense prop (cost column
+ retry markers) and a per-row retry event count. Under-the-hood reveals
the retries column.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: Run Inspector detail — KPI cards, per-role cost, speedup

Rebuild the trace detail as the Run Inspector centerpiece: breach-aware KPI cards, the waterfall (dense under-the-hood), a per-role cost breakdown, and the sequential-vs-parallel speedup number computed from the retriever spans. Client view shows headline KPIs + waterfall; under-the-hood adds per-role cost + span cost column.

**Files:**
- Modify: `frontend/src/lib/waterfall.ts`
- Create: `frontend/src/components/KpiCard.tsx`
- Modify: `frontend/src/pages/TraceDetailPage.tsx`

- [ ] **Step 1: Add `perRoleCost` + `retrievalSpeedup` to `waterfall.ts`**

Append after `triageRestoreRows`:

```ts
export interface RoleCost {
  seriesKey: SeriesKey
  label: string
  cost: number
  tokens: number
}

/** Per-role cost + token rollup for the Run Inspector, summed over the span tree by series. */
export function perRoleCost(trace: TraceDetail): RoleCost[] {
  const byKey = new Map<SeriesKey, RoleCost>()
  function walk(spans: SpanNode[]) {
    for (const s of spans) {
      const key = seriesKeyForName(s.name)
      const cur = byKey.get(key) ?? { seriesKey: key, label: SERIES_LABEL[key], cost: 0, tokens: 0 }
      cur.cost += s.cost_usd ?? 0
      cur.tokens += (s.input_tokens ?? 0) + (s.output_tokens ?? 0)
      byKey.set(key, cur)
      walk(s.children)
    }
  }
  walk(trace.spans)
  return SERIES_ORDER.map((k) => byKey.get(k)).filter(
    (r): r is RoleCost => !!r && (r.cost > 0 || r.tokens > 0),
  )
}

/** Sequential-vs-parallel wall-clock speedup for the parallel retrievers (spec 07), derived from
 * span timestamps — no backend field needed. Returns null when there are <2 retrievers. */
export function retrievalSpeedup(trace: TraceDetail): { sequential: number; parallel: number; speedup: number } | null {
  const retrievers: SpanNode[] = []
  function walk(spans: SpanNode[]) {
    for (const s of spans) {
      if (seriesKeyForName(s.name) === 'retriever') retrievers.push(s)
      walk(s.children)
    }
  }
  walk(trace.spans)
  if (retrievers.length < 2) return null
  const sequential = retrievers.reduce((a, s) => a + s.duration_seconds, 0)
  const starts = retrievers.map((s) => new Date(s.started_at).getTime())
  const ends = retrievers.map((s) => new Date(s.ended_at).getTime())
  const parallel = (Math.max(...ends) - Math.min(...starts)) / 1000
  if (parallel <= 0) return null
  return { sequential, parallel, speedup: sequential / parallel }
}
```

- [ ] **Step 2: Create `frontend/src/components/KpiCard.tsx`**

```tsx
import { Warning } from '@phosphor-icons/react'
import Card from './Card'

export default function KpiCard({
  label,
  value,
  sub,
  breach = false,
}: {
  label: string
  value: string
  sub?: string
  breach?: boolean
}) {
  return (
    <Card tone={breach ? 'breach' : 'default'}>
      <p className="mb-1 flex items-center gap-1 text-xs text-mutedForeground">
        {label}
        {breach && <Warning size={12} weight="fill" className="text-destructive" />}
      </p>
      <p className={`text-2xl font-semibold ${breach ? 'text-destructive' : 'text-foreground'}`}>{value}</p>
      {sub && <p className="mt-0.5 text-[11px] text-mutedForeground tabular-nums">{sub}</p>}
    </Card>
  )
}
```

- [ ] **Step 3: Rewrite `TraceDetailPage.tsx`**

```tsx
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowSquareOut } from '@phosphor-icons/react'
import KpiCard from '../components/KpiCard'
import SpanWaterfall from '../components/SpanWaterfall'
import Badge from '../components/Badge'
import { getTrace } from '../lib/api'
import type { TraceDetail } from '../lib/types'
import { perRoleCost, retrievalSpeedup, spanTreeToRows } from '../lib/waterfall'
import { useViewMode } from '../lib/viewMode'

export default function TraceDetailPage() {
  const { traceId } = useParams()
  const { underTheHood } = useViewMode()
  const [trace, setTrace] = useState<TraceDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!traceId) return
    getTrace(Number(traceId)).then(setTrace).catch((e) => setError(String(e)))
  }, [traceId])

  const speedup = trace ? retrievalSpeedup(trace) : null
  const roles = trace ? perRoleCost(trace) : []

  return (
    <div className="viz space-y-4">
      <Link to="/observability" className="text-sm text-accent hover:underline">
        &larr; back to runs
      </Link>
      {error && <p className="text-sm text-destructive">{error}</p>}
      {!trace && !error && <p className="text-sm text-mutedForeground">Loading run…</p>}
      {trace && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h1 className="text-xl font-semibold text-foreground">
              Run #{trace.id} · {trace.name}
            </h1>
            {trace.langfuse_url && (
              <a
                href={trace.langfuse_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs text-foreground hover:border-accent/50"
              >
                <ArrowSquareOut size={14} weight="regular" />
                View in Langfuse
              </a>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <KpiCard label="Total cost" value={`$${trace.total_cost_usd.toFixed(6)}`}
              sub={trace.budgets ? `budget $${trace.budgets.cost_limit_usd.toFixed(4)}` : undefined}
              breach={trace.budgets?.cost_breach ?? false} />
            <KpiCard label="Duration" value={`${trace.duration_seconds.toFixed(2)}s`}
              sub={trace.budgets ? `budget ${trace.budgets.latency_limit_seconds.toFixed(1)}s` : undefined}
              breach={trace.budgets?.latency_breach ?? false} />
            <KpiCard label="Cache-hit" value={`${trace.cache_hit_pct.toFixed(1)}%`} />
            <KpiCard label="Total tokens" value={trace.total_tokens.toLocaleString()} />
          </div>

          {speedup && (
            <Badge tone="success">
              {speedup.speedup.toFixed(1)}× parallel speedup — {speedup.sequential.toFixed(2)}s of retrieval done in {speedup.parallel.toFixed(2)}s wall-clock
            </Badge>
          )}

          <section className="rounded-lg border border-border bg-primary/30 p-4">
            <h2 className="mb-3 text-sm font-medium text-foreground">Span waterfall</h2>
            <SpanWaterfall rows={spanTreeToRows(trace)} dense={underTheHood} />
          </section>

          {underTheHood && roles.length > 0 && (
            <section className="rounded-lg border border-border bg-primary/30 p-4">
              <h2 className="mb-3 text-sm font-medium text-foreground">Per-role cost</h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border text-left text-xs text-mutedForeground">
                      <th className="px-3 py-2 font-medium">Role</th>
                      <th className="px-3 py-2 font-medium text-right">Tokens</th>
                      <th className="px-3 py-2 font-medium text-right">Cost</th>
                    </tr>
                  </thead>
                  <tbody>
                    {roles.map((r) => (
                      <tr key={r.seriesKey} className="border-b border-border/60 last:border-0">
                        <td className="px-3 py-2">{r.label}</td>
                        <td className="px-3 py-2 text-right tabular-nums">{r.tokens.toLocaleString()}</td>
                        <td className="px-3 py-2 text-right tabular-nums">${r.cost.toFixed(6)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}
        </>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Typecheck / build** — `docker compose exec frontend npm run build`. Expected: succeeds.

- [ ] **Step 5: Manual browser verification**
  1. Open a run at `/observability/:id`. Expected: title "Run #… · …", four KPI cards (cost, duration, cache-hit, tokens), a green "N× parallel speedup — …" badge (when ≥2 retrievers), and the span waterfall.
  2. If the trace carries `budgets`, KPI cards for a breached metric render in breach tone (red value + warning icon) with the budget shown as a sub-line.
  3. If the trace carries `langfuse_url`, a "View in Langfuse" button appears top-right and opens the external trace in a new tab.
  4. Toggle **Under the hood** → the waterfall gains a `$0.00….` cost column per row and a "Per-role cost" table appears (Classify/Plan/Retrieve/Resolve/Critique with tokens + cost). **Client view** hides both.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/waterfall.ts frontend/src/components/KpiCard.tsx frontend/src/pages/TraceDetailPage.tsx
git commit -m "feat(frontend): Run Inspector detail — breach-aware KPIs, per-role cost, speedup

Trace detail becomes the Run Inspector centerpiece: KpiCard cost/duration
cards flag budget breaches, a badge shows the sequential-vs-parallel
retrieval speedup (computed from span timestamps), and under-the-hood adds
a per-role cost table + span cost column. Adds a Langfuse deep-link button.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: Run-compare diff

A two-run side-by-side diff on the Run Inspector list: pick two runs, compare their headline metrics with per-metric deltas. Kept lightweight (list-level, no new route). Visible in both modes; under-the-hood adds token/retry rows.

**Files:**
- Modify: `frontend/src/pages/ObservabilityPage.tsx`

- [ ] **Step 1: Add compare selection + panel to `ObservabilityPage.tsx`**

Add to imports:

```tsx
import { getTrace, getTraces } from '../lib/api'
import type { TraceDetail, TraceListItem } from '../lib/types'
```

Add state (near the others):

```tsx
  const [compareIds, setCompareIds] = useState<number[]>([])
  const [compareData, setCompareData] = useState<TraceDetail[] | null>(null)
  const [comparing, setComparing] = useState(false)

  function toggleCompare(id: number) {
    setCompareIds((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id)
      if (prev.length >= 2) return [prev[1], id] // keep the last two picked
      return [...prev, id]
    })
    setCompareData(null)
  }

  async function runCompare() {
    if (compareIds.length !== 2) return
    setComparing(true)
    try {
      setCompareData(await Promise.all(compareIds.map((id) => getTrace(id))))
    } catch (e) {
      setError(String(e))
    } finally {
      setComparing(false)
    }
  }
```

Add a compare checkbox as the first cell of each row (before the `#` cell) — insert a new `<th>` and matching `<td>`:

In `<thead>`, add before the `#` header:

```tsx
                <th className="px-3 py-2 font-medium">⇄</th>
```

In the row, add before the `#` `<td>`:

```tsx
                    <td className="px-3 py-2">
                      <input
                        type="checkbox"
                        checked={compareIds.includes(t.id)}
                        onChange={() => toggleCompare(t.id)}
                        aria-label={`select run ${t.id} to compare`}
                      />
                    </td>
```

Add the compare panel immediately **before** the closing `</div>` of the outer `viz` container (after the table block):

```tsx
      {compareIds.length > 0 && (
        <div className="rounded-lg border border-border bg-primary/30 p-4">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-medium text-foreground">
              Compare runs {compareIds.map((id) => `#${id}`).join(' vs ')}
            </h2>
            <button
              type="button"
              onClick={runCompare}
              disabled={compareIds.length !== 2 || comparing}
              className="rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-background disabled:opacity-40"
            >
              {comparing ? 'Loading…' : compareIds.length === 2 ? 'Compare' : 'Pick 2 runs'}
            </button>
          </div>
          {compareData && compareData.length === 2 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs text-mutedForeground">
                    <th className="px-3 py-2 font-medium">Metric</th>
                    <th className="px-3 py-2 font-medium text-right">#{compareData[0].id}</th>
                    <th className="px-3 py-2 font-medium text-right">#{compareData[1].id}</th>
                    <th className="px-3 py-2 font-medium text-right">Δ</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    { label: 'Cost ($)', a: compareData[0].total_cost_usd, b: compareData[1].total_cost_usd, dp: 6 },
                    { label: 'Duration (s)', a: compareData[0].duration_seconds, b: compareData[1].duration_seconds, dp: 2 },
                    { label: 'Cache-hit (%)', a: compareData[0].cache_hit_pct, b: compareData[1].cache_hit_pct, dp: 1 },
                    { label: 'Tokens', a: compareData[0].total_tokens, b: compareData[1].total_tokens, dp: 0 },
                  ].map((m) => {
                    const delta = m.b - m.a
                    return (
                      <tr key={m.label} className="border-b border-border/60 last:border-0">
                        <td className="px-3 py-2">{m.label}</td>
                        <td className="px-3 py-2 text-right tabular-nums">{m.a.toFixed(m.dp)}</td>
                        <td className="px-3 py-2 text-right tabular-nums">{m.b.toFixed(m.dp)}</td>
                        <td
                          className="px-3 py-2 text-right tabular-nums"
                          style={{ color: delta === 0 ? undefined : delta > 0 ? 'var(--status-critical)' : 'var(--status-good)' }}
                        >
                          {delta > 0 ? '+' : ''}{delta.toFixed(m.dp)}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
```

- [ ] **Step 2: Typecheck / build** — `docker compose exec frontend npm run build`. Expected: succeeds.

- [ ] **Step 3: Manual browser verification**
  1. On `/observability`, tick the ⇄ checkbox on two runs → a "Compare runs #a vs #b" panel appears. Tick a third → the oldest selection drops (keeps the last two).
  2. Click **Compare** → a metric table shows both runs' cost/duration/cache-hit/tokens with a Δ column (green when run B is lower, red when higher).
  3. Untick both → the panel disappears.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ObservabilityPage.tsx
git commit -m "feat(frontend): run-compare diff on the Run Inspector list

Pick two runs via a row checkbox and compare cost/duration/cache-hit/tokens
side by side with per-metric deltas. List-level, no new route.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 11: Analytics section — embedded Langfuse dashboard

Add an "Analytics" section to the Run Inspector list that embeds a Langfuse public/shared dashboard (cost over time, latency percentiles, token trends) via `VITE_LANGFUSE_DASHBOARD_URL`. Falls back to an honest note when the env var is unset (per spec 06's embed-first / API-pull-fallback guidance — the note documents the fallback rather than half-building it). Under-the-hood-and-client both show it (charts are a manager ask), but the raw iframe URL is only revealed under-the-hood.

**Files:**
- Modify: `frontend/src/pages/ObservabilityPage.tsx`

- [ ] **Step 1: Add the Analytics section**

Add near the top of the component body:

```tsx
  const dashboardUrl = import.meta.env.VITE_LANGFUSE_DASHBOARD_URL as string | undefined
```

Insert the section immediately **after** the intro `<div>…</div>` (before the filters row):

```tsx
      <section className="rounded-lg border border-border bg-primary/30 p-4">
        <h2 className="mb-3 flex items-center gap-2 text-sm font-medium text-foreground">
          Analytics
          <span className="text-[10px] font-normal uppercase tracking-wide text-mutedForeground">Langfuse</span>
        </h2>
        {dashboardUrl ? (
          <>
            <div className="overflow-hidden rounded-lg border border-border">
              <iframe
                title="Langfuse dashboard"
                src={dashboardUrl}
                className="h-[420px] w-full bg-background"
                loading="lazy"
              />
            </div>
            {underTheHood && (
              <p className="mt-2 break-all text-[11px] text-mutedForeground">embed: {dashboardUrl}</p>
            )}
          </>
        ) : (
          <p className="text-sm text-mutedForeground">
            Set <code className="text-foreground">VITE_LANGFUSE_DASHBOARD_URL</code> to a Langfuse shared-dashboard
            URL to embed cost/latency/token charts here. (Iframes can be brittle behind auth/CSP; the documented
            fallback is pulling aggregates via the Langfuse public API into a Recharts panel — spec 06.)
          </p>
        )}
      </section>
```

- [ ] **Step 2: Typecheck / build** — `docker compose exec frontend npm run build`. Expected: succeeds.

- [ ] **Step 3: Manual browser verification**
  1. With `VITE_LANGFUSE_DASHBOARD_URL` unset, load `/observability` → the Analytics section shows the honest configuration note (no broken iframe).
  2. Set `VITE_LANGFUSE_DASHBOARD_URL` in `frontend/.env` to a Langfuse shared-dashboard URL, restart Vite → the dashboard renders in an embedded iframe. Toggle **Under the hood** → the raw embed URL line appears beneath it.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ObservabilityPage.tsx
git commit -m "feat(frontend): embed Langfuse analytics dashboard on the Run Inspector

Adds an Analytics section that iframes a Langfuse shared dashboard from
VITE_LANGFUSE_DASHBOARD_URL (cost/latency/token charts), with an honest
config/fallback note when unset. Under-the-hood reveals the embed URL.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 12: KB-browse panel (MCP resources)

A panel that browses the KB over MCP resources — `GET /mcp/kb` (`kb://index`) lists docs; clicking one fetches `GET /mcp/kb/{id}` (`kb://doc/{id}`) and shows its markdown. Proves MCP resources are real and application-addressable. Lives on the Run Inspector list (a technical surface). Shown in both modes; under-the-hood reveals each doc's `kb://` URI.

**Files:**
- Create: `frontend/src/components/KbBrowser.tsx`
- Modify: `frontend/src/pages/ObservabilityPage.tsx`

- [ ] **Step 1: Create `frontend/src/components/KbBrowser.tsx`**

```tsx
import { BookOpen } from '@phosphor-icons/react'
import { useEffect, useState } from 'react'
import { getKbDoc, getKbIndex } from '../lib/api'
import type { KbDocResource, KbIndexEntry } from '../lib/types'
import { useViewMode } from '../lib/viewMode'

export default function KbBrowser() {
  const { underTheHood } = useViewMode()
  const [index, setIndex] = useState<KbIndexEntry[] | null>(null)
  const [selected, setSelected] = useState<number | null>(null)
  const [doc, setDoc] = useState<KbDocResource | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [docError, setDocError] = useState<string | null>(null)

  useEffect(() => {
    getKbIndex()
      .then((r) => setIndex(r.resources))
      .catch((e) => setError(String(e)))
  }, [])

  async function open(id: number) {
    setSelected(id)
    setDoc(null)
    setDocError(null)
    try {
      setDoc(await getKbDoc(id))
    } catch (e) {
      setDocError(String(e))
    }
  }

  if (error) return null // MCP resources optional; hide the panel if the passthrough is down.

  return (
    <section className="rounded-lg border border-border bg-primary/30 p-4">
      <h2 className="mb-3 flex items-center gap-2 text-sm font-medium text-foreground">
        <BookOpen size={16} weight="regular" className="text-accent" />
        Knowledge base
        <span className="text-[10px] font-normal uppercase tracking-wide text-mutedForeground">via MCP kb://index</span>
      </h2>
      {!index && <p className="text-sm text-mutedForeground">Loading catalog…</p>}
      {index && (
        <div className="grid gap-4 sm:grid-cols-[16rem_1fr]">
          <ul className="max-h-72 space-y-1 overflow-y-auto">
            {index.map((r) => (
              <li key={r.id}>
                <button
                  type="button"
                  onClick={() => open(r.id)}
                  aria-pressed={selected === r.id}
                  className={`w-full rounded-md border px-3 py-2 text-left text-xs transition-colors ${
                    selected === r.id ? 'border-accent/60 bg-primary' : 'border-transparent hover:border-border hover:bg-primary/40'
                  }`}
                >
                  <span className="block text-foreground/90">{r.title}</span>
                  <span className="mt-0.5 block text-[10px] uppercase tracking-wide text-mutedForeground">
                    {r.source_type}
                    {underTheHood && <> · kb://doc/{r.id}</>}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          <div className="rounded-md border border-border bg-background p-3">
            {docError && <p className="text-xs text-destructive">{docError}</p>}
            {!doc && !docError && <p className="text-xs text-mutedForeground">Select a document to read it.</p>}
            {doc && (
              <>
                <p className="text-sm font-medium text-foreground">{doc.title}</p>
                {underTheHood && (
                  <p className="mb-2 text-[10px] uppercase tracking-wide text-mutedForeground">{doc.uri}</p>
                )}
                <pre className="mt-2 max-h-72 overflow-y-auto whitespace-pre-wrap text-xs leading-relaxed text-foreground/90">
                  {doc.markdown}
                </pre>
              </>
            )}
          </div>
        </div>
      )}
    </section>
  )
}
```

- [ ] **Step 2: Mount it on `ObservabilityPage.tsx`**

Add the import:

```tsx
import KbBrowser from '../components/KbBrowser'
```

Render `<KbBrowser />` immediately after the Analytics section (before the filters row).

- [ ] **Step 3: Typecheck / build** — `docker compose exec frontend npm run build`. Expected: succeeds.

- [ ] **Step 4: Manual browser verification**
  1. With the MCP passthrough up, load `/observability` → a "Knowledge base — via MCP kb://index" panel lists KB docs (title + source_type).
  2. Click a doc → its markdown renders in the right pane (fetched from `/mcp/kb/{id}`).
  3. Toggle **Under the hood** → each list item and the open doc show their `kb://doc/{id}` URI.
  4. Stop the MCP service and reload → the panel hides itself (the index fetch errors → `return null`); the rest of the page is unaffected.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/KbBrowser.tsx frontend/src/pages/ObservabilityPage.tsx
git commit -m "feat(frontend): KB-browse panel reading MCP kb://index + kb://doc resources

Lists the KB catalog from GET /mcp/kb and reads a doc's markdown from
GET /mcp/kb/{id}, proving MCP resources are real. Under-the-hood reveals
the kb:// URIs; the panel hides itself if the passthrough is down.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 13: Quality Dashboard — score cards, taxonomy bars, regression, failing-case drill

Reframe Evals as the "Quality Dashboard": headline score cards, the existing per-metric bars, a per-category **failure-taxonomy** bar panel, a **regression-vs-baseline** indicator, and a failing-case drill-down that adds the **retrieved context** alongside the existing judge reasoning. The ~11-min free-tier note and the lexical regression note are preserved. Client view leads with score cards + taxonomy; under-the-hood keeps the full per-case table.

**Files:**
- Create: `frontend/src/components/FailureTaxonomyBars.tsx`
- Modify: `frontend/src/pages/EvalsPage.tsx`

- [ ] **Step 1: Create `frontend/src/components/FailureTaxonomyBars.tsx`**

```tsx
import type { FailureTaxonomyBucket } from '../lib/types'

// Human labels for the spec-07 taxonomy keys; unknown keys fall back to the raw label.
const LABELS: Record<string, string> = {
  hallucinated_policy: 'Hallucinated policy',
  missed_citation: 'Missed citation',
  wrong_category: 'Wrong category',
  over_escalation: 'Over-escalation',
  under_escalation: 'Under-escalation',
}

export default function FailureTaxonomyBars({ buckets }: { buckets: FailureTaxonomyBucket[] }) {
  if (buckets.length === 0) {
    return <p className="text-sm text-mutedForeground">No failures recorded in this run.</p>
  }
  const max = Math.max(...buckets.map((b) => b.count), 1)
  return (
    <div className="space-y-2">
      {buckets.map((b) => (
        <div key={b.label} className="viz">
          <div className="mb-1 flex items-baseline justify-between">
            <span className="text-sm text-mutedForeground">{LABELS[b.label] ?? b.label}</span>
            <span className="text-sm font-semibold tabular-nums text-foreground">{b.count}</span>
          </div>
          <div className="h-2 rounded-full" style={{ background: 'var(--viz-gridline)' }}>
            <div
              className="h-full rounded-full"
              style={{ width: `${(b.count / max) * 100}%`, background: 'var(--status-critical)' }}
            />
          </div>
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 2: Update `EvalsPage.tsx`**

Add imports:

```tsx
import FailureTaxonomyBars from '../components/FailureTaxonomyBars'
import KpiCard from '../components/KpiCard'
import Badge from '../components/Badge'
import CitationBadge from '../components/CitationBadge'
import { useViewMode } from '../lib/viewMode'
```

Read the mode in the component body (near the other hooks):

```tsx
  const { underTheHood } = useViewMode()
```

Change the page title/intro:

```tsx
      <div>
        <h1 className="text-xl font-semibold text-foreground">Quality Dashboard</h1>
        <p className="text-sm text-mutedForeground">
          Golden-set scores for the Stripe payments support-triage agent, graded against real
          Stripe-docs-grounded retrieval — with a per-category failure taxonomy and regression gating.
        </p>
      </div>
```

Immediately after the `run && (` opening `<>`, and **before** the existing "Latest run" metrics section, insert the score cards, regression indicator, and taxonomy:

```tsx
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <KpiCard label="Classification" value={run.classification_accuracy.toFixed(2)} />
            <KpiCard label="Retrieval hit-rate" value={run.retrieval_hit_rate.toFixed(2)} />
            <KpiCard label="Faithfulness" value={run.faithfulness_avg.toFixed(2)} />
            <KpiCard label="Helpfulness" value={run.helpfulness_avg.toFixed(2)} />
          </div>

          {run.regression_failed != null && (
            <Badge tone={run.regression_failed ? 'destructive' : 'success'}>
              {run.regression_failed
                ? 'Regression vs baseline — quality dropped, gate would FAIL'
                : 'No regression vs baseline — gate PASSES'}
            </Badge>
          )}

          {run.failure_taxonomy && run.failure_taxonomy.length > 0 && (
            <section className="rounded-lg border border-border bg-primary/30 p-4">
              <h2 className="mb-3 text-sm font-medium text-foreground">Failure taxonomy (per category)</h2>
              <FailureTaxonomyBars buckets={run.failure_taxonomy} />
            </section>
          )}
```

In the existing per-metric section, extend the baseline note so it also reflects the stored baseline (not only a mode switch). Replace the `{previousRun && …}` block with:

```tsx
                  {run.baseline && (
                    <p className="mt-1 text-[11px] text-mutedForeground tabular-nums">
                      baseline: {(run.baseline[m.key as keyof typeof run.baseline] as number).toFixed(2)}
                    </p>
                  )}
                  {!run.baseline && previousRun && previousRun.retrieval_mode !== run.retrieval_mode && (
                    <p className="mt-1 text-[11px] text-mutedForeground tabular-nums">
                      vs {previousRun.retrieval_mode}: {(previousRun[m.key] as number).toFixed(2)}
                    </p>
                  )}
```

> `m.key` is a `keyof EvalRun`; `EvalBaseline` shares those six metric keys, so `m.key as keyof typeof run.baseline` is safe for the six METRICS entries.

Gate the per-case table behind under-the-hood (client view leads with cards + taxonomy; the dense table is the technical view). Wrap the existing `<section className="overflow-x-auto rounded-lg border border-border">…</section>` in:

```tsx
          {underTheHood && (
            <section className="overflow-x-auto rounded-lg border border-border">
              {/* …existing table… */}
            </section>
          )}
```

Finally, in the expanded failing-case row, add the retrieved context above the judge reasoning. Replace the expanded `<td>` content with:

```tsx
                        <td colSpan={8} className="space-y-2 px-3 py-3 text-xs text-mutedForeground">
                          {c.failure_labels && c.failure_labels.length > 0 && (
                            <div className="flex flex-wrap gap-1.5">
                              {c.failure_labels.map((l) => (
                                <Badge key={l} tone="destructive">{l}</Badge>
                              ))}
                            </div>
                          )}
                          {c.retrieved_context && c.retrieved_context.length > 0 && (
                            <p className="flex flex-wrap items-center gap-1.5">
                              <span className="font-medium text-foreground">Retrieved context:</span>
                              {c.retrieved_context.map((cc) => (
                                <CitationBadge key={cc.chunk_id} citation={cc} />
                              ))}
                            </p>
                          )}
                          <p><span className="font-medium text-foreground">Faithfulness reasoning:</span> {c.faithfulness_reasoning}</p>
                          <p><span className="font-medium text-foreground">Helpfulness reasoning:</span> {c.helpfulness_reasoning}</p>
                        </td>
```

- [ ] **Step 3: Typecheck / build** — `docker compose exec frontend npm run build`. Expected: succeeds.

- [ ] **Step 4: Manual browser verification**
  1. `http://localhost:5173/evals` → title reads "Quality Dashboard". With a stored run, four score cards (Classification / Retrieval / Faithfulness / Helpfulness) render above the per-metric bars.
  2. If the run carries `regression_failed`, a green "gate PASSES" or red "gate FAILS" badge shows; if it carries `failure_taxonomy`, a per-category failure bar panel renders. If `baseline` is present, each metric bar shows a "baseline: N.NN" sub-line.
  3. **Client view**: the dense per-case table is hidden. Toggle **Under the hood** → the full per-case table appears. Click a case row → the drill-down shows failure-label badges, "Retrieved context:" citation chips (clickable → KB doc), and the faithfulness/helpfulness judge reasoning.
  4. Click **Run eval** → the ~11-min free-tier note still shows while running; lexical mode still shows the regression-demo note.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/FailureTaxonomyBars.tsx frontend/src/pages/EvalsPage.tsx
git commit -m "feat(frontend): Quality Dashboard — score cards, failure taxonomy, regression, context drill

Reframes Evals as the Quality Dashboard: headline score cards, a per-category
failure-taxonomy bar panel, a regression-vs-baseline gate indicator, and a
failing-case drill-down that adds retrieved context (clickable citations)
next to the judge reasoning. Client view leads with cards+taxonomy;
under-the-hood keeps the dense per-case table.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review

**Spec 08 coverage**

*Global:*
- Client/Under-the-hood toggle, persisted, default Client → Task 1 (`viewMode.tsx` + `ViewModeToggle`). ✅
- Toggle switches all three screens → Triage (Tasks 5–7), Run Inspector (Tasks 8–12), Quality Dashboard (Task 13) all read `underTheHood`. ✅
- Light design-token pass, NOT full shadcn → Task 2 (semantic aliases + `Card`/`Badge`/`SectionHeading`; note explicitly rejects shadcn migration). ✅

*Triage:*
- Cleaner intake, KEEP live SSE timeline → Task 4 preserves the SSE `submit()` verbatim; timeline section unchanged. ✅
- Clickable citation chips → source span / `kb://doc/{id}` → Task 5 (`CitationBadge` opens `getKbDoc`; under-the-hood shows chunk/URI). ✅
- Category/priority/sentiment badges → existing `ClassificationChips` reused (Task 6 render path). ✅
- Reply card Send/Edit/Escalate + approval gate calling approve endpoint → Task 6 (`ReplyCard` + `EscalationGate` → `approveEscalation`). ✅
- Skill-loaded badge → Task 6 (`SkillBadge` from `skill_invocation`). ✅
- Keep How it works → untouched (`HowItWorks` still rendered in Task 4's TriagePage). ✅
- Optional MCP prompt quick-actions → Task 7. ✅

*Observability → Run Inspector:*
- KPI cards cost/latency/cache/tokens/budget breach flags → Task 9 (`KpiCard` breach tone). ✅
- Waterfall centerpiece → Task 9 (`SpanWaterfall`, dense under-the-hood). ✅
- Per-role cost → Task 9 (`perRoleCost`). ✅
- Run-compare → Task 10. ✅
- Filters → Task 8. ✅
- Analytics embedding Langfuse dashboard + per-ticket "View in Langfuse" deep link → Task 11 (embed) + Task 9 (deep-link button). ✅
- KB-browse panel reading `kb://index`/`kb://doc/{id}` → Task 12. ✅
- Seq-vs-parallel speedup number → Task 9 (`retrievalSpeedup`). ✅
- Retry/error events in the waterfall → Task 8 (retry marker; error `borderLeft` already present). ✅

*Evals → Quality Dashboard:*
- Score cards → Task 13 (`KpiCard`s). ✅
- Per-metric + per-category (taxonomy) bars → existing `MetricBar` + Task 13 `FailureTaxonomyBars`. ✅
- Regression-vs-baseline indicator → Task 13 (`regression_failed` badge + baseline sub-lines). ✅
- Run evals button + ~11-min note → preserved from existing `EvalsPage`. ✅
- Drill into failing case: retrieved context + judge reasoning → Task 13 (expanded row adds `retrieved_context` chips; existing reasoning kept). ✅

*Acceptance criteria:* toggle persists (A) ✅; chips resolve to source/resource (Task 5) ✅; escalate gate approve-commits / cancel-doesn't (Task 6) ✅; in-app waterfall+KPIs + embedded Langfuse + working deep link (Tasks 9,11) ✅; taxonomy bars + failing-case judge drill (Task 13) ✅; no backend URL/path changes — only additive Phase-C/D read endpoints under existing prefixes, zero backend code (Global Constraints) ✅.

**Placeholder scan:** No TBD/TODO/`...` placeholders; every new/modified file has complete code. Comment ellipses (`…`) are UI copy, not code gaps. ✅

**Prop/type consistency (against `types.ts` + assumed contracts):**
- `useViewMode()` returns `{ mode, setMode, underTheHood }` — consumed identically everywhere. ✅
- `Card` `tone` union `'default'|'muted'|'breach'` matches all call sites (`KpiCard`, `EscalationGate`). ✅
- `Badge` `tone` union `'neutral'|'accent'|'success'|'warning'|'destructive'` — every call site uses a member. ✅
- `SpanWaterfall({ rows, dense? })` — TriagePage calls without `dense` (defaults false, preserving live view); TraceDetail passes `dense={underTheHood}`. `WaterfallRow.cost?`/`retries?` already optional. ✅
- `CitationBadge({ citation: CitedChunk })` unchanged signature; new `doc_id?` optional field guarded before use. Reused by EvalsPage with `CitedChunk` entries. ✅
- `ReplyCard` `renderReply: (text, cited) => ReactNode` matches `renderReplyWithCitations(text, CitedChunk[])`. ✅
- `EscalationGate` calls `approveEscalation(ticketId: number, reason: string): Promise<EscalationHandle>` — matches `api.ts`. `ticketId` sourced from `escalation.ticket_id` (number) with `trace_id` (number) fallback — both numeric. ✅
- `SkillBadge({ skill: SkillInvocation })` — `skill.script`/`script_result` are `string|null`, guarded. ✅
- `perRoleCost`/`retrievalSpeedup` consume `SpanNode` (with optional `cost_usd`) and `TraceDetail.spans`; return types match `TraceDetailPage` usage. ✅
- `FailureTaxonomyBars({ buckets: FailureTaxonomyBucket[] })` — `EvalRun.failure_taxonomy?` guarded before render. ✅
- `EvalRun.baseline` indexed by `m.key as keyof typeof run.baseline`; `METRICS` keys are exactly the six `EvalBaseline` fields. ✅
- `api.ts` import list extended to include `EscalationHandle`, `KbDocResource`, `KbIndexEntry`, `McpPrompt` — all defined in Task 3. ✅

**Backend-contract assumptions (called out, all optional/graceful):** A1 `skill_invocation`, A2 `escalation`, A3 `POST /agent/escalate/approve`, A4 `SpanNode.cost_usd`, A5 `budgets`+breach, A6 `langfuse_url`+`VITE_LANGFUSE_DASHBOARD_URL`, A7 eval `failure_labels`/`retrieved_context`/`failure_taxonomy`/`baseline`/`regression_failed`, A8 `/mcp/kb`,`/mcp/kb/{id}`,`/mcp/prompts`+`CitedChunk.doc_id`. Every consumer hides its affordance when the field/endpoint is absent, so the app stays runnable if a Phase-C/D contract lands slightly differently. ✅

**Manual-verification discipline (matches the template plan):** every task ends with `docker compose exec frontend npm run build` (the `tsc -b` typecheck gate) + an explicit `http://localhost:5173` click-path with expected visual result, then a commit. No test-framework code introduced. ✅
