import { API_BASE } from './api'
import type { RetrievalMode, TriageEvent } from './types'

// The triage stream is POSTed (the ticket message is a body, not a query string), so it can't
// use EventSource (GET-only) — this reads the fetch() ReadableStream by hand and splits on the
// backend's `data: ...\n\n` framing (same convention as GET /llm/stream), stopping at `[DONE]`.
export async function* streamTriage(
  message: string,
  opts: { skill?: boolean; searchMode?: RetrievalMode } = {},
): AsyncGenerator<TriageEvent> {
  const params = new URLSearchParams()
  if (opts.skill !== undefined) params.set('skill', String(opts.skill))
  if (opts.searchMode) params.set('search_mode', opts.searchMode)

  const res = await fetch(`${API_BASE}/agent/triage/stream?${params}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  })
  if (!res.ok || !res.body) {
    throw new Error(`triage stream failed: ${res.status} ${await res.text().catch(() => '')}`)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let boundary: number
    while ((boundary = buffer.indexOf('\n\n')) !== -1) {
      const raw = buffer.slice(0, boundary)
      buffer = buffer.slice(boundary + 2)
      const payload = raw.startsWith('data: ') ? raw.slice('data: '.length) : raw
      if (payload === '[DONE]') return
      yield JSON.parse(payload) as TriageEvent
    }
  }
}
