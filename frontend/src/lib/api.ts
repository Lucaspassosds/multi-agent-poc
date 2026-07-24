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

export function getTraces(limit = 20, offset = 0): Promise<{ traces: TraceListItem[]; total: number }> {
  return getJSON(`/traces?limit=${limit}&offset=${offset}`)
}

export function getTrace(id: number): Promise<TraceDetail> {
  return getJSON(`/traces/${id}`)
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

export function getEvals(): Promise<EvalRun> {
  return getJSON('/evals')
}

export function runEvals(retrievalMode: RetrievalMode): Promise<EvalRun> {
  return postJSON(`/evals/run?retrieval_mode=${retrievalMode}`)
}

export function ingest(fetchDocs: boolean, reset: boolean): Promise<unknown> {
  return postJSON(`/ingest?fetch=${fetchDocs}&reset=${reset}`)
}

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
