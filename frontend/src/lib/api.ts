import type { EvalRun, RetrievalMode, TraceDetail, TraceListItem } from './types'

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

export function getEvals(): Promise<EvalRun> {
  return getJSON('/evals')
}

export function runEvals(retrievalMode: RetrievalMode): Promise<EvalRun> {
  return postJSON(`/evals/run?retrieval_mode=${retrievalMode}`)
}

export function ingest(fetchDocs: boolean, reset: boolean): Promise<unknown> {
  return postJSON(`/ingest?fetch=${fetchDocs}&reset=${reset}`)
}
