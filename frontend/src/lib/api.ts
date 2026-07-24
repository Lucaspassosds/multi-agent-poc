import type {
  EscalationHandle,
  EvalBaseline,
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

export const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000'

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`)
  if (!res.ok) throw new Error(`${path} -> ${res.status} ${await res.text()}`)
  return res.json() as Promise<T>
}

async function postJSON<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`${path} -> ${res.status} ${await res.text()}`)
  return res.json() as Promise<T>
}

// --- Budget reconciliation ------------------------------------------------- //
// The backend (backend/app/api/traces.py) reports ONE combined flag per trace — `over_budget`,
// true when cost > cost_budget_usd OR duration > latency_budget_ms — and publishes the two limits
// only on the collection endpoints (`GET /traces` and `GET /traces/stats` both carry a
// `budgets: {cost_budget_usd, latency_budget_ms}` block). The UI wants them separately (to label
// which budget tripped and to print the limit next to the KPI), so we split the flag back out with
// the backend's own comparison, against the backend's own limits. No thresholds live here.

interface BudgetLimits {
  cost_budget_usd: number
  latency_budget_ms: number
}

type RawTraceListItem = Omit<TraceListItem, 'cost_breach' | 'latency_breach'>
type RawTraceDetail = Omit<TraceDetail, 'budgets'>

let budgetLimitsCache: Promise<BudgetLimits> | null = null

/** The limits, fetched once from the list endpoint (they are static config, not per-trace data). */
function budgetLimits(): Promise<BudgetLimits> {
  if (!budgetLimitsCache) {
    budgetLimitsCache = getJSON<{ budgets: BudgetLimits }>('/traces?limit=1&offset=0')
      .then((r) => r.budgets)
      .catch((e) => {
        budgetLimitsCache = null // don't cache a failure
        throw e
      })
  }
  return budgetLimitsCache
}

function breaches(costUsd: number, durationSeconds: number, limits: BudgetLimits) {
  return {
    cost_breach: costUsd > limits.cost_budget_usd,
    latency_breach: durationSeconds * 1000 > limits.latency_budget_ms,
  }
}

export async function getTraces(
  limit = 20,
  offset = 0,
): Promise<{ traces: TraceListItem[]; total: number }> {
  const raw = await getJSON<{ traces: RawTraceListItem[]; total: number; budgets: BudgetLimits }>(
    `/traces?limit=${limit}&offset=${offset}`,
  )
  budgetLimitsCache = Promise.resolve(raw.budgets)
  return {
    total: raw.total,
    traces: raw.traces.map((t) => ({ ...t, ...breaches(t.total_cost_usd, t.duration_seconds, raw.budgets) })),
  }
}

export async function getTrace(id: number): Promise<TraceDetail> {
  const [raw, limits] = await Promise.all([
    getJSON<RawTraceDetail>(`/traces/${id}`),
    // A missing budgets block must not break the run view — it only costs the budget annotations.
    budgetLimits().catch(() => null),
  ])
  if (!limits) return raw
  return {
    ...raw,
    budgets: {
      cost_usd: raw.total_cost_usd,
      cost_limit_usd: limits.cost_budget_usd,
      latency_seconds: raw.duration_seconds,
      latency_limit_seconds: limits.latency_budget_ms / 1000,
      ...breaches(raw.total_cost_usd, raw.duration_seconds, limits),
    },
  }
}

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

// --- Eval-run reconciliation ------------------------------------------------ //
// backend/app/api/evals.py + evals/runner.py name these differently than the UI does:
//   failure_breakdown  {label: count} dict   → failure_taxonomy  {label, count}[] (sorted desc)
//   regression         bool                  → regression_failed
//   regression_detail  {metric: {baseline, current}} → baseline (POST /evals/run only, and only
//                      for the metrics that tripped the gate — GET /evals exposes none).

interface RawEvalRun extends Omit<EvalRun, 'failure_taxonomy' | 'regression_failed' | 'baseline'> {
  failure_breakdown?: Record<string, number> | null
  regression?: boolean | null
  regression_detail?: Record<string, { baseline: number; current: number }> | null
}

function mapEvalRun(raw: RawEvalRun): EvalRun {
  const { failure_breakdown, regression, regression_detail, ...rest } = raw
  const baseline = Object.fromEntries(
    Object.entries(regression_detail ?? {}).map(([metric, d]) => [metric, d.baseline]),
  ) as Partial<EvalBaseline>
  return {
    ...rest,
    failure_taxonomy: Object.entries(failure_breakdown ?? {})
      .map(([label, count]) => ({ label, count }))
      .sort((a, b) => b.count - a.count),
    regression_failed: regression ?? undefined,
    baseline: Object.keys(baseline).length > 0 ? baseline : null,
  }
}

export function getEvals(): Promise<EvalRun> {
  return getJSON<RawEvalRun>('/evals').then(mapEvalRun)
}

export function runEvals(retrievalMode: RetrievalMode): Promise<EvalRun> {
  return postJSON<RawEvalRun>(`/evals/run?retrieval_mode=${retrievalMode}`).then(mapEvalRun)
}

export function ingest(fetchDocs: boolean, reset: boolean): Promise<unknown> {
  return postJSON(`/ingest?fetch=${fetchDocs}&reset=${reset}`)
}

// --- Phase E: gated escalate (spec 05). Called ONLY on human approval. ---
// POST /agent/escalations is the ONLY writer (backend/app/api/escalations.py::approve): it inserts
// the `escalations` row and flips the linked ticket to 'escalated'. `handle` is required and unique
// — re-approving the same handle returns 409, which is the intended double-commit guard.
export function approveEscalation(input: {
  handle: string
  reason: string
  severity?: 'low' | 'medium' | 'high'
  ticketId?: number | null
  ticketRef?: string | null
}): Promise<EscalationHandle> {
  return postJSON('/agent/escalations', {
    handle: input.handle,
    reason: input.reason,
    severity: input.severity ?? 'medium',
    ticket_id: input.ticketId ?? null,
    ticket_ref: input.ticketRef ?? null,
  })
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
