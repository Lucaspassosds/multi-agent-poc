import { CheckCircle, PaperPlaneTilt, Waveform } from '@phosphor-icons/react'
import { Fragment, useEffect, useRef, useState } from 'react'
import ClassificationChips from '../components/ClassificationChips'
import CitationBadge from '../components/CitationBadge'
import HowItWorks from '../components/HowItWorks'
import SpanWaterfall from '../components/SpanWaterfall'
import TicketSidebar from '../components/TicketSidebar'
import { getTicket, getTickets, getTrace } from '../lib/api'
import { getOrCreateSessionId } from '../lib/session'
import { streamTriage } from '../lib/sse'
import type { CitedChunk, Classification, TicketListItem, TriageResult } from '../lib/types'
import { seriesKeyForName, triageRestoreRows, type WaterfallRow } from '../lib/waterfall'

const PRESETS = [
  'I was charged twice for my subscription this month, please refund the duplicate.',
  'My card was declined but the money still left my account.',
  'I want to cancel my subscription and get a prorated refund.',
]

// Maps an SSE step to the backend span-name vocabulary seriesKeyForName() understands, purely
// for color lookup — kept separate from the plain-language STEP_DISPLAY_LABEL shown to the user.
const STEP_SERIES_NAME: Record<string, string> = {
  classify: 'classifier',
  plan: 'planner',
  retrieve: 'retriever',
  resolve: 'resolver',
  critique: 'critic',
  revise: 'resolver:revision',
}

// Plain-language row labels — match the "How it works" step cards' titles exactly.
const STEP_DISPLAY_LABEL: Record<string, string> = {
  classify: 'Classify',
  plan: 'Plan',
  resolve: 'Resolve',
  critique: 'Critique',
  revise: 'Resolve (revision)',
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
  const [tickets, setTickets] = useState<TicketListItem[]>([])
  const [viewingId, setViewingId] = useState<number | null>(null)
  const startedAt = useRef(0)
  const rowStart = useRef<Map<string, number>>(new Map())
  const sessionId = useRef<string>(getOrCreateSessionId())

  async function refreshTickets() {
    try {
      const { tickets } = await getTickets(sessionId.current)
      setTickets(tickets)
    } catch {
      // History is non-critical; a failed refresh should never block triage.
    }
  }

  useEffect(() => {
    void refreshTickets()
  }, [])

  function newTicket() {
    setViewingId(null)
    setMessage('')
    setRows([])
    setResult(null)
    setClassification(null)
    setError(null)
  }

  async function selectTicket(id: number) {
    if (running) return
    setViewingId(id)
    setError(null)
    setRows([])
    setResult(null)
    setClassification(null)
    try {
      const res = await getTicket(id)
      setResult(res)
      setClassification(res.classification)
      if (res.trace_id) {
        const trace = await getTrace(res.trace_id)
        setRows(triageRestoreRows(trace, res.evidence))
      }
    } catch (e) {
      setError(String(e))
    }
  }

  async function submit(msg: string) {
    setRunning(true)
    setViewingId(null)
    setRows([])
    setResult(null)
    setClassification(null)
    setError(null)
    startedAt.current = performance.now()
    rowStart.current = new Map()

    const elapsed = () => (performance.now() - startedAt.current) / 1000
    let gotFinal = false

    try {
      for await (const event of streamTriage(msg, { sessionId: sessionId.current })) {
        if (event.type === 'step_start') {
          const id = event.step === 'retrieve' ? `retrieve-${event.index}` : event.step
          const label = event.step === 'retrieve'
            ? `Retrieve — ${event.subquestion ?? `#${event.index}`}`
            : STEP_DISPLAY_LABEL[event.step]
          rowStart.current.set(id, elapsed())
          setRows((prev) => upsertRow(prev, {
            id,
            label,
            seriesKey: seriesKeyForName(event.step === 'retrieve' ? 'retriever' : STEP_SERIES_NAME[event.step]),
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
            label: prev.find((r) => r.id === id)?.label ?? STEP_DISPLAY_LABEL[event.step] ?? event.step,
            seriesKey: prev.find((r) => r.id === id)?.seriesKey ?? seriesKeyForName(STEP_SERIES_NAME[event.step] ?? event.step),
            status: 'ok',
            depth: event.step === 'retrieve' ? 1 : 0,
            startOffset: start,
            duration: elapsed() - start,
          }))
          if (event.step === 'classify') setClassification(event.data as Classification)
        } else if (event.type === 'final') {
          setResult(event.result)
          gotFinal = true
        } else if (event.type === 'error') {
          setError(event.message)
        }
      }
    } catch (e) {
      setError(String(e))
    } finally {
      setRunning(false)
    }

    // Clear the composer only on a clean run; keep the text on error so the user can retry.
    if (gotFinal) {
      setMessage('')
      void refreshTickets()
    }
  }

  return (
    <div className="flex gap-6">
      <TicketSidebar
        tickets={tickets}
        selectedId={viewingId}
        disabled={running}
        onSelect={selectTicket}
        onNew={newTicket}
      />

      <div className="flex-1 space-y-6">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Stripe payments support triage</h1>
          <p className="mt-1 text-sm text-mutedForeground">
            Submit a Stripe payments support ticket — refunds, disputes, failed charges, subscription
            billing — and watch a multi-agent pipeline classify, research (grounded in real Stripe
            documentation), draft, and self-check a reply in real time.
          </p>
        </div>

        <HowItWorks />

        <section className="rounded-lg border border-border bg-primary p-4">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-mutedForeground">Submit a ticket</h2>
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            rows={4}
            placeholder="Describe the customer's issue…"
            className="w-full rounded-lg border border-border bg-background p-3 text-sm text-foreground placeholder:text-mutedForeground focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
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
            className="mt-4 inline-flex items-center gap-2 rounded-md bg-accent px-4 py-2 text-sm font-medium text-background disabled:cursor-not-allowed disabled:opacity-40"
          >
            <PaperPlaneTilt size={16} weight="bold" />
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
            <h2 className="mb-3 flex items-center gap-2 text-sm font-medium text-foreground">
              <Waveform size={16} weight="regular" className="text-accent" />
              Agent timeline
            </h2>
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
              <div className="mb-2 flex items-center justify-between">
                <h2 className="flex items-center gap-2 text-sm font-medium text-foreground">
                  <CheckCircle size={16} weight="regular" className="text-accent" />
                  Final reply
                </h2>
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
    </div>
  )
}
