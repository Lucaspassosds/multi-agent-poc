import type { SpanNode, TraceDetail } from './types'

// The fixed, ordered identity mapping for span/step coloring (dataviz: "assign categorical hues
// in fixed order, never cycled"). Shared by both the live SSE timeline (Triage) and the
// retrospective span tree (Observability) so the same name always gets the same color.
export const SERIES_ORDER = [
  'agent', 'retriever', 'classifier', 'planner', 'resolver', 'critic', 'tool', 'llm_call',
] as const
export type SeriesKey = (typeof SERIES_ORDER)[number]

export const SERIES_LABEL: Record<SeriesKey, string> = {
  agent: 'Orchestrator',
  retriever: 'Retriever',
  classifier: 'Classifier',
  planner: 'Planner',
  resolver: 'Resolver',
  critic: 'Critic',
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
        error: s.error,
      })
      walk(s.children, depth + 1)
    }
  }
  walk(trace.spans, 0)
  return rows
}
