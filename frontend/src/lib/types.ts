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
}

export interface TicketListItem {
  id: number
  ticket_text: string
  category: string | null
  trace_id: number | null
  created_at: string
}
