import type { Evidence, SpanNode, TraceDetail } from './types'

// The fixed, ordered identity mapping for span/step coloring (dataviz: "assign categorical hues
// in fixed order, never cycled"). Shared by both the live SSE timeline (Triage) and the
// retrospective span tree (Observability) so the same name always gets the same color.
export const SERIES_ORDER = [
  'agent', 'retriever', 'classifier', 'planner', 'resolver', 'critic', 'tool', 'llm_call',
] as const
export type SeriesKey = (typeof SERIES_ORDER)[number]

export const SERIES_LABEL: Record<SeriesKey, string> = {
  agent: 'Orchestrator',
  retriever: 'Retrieve',
  classifier: 'Classify',
  planner: 'Plan',
  resolver: 'Resolve',
  critic: 'Critique',
  tool: 'Tool call',
  llm_call: 'LLM call',
}

export function seriesKeyForName(name: string): SeriesKey {
  if (name.startsWith('retriever')) return 'retriever'
  if (name.startsWith('resolver')) return 'resolver'
  if (name === 'classifier') return 'classifier'
  if (name === 'planner') return 'planner'
  if (name === 'critic') return 'critic'
  if (name.startsWith('tool:')) return 'tool'
  if (name === 'llm_call') return 'llm_call'
  return 'agent'
}

export type RowStatus = 'ok' | 'error' | 'pending' | 'running'

export interface WaterfallRow {
  id: string
  label: string
  seriesKey: SeriesKey
  status: RowStatus
  depth: number
  startOffset: number // seconds from the timeline's own start
  duration: number | null // seconds; null while pending/running (renders as a skeleton pulse)
  model?: string | null
  inputTokens?: number
  outputTokens?: number
  cacheReadTokens?: number
  retries?: number
  cost?: number
  error?: string | null
}

/** Flattens a persisted span tree (GET /traces/{id}) into rows for SpanWaterfall, offsetting
 * every timestamp from the trace's own start so the x-axis reads as elapsed seconds. */
export function spanTreeToRows(trace: TraceDetail): WaterfallRow[] {
  const traceStart = new Date(trace.started_at).getTime()
  const rows: WaterfallRow[] = []

  function walk(spans: SpanNode[], depth: number) {
    for (const s of spans) {
      const startOffset = (new Date(s.started_at).getTime() - traceStart) / 1000
      const duration = s.duration_seconds
      rows.push({
        id: String(s.id),
        label: s.name,
        seriesKey: seriesKeyForName(s.name),
        status: s.error ? 'error' : 'ok',
        depth,
        startOffset,
        duration,
        model: s.model,
        inputTokens: s.input_tokens,
        outputTokens: s.output_tokens,
        cacheReadTokens: s.cache_read_tokens,
        retries: s.retries,
        cost: s.cost_usd,
        error: s.error,
      })
      walk(s.children, depth + 1)
    }
  }
  walk(trace.spans, 0)
  return rows
}

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
      cost: s.cost_usd,
      error: s.error,
    }
  })
}

export interface RoleCost {
  seriesKey: SeriesKey
  label: string
  /** null when NO span in this role reported a cost. GET /traces/{id} does not serialize per-span
   * cost today (see SpanNode.cost_usd), so this is normally null for every role — callers must
   * render it as "unavailable" and must not print $0.000000, which would be confidently wrong. */
  cost: number | null
  tokens: number
}

/** Per-role cost + token rollup for the Run Inspector, summed over the span tree by series. */
export function perRoleCost(trace: TraceDetail): RoleCost[] {
  const byKey = new Map<SeriesKey, RoleCost>()
  function walk(spans: SpanNode[]) {
    for (const s of spans) {
      const key = seriesKeyForName(s.name)
      const cur = byKey.get(key) ?? { seriesKey: key, label: SERIES_LABEL[key], cost: null, tokens: 0 }
      if (s.cost_usd != null) cur.cost = (cur.cost ?? 0) + s.cost_usd
      cur.tokens += (s.input_tokens ?? 0) + (s.output_tokens ?? 0)
      byKey.set(key, cur)
      walk(s.children)
    }
  }
  walk(trace.spans)
  return SERIES_ORDER.map((k) => byKey.get(k)).filter(
    (r): r is RoleCost => !!r && ((r.cost != null && r.cost > 0) || r.tokens > 0),
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
