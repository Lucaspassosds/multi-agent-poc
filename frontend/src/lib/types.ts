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
  cost_usd?: number // per-span cost (spec 06); absent on older traces
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
  langfuse_url?: string | null // spec 06 deep-link
  cost_breach?: boolean // spec 06 budget flag
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
  failure_taxonomy?: FailureTaxonomyBucket[] // spec 07 aggregate
  baseline?: EvalBaseline | null // spec 07 regression baseline
  regression_failed?: boolean // spec 07 gate result
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
