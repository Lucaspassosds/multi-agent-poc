// Mirrors backend/app/api_traces.py, api_evals.py, schema.sql, and the orchestrator.triage()
// result shape (backend/app/agents/orchestrator.py). Keep in sync by hand — no codegen for a POC.

export type SpanType = 'agent' | 'subagent' | 'tool' | 'llm_call'
export type TraceStatus = 'ok' | 'error'

export interface SpanNode {
  id: number
  parent_id: number | null
  name: string
  span_type: SpanType
  model: string | null
  started_at: string
  ended_at: string
  duration_seconds: number
  input_tokens: number
  output_tokens: number
  cache_read_tokens: number
  cache_creation_tokens: number
  // Per-span cost is NOT serialized by GET /traces/{id} (backend/app/api/traces.py only exposes
  // token counts per span; `cost_usd()` is applied to the run total and to /traces/stats per-role
  // rollups). Kept optional so a future backend that does emit it flows straight through — every
  // consumer must treat `undefined` as "unavailable", never as 0.
  cost_usd?: number
  retries: number
  error: string | null
  children: SpanNode[]
}

export interface TraceListItem {
  id: number
  name: string
  ticket_id: number | null
  status: TraceStatus
  started_at: string
  ended_at: string
  duration_seconds: number
  total_tokens: number
  total_cost_usd: number
  cache_hit_pct: number
  retries: number
  langfuse_url?: string | null // spec 06 deep-link (not on the list endpoint today)
  over_budget?: boolean // backend's combined cost-OR-latency flag (GET /traces)
  // Split out of `over_budget` in api.ts against the `budgets` limits the same response carries —
  // the backend collapses both breaches into one boolean, the table shows which one tripped.
  cost_breach?: boolean
  latency_breach?: boolean
}

export interface TraceDetail {
  id: number
  name: string
  ticket_id: number | null
  status: TraceStatus
  started_at: string
  ended_at: string
  duration_seconds: number
  total_tokens: number
  total_cost_usd: number
  cache_hit_pct: number
  spans: SpanNode[]
  over_budget?: boolean // backend's combined cost-OR-latency flag (GET /traces/{id})
  // Composed in api.ts: the detail endpoint returns only `over_budget`, so the limits come from
  // the `budgets` block on GET /traces and the two breaches are re-derived from them.
  budgets?: Budgets | null
  langfuse_trace_id?: string | null
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

export interface Classification {
  category: string
  priority: 'low' | 'medium' | 'high'
  sentiment: 'angry' | 'neutral' | 'happy'
}

export interface SubQuestions {
  questions: string[]
}

export interface CitedChunk {
  chunk_id: number
  doc_id?: number // KB document this chunk belongs to (spec 03) — lets a citation resolve to kb://doc/{id}
  title: string
  source_type: string
  snippet: string
}

export interface Evidence {
  subquestion: string
  summary: string
  cited: CitedChunk[]
  seconds: number
}

export interface Critique {
  verdict: 'approve' | 'revise'
  issues: string[]
  fixes: string[]
}

export interface Parallelism {
  retrievers: number
  parallel_seconds: number
  sequential_estimate_seconds: number
  speedup: number | null
}

export interface Usage {
  input_tokens: number
  output_tokens: number
  cached_tokens: number
}

export interface TriageResult {
  ticket: string
  classification: Classification
  subquestions: string[]
  evidence: Evidence[]
  draft: string
  critique: Critique
  revised: boolean
  skill_used: string | null
  final_reply: string
  parallelism: Parallelism
  usage: Usage
  total_seconds: number
  trace_id: number
  cost_usd: number
  skill_invocation?: SkillInvocation | null // spec 04
  escalation?: EscalationProposal | null // spec 05
}

export interface SkillInvocation {
  name: string
  script: string | null
  script_result: string | null
}

/** A proposal from the gated `escalate` tool (backend/app/tools/registry.py::EscalateResult).
 * The tool writes nothing — it mints a `handle` ("ESC-<hex8>") that POST /agent/escalations
 * later commits. The current triage pipeline does not surface a proposal on its result at all,
 * so every field beyond `proposed`/`reason` is optional and the UI hides the gate when absent. */
export interface EscalationProposal {
  proposed: boolean
  reason: string
  handle?: string
  severity?: 'low' | 'medium' | 'high'
  ticket_ref?: string | null
  ticket_id?: number | null // a saved `tickets` row id — required for the ticket-status write
  preview?: string
}

/** Response of POST /agent/escalations (backend/app/api/escalations.py::approve). */
export interface EscalationHandle {
  id: number
  handle: string
  status: string
  assignee: string | null
  decided_at: string
  ticket_id: number | null
}

export type TriageStep = 'classify' | 'plan' | 'retrieve' | 'resolve' | 'critique' | 'revise'

export interface TriageStepStartEvent {
  type: 'step_start'
  step: TriageStep
  index?: number
  subquestion?: string
}

export interface TriageStepDoneEvent {
  type: 'step_done'
  step: TriageStep
  index?: number
  data: Classification | SubQuestions | Evidence | { draft: string } | Critique | { revised: string }
}

export interface TriageFinalEvent {
  type: 'final'
  result: TriageResult
}

export interface TriageErrorEvent {
  type: 'error'
  message: string
}

export type TriageEvent = TriageStepStartEvent | TriageStepDoneEvent | TriageFinalEvent | TriageErrorEvent

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

export type RetrievalMode = 'lexical' | 'semantic' | 'hybrid'

export interface EvalRun {
  id: number
  retrieval_mode: RetrievalMode
  started_at: string
  ended_at: string
  n_cases: number
  classification_accuracy: number
  priority_accuracy: number
  retrieval_hit_rate: number
  citation_coverage: number
  faithfulness_avg: number
  helpfulness_avg: number
  total_cost_usd: number
  cases: EvalCase[]
  // Mapped in api.ts from the backend's `failure_breakdown` dict ({label: count}).
  failure_taxonomy?: FailureTaxonomyBucket[]
  // Mapped in api.ts from the backend's `regression` boolean.
  regression_failed?: boolean
  // PARTIAL by construction: the backend only exposes baseline numbers through
  // `regression_detail` on POST /evals/run, and only for the metrics that actually regressed
  // (GET /evals exposes none at all — baseline.json is server-side only). Consumers must guard
  // the individual metric they read, not just this container.
  baseline?: Partial<EvalBaseline> | null
}

export interface TicketListItem {
  id: number
  ticket_text: string
  category: string | null
  trace_id: number | null
  created_at: string
}

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

export type MetricsChart = 'observations' | 'cost' | 'latency' | 'scores'

export interface MetricsPoint {
  t: string // ISO date, e.g. "2026-07-24"
  v: number
}

export interface MetricsSeries {
  label: string
  points: MetricsPoint[]
}

/** GET /observability/metrics/{chart} (backend/app/langfuse_metrics.py). Fails soft — when
 * Langfuse is disabled or the call errors, `available` is false and `series` is absent. */
export interface MetricsChartResponse {
  available: boolean
  reason?: string
  chart?: MetricsChart
  granularity?: string
  series?: MetricsSeries[]
  cached?: boolean
}
