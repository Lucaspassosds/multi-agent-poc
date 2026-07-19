import { Fragment, useRef, useState } from 'react'
import ClassificationChips from '../components/ClassificationChips'
import CitationBadge from '../components/CitationBadge'
import SpanWaterfall from '../components/SpanWaterfall'
import { streamTriage } from '../lib/sse'
import type { CitedChunk, Classification, TriageResult } from '../lib/types'
import { seriesKeyForName, type WaterfallRow } from '../lib/waterfall'

const PRESETS = [
  'I was charged twice for my subscription this month, please refund the duplicate.',
  'My card was declined but the money still left my account.',
  'I want to cancel my subscription and get a prorated refund.',
]

const STEP_LABEL: Record<string, string> = {
  classify: 'classifier',
  plan: 'planner',
  retrieve: 'retriever',
  resolve: 'resolver',
  critique: 'critic',
  revise: 'resolver:revision',
}

function upsertRow(rows: WaterfallRow[], row: WaterfallRow): WaterfallRow[] {
  const idx = rows.findIndex((r) => r.id === row.id)
  if (idx === -1) return [...rows, row]
  const next = [...rows]
  next[idx] = { ...next[idx], ...row }
  return next
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
  const [running, setRunning] = useState(false)
  const [rows, setRows] = useState<WaterfallRow[]>([])
  const [result, setResult] = useState<TriageResult | null>(null)
  const [classification, setClassification] = useState<Classification | null>(null)
  const [error, setError] = useState<string | null>(null)
  const startedAt = useRef(0)
  const rowStart = useRef<Map<string, number>>(new Map())

  async function submit(msg: string) {
    setRunning(true)
    setRows([])
    setResult(null)
    setClassification(null)
    setError(null)
    startedAt.current = performance.now()
    rowStart.current = new Map()

    const elapsed = () => (performance.now() - startedAt.current) / 1000

    try {
      for await (const event of streamTriage(msg)) {
        if (event.type === 'step_start') {
          const id = event.step === 'retrieve' ? `retrieve-${event.index}` : event.step
          const label = event.step === 'retrieve'
            ? (event.subquestion?.slice(0, 24) ?? `retrieve #${event.index}`)
            : STEP_LABEL[event.step]
          rowStart.current.set(id, elapsed())
          setRows((prev) => upsertRow(prev, {
            id,
            label,
            seriesKey: seriesKeyForName(event.step === 'retrieve' ? 'retriever' : STEP_LABEL[event.step]),
            status: 'running',
            depth: event.step === 'retrieve' ? 1 : 0,
            startOffset: elapsed(),
            duration: null,
          }))
        } else if (event.type === 'step_done') {
          const id = event.step === 'retrieve' ? `retrieve-${event.index}` : event.step
          const start = rowStart.current.get(id) ?? elapsed()
          setRows((prev) => upsertRow(prev, {
            id,
            label: prev.find((r) => r.id === id)?.label ?? event.step,
            seriesKey: prev.find((r) => r.id === id)?.seriesKey ?? seriesKeyForName(event.step),
            status: 'ok',
            depth: event.step === 'retrieve' ? 1 : 0,
            startOffset: start,
            duration: elapsed() - start,
          }))
          if (event.step === 'classify') setClassification(event.data as Classification)
        } else if (event.type === 'final') {
          setResult(event.result)
        } else if (event.type === 'error') {
          setError(event.message)
        }
      }
    } catch (e) {
      setError(String(e))
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="space-y-6">
      <section>
        <h1 className="text-lg font-semibold text-foreground mb-3">Submit a ticket</h1>
        <textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          rows={4}
          placeholder="Describe the customer's issue…"
          className="w-full rounded-lg border border-border bg-primary p-3 text-sm text-foreground placeholder:text-mutedForeground focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
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
          className="mt-4 rounded-md bg-accent px-4 py-2 text-sm font-medium text-background disabled:opacity-40 disabled:cursor-not-allowed"
        >
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
          <h2 className="text-sm font-medium text-foreground mb-3">Agent timeline</h2>
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
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-sm font-medium text-foreground">Final reply</h2>
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
  )
}
