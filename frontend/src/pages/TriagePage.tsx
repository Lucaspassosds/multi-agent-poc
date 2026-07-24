import { CheckCircle, PaperPlaneTilt, Waveform } from '@phosphor-icons/react'
import { Fragment, useEffect, useReducer, useRef, useState } from 'react'
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

// --- Grouped run state (deferred Phase-B cleanup): one reducer instead of six useState. ---
interface RunState {
  status: 'idle' | 'running' | 'done' | 'error'
  rows: WaterfallRow[]
  result: TriageResult | null
  classification: Classification | null
  error: string | null
  viewingId: number | null // non-null while revisiting a past ticket
}

const IDLE: RunState = {
  status: 'idle',
  rows: [],
  result: null,
  classification: null,
  error: null,
  viewingId: null,
}

type RunAction =
  | { type: 'reset' }
  | { type: 'start' }
  | { type: 'upsertRow'; row: WaterfallRow }
  | { type: 'classification'; value: Classification }
  | { type: 'result'; value: TriageResult }
  | { type: 'error'; message: string }
  | { type: 'finish' }
  | { type: 'viewStart'; id: number }
  | { type: 'viewLoaded'; result: TriageResult; rows: WaterfallRow[] }

function upsert(rows: WaterfallRow[], row: WaterfallRow): WaterfallRow[] {
  const idx = rows.findIndex((r) => r.id === row.id)
  if (idx === -1) return [...rows, row]
  const next = [...rows]
  next[idx] = { ...next[idx], ...row }
  return next
}

function runReducer(state: RunState, action: RunAction): RunState {
  switch (action.type) {
    case 'reset':
      return IDLE
    case 'start':
      return { ...IDLE, status: 'running' }
    case 'upsertRow':
      return { ...state, rows: upsert(state.rows, action.row) }
    case 'classification':
      return { ...state, classification: action.value }
    case 'result':
      return { ...state, result: action.value }
    case 'error':
      return { ...state, status: 'error', error: action.message }
    case 'finish':
      return state.status === 'error' ? state : { ...state, status: 'done' }
    case 'viewStart':
      return { ...IDLE, viewingId: action.id }
    case 'viewLoaded':
      return {
        ...state,
        status: 'done',
        result: action.result,
        classification: action.result.classification,
        rows: action.rows,
      }
    default:
      return state
  }
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
  const [tickets, setTickets] = useState<TicketListItem[]>([])
  const [state, dispatch] = useReducer(runReducer, IDLE)
  const running = state.status === 'running'
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
    setMessage('')
    dispatch({ type: 'reset' })
  }

  async function selectTicket(id: number) {
    if (running) return
    dispatch({ type: 'viewStart', id })
    try {
      const res = await getTicket(id)
      let rows: WaterfallRow[] = []
      if (res.trace_id) {
        const trace = await getTrace(res.trace_id)
        rows = triageRestoreRows(trace, res.evidence)
      }
      dispatch({ type: 'viewLoaded', result: res, rows })
    } catch (e) {
      dispatch({ type: 'error', message: String(e) })
    }
  }

  async function submit(msg: string) {
    dispatch({ type: 'start' })
    startedAt.current = performance.now()
    rowStart.current = new Map()
    // Deviation from the plan's target code (flagged, not silent — see task-4-report.md):
    // TriageStepDoneEvent has no `subquestion` field, so recomputing the retrieve row's label
    // from `event.index` alone at step_done would regress the visible label from
    // "Retrieve — <subquestion text>" (set at step_start) to a bare "Retrieve — #N" the moment
    // the row finishes — a guaranteed-every-run visual change, since the backend always sends
    // `subquestion` on step_start (see orchestrator.py `_retrieve_emit`). This local map
    // remembers each retrieve row's step_start label so step_done can reuse it verbatim,
    // preserving today's behavior exactly — the same pattern `rowStart` already uses to track
    // per-row timing outside React state.
    const retrieveLabels = new Map<string, string>()

    const elapsed = () => (performance.now() - startedAt.current) / 1000
    let gotFinal = false

    try {
      for await (const event of streamTriage(msg, { sessionId: sessionId.current })) {
        if (event.type === 'step_start') {
          const id = event.step === 'retrieve' ? `retrieve-${event.index}` : event.step
          const label = event.step === 'retrieve'
            ? `Retrieve — ${event.subquestion ?? `#${event.index}`}`
            : STEP_DISPLAY_LABEL[event.step]
          if (event.step === 'retrieve') retrieveLabels.set(id, label)
          rowStart.current.set(id, elapsed())
          dispatch({
            type: 'upsertRow',
            row: {
              id,
              label,
              seriesKey: seriesKeyForName(event.step === 'retrieve' ? 'retriever' : STEP_SERIES_NAME[event.step]),
              status: 'running',
              depth: event.step === 'retrieve' ? 1 : 0,
              startOffset: elapsed(),
              duration: null,
            },
          })
        } else if (event.type === 'step_done') {
          const id = event.step === 'retrieve' ? `retrieve-${event.index}` : event.step
          const start = rowStart.current.get(id) ?? elapsed()
          dispatch({
            type: 'upsertRow',
            row: {
              id,
              label: event.step === 'retrieve'
                ? (retrieveLabels.get(id) ?? `Retrieve — #${event.index}`)
                : STEP_DISPLAY_LABEL[event.step] ?? event.step,
              seriesKey: seriesKeyForName(event.step === 'retrieve' ? 'retriever' : STEP_SERIES_NAME[event.step] ?? event.step),
              status: 'ok',
              depth: event.step === 'retrieve' ? 1 : 0,
              startOffset: start,
              duration: elapsed() - start,
            },
          })
          if (event.step === 'classify') dispatch({ type: 'classification', value: event.data as Classification })
        } else if (event.type === 'final') {
          dispatch({ type: 'result', value: event.result })
          gotFinal = true
        } else if (event.type === 'error') {
          dispatch({ type: 'error', message: event.message })
        }
      }
    } catch (e) {
      dispatch({ type: 'error', message: String(e) })
    } finally {
      dispatch({ type: 'finish' })
    }

    // Clear the composer only on a clean run; keep the text on error so the user can retry.
    if (gotFinal) {
      setMessage('')
      void refreshTickets()
    }
  }

  const { rows, result, classification, error, viewingId } = state

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
