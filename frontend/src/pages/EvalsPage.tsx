import { Fragment, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import MetricBar from '../components/MetricBar'
import { getEvals, runEvals } from '../lib/api'
import type { EvalRun, RetrievalMode } from '../lib/types'

const METRICS: Array<{ key: keyof EvalRun; label: string }> = [
  { key: 'classification_accuracy', label: 'Classification accuracy' },
  { key: 'priority_accuracy', label: 'Priority accuracy' },
  { key: 'retrieval_hit_rate', label: 'Retrieval hit-rate' },
  { key: 'citation_coverage', label: 'Citation coverage' },
  { key: 'faithfulness_avg', label: 'Faithfulness (LLM judge)' },
  { key: 'helpfulness_avg', label: 'Helpfulness (LLM judge)' },
]

export default function EvalsPage() {
  const [run, setRun] = useState<EvalRun | null>(null)
  const [previousRun, setPreviousRun] = useState<EvalRun | null>(null)
  const [loadNote, setLoadNote] = useState<string | null>(null)
  const [mode, setMode] = useState<RetrievalMode>('hybrid')
  const [running, setRunning] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [runError, setRunError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const intervalRef = useRef<number | undefined>(undefined)

  useEffect(() => {
    getEvals()
      .then(setRun)
      .catch(() => setLoadNote('No eval runs yet — click "Run eval" below.'))
  }, [])

  async function handleRun() {
    setRunning(true)
    setRunError(null)
    setElapsed(0)
    intervalRef.current = window.setInterval(() => setElapsed((e) => e + 1), 1000)
    try {
      const result = await runEvals(mode)
      setPreviousRun(run)
      setRun(result)
      setLoadNote(null)
    } catch (e) {
      setRunError(String(e))
    } finally {
      window.clearInterval(intervalRef.current)
      setRunning(false)
    }
  }

  function toggle(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  return (
    <div className="viz space-y-4">
      <h1 className="text-lg font-semibold text-foreground">Evals</h1>

      <section className="rounded-lg border border-border bg-primary p-4 flex flex-wrap items-center gap-3">
        <label className="text-sm text-mutedForeground">
          Retrieval mode
          <select
            value={mode}
            onChange={(e) => setMode(e.target.value as RetrievalMode)}
            disabled={running}
            className="ml-2 rounded border border-border bg-background px-2 py-1 text-sm text-foreground"
          >
            <option value="hybrid">hybrid</option>
            <option value="semantic">semantic</option>
            <option value="lexical">lexical</option>
          </select>
        </label>
        <button
          type="button"
          onClick={handleRun}
          disabled={running}
          className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-background disabled:opacity-40"
        >
          {running ? `Running… ${elapsed}s` : 'Run eval'}
        </button>
        {running && (
          <p className="text-xs text-mutedForeground">
            This can take up to <strong>~11 minutes</strong> — the golden set is 20 cases and the
            Gemini free tier caps at 15 requests/minute, so each case waits out its own rate limit.
            This is expected, not a hang.
          </p>
        )}
        {mode === 'lexical' && !running && (
          <p className="text-xs text-mutedForeground w-full">
            Regression demo: lexical-only retrieval is expected to tank hit-rate/citation/faithfulness
            while classification accuracy stays roughly the same (it doesn't depend on retrieval).
          </p>
        )}
      </section>

      {runError && <p className="text-sm text-destructive">{runError}</p>}
      {loadNote && !run && <p className="text-sm text-mutedForeground">{loadNote}</p>}

      {run && (
        <>
          <section className="rounded-lg border border-border bg-primary/30 p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-medium text-foreground">
                Latest run — {run.retrieval_mode} · {run.n_cases} cases
              </h2>
              <span className="text-xs text-mutedForeground tabular-nums">
                total cost ${run.total_cost_usd.toFixed(4)}
              </span>
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {METRICS.map((m) => (
                <div key={m.key}>
                  <MetricBar label={m.label} value={run[m.key] as number} />
                  {previousRun && previousRun.retrieval_mode !== run.retrieval_mode && (
                    <p className="mt-1 text-[11px] text-mutedForeground tabular-nums">
                      vs {previousRun.retrieval_mode}: {(previousRun[m.key] as number).toFixed(2)}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </section>

          <section className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-mutedForeground">
                  <th className="px-3 py-2 font-medium">Case</th>
                  <th className="px-3 py-2 font-medium">Category</th>
                  <th className="px-3 py-2 font-medium">Priority</th>
                  <th className="px-3 py-2 font-medium text-right">Hit</th>
                  <th className="px-3 py-2 font-medium text-right">Coverage</th>
                  <th className="px-3 py-2 font-medium text-right">Faithful.</th>
                  <th className="px-3 py-2 font-medium text-right">Helpful.</th>
                  <th className="px-3 py-2 font-medium text-right">Trace</th>
                </tr>
              </thead>
              <tbody>
                {run.cases.map((c) => (
                  <Fragment key={c.golden_id}>
                    <tr
                      className="border-b border-border/60 hover:bg-primary/40 cursor-pointer"
                      onClick={() => toggle(c.golden_id)}
                    >
                      <td className="px-3 py-2 max-w-[16rem] truncate" title={c.ticket}>{c.ticket}</td>
                      <td className="px-3 py-2" style={{ color: c.category_correct ? 'var(--status-good)' : 'var(--status-critical)' }}>
                        {c.predicted_category}{!c.category_correct && ` (expected ${c.expected_category})`}
                      </td>
                      <td className="px-3 py-2" style={{ color: c.priority_correct ? 'var(--status-good)' : 'var(--status-critical)' }}>
                        {c.predicted_priority}{!c.priority_correct && ` (expected ${c.expected_priority})`}
                      </td>
                      <td className="px-3 py-2 text-right" style={{ color: c.retrieval_hit ? 'var(--status-good)' : 'var(--status-critical)' }}>
                        {c.retrieval_hit ? 'yes' : 'no'}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums">{c.citation_coverage.toFixed(2)}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{c.faithfulness_score.toFixed(2)}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{c.helpfulness_score.toFixed(2)}</td>
                      <td className="px-3 py-2 text-right">
                        {c.trace_id != null && (
                          <Link
                            to={`/observability/${c.trace_id}`}
                            onClick={(e) => e.stopPropagation()}
                            className="text-accent hover:underline"
                          >
                            #{c.trace_id}
                          </Link>
                        )}
                      </td>
                    </tr>
                    {expanded.has(c.golden_id) && (
                      <tr className="border-b border-border/60 bg-primary/20">
                        <td colSpan={8} className="px-3 py-3 text-xs text-mutedForeground space-y-1.5">
                          <p><span className="text-foreground font-medium">Faithfulness reasoning:</span> {c.faithfulness_reasoning}</p>
                          <p><span className="text-foreground font-medium">Helpfulness reasoning:</span> {c.helpfulness_reasoning}</p>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </section>
        </>
      )}
    </div>
  )
}
