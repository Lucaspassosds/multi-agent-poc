import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowSquareOut } from '@phosphor-icons/react'
import KpiCard from '../components/KpiCard'
import SpanWaterfall from '../components/SpanWaterfall'
import Badge from '../components/Badge'
import { getTrace } from '../lib/api'
import type { TraceDetail } from '../lib/types'
import { perRoleCost, retrievalSpeedup, spanTreeToRows } from '../lib/waterfall'
import { useViewMode } from '../lib/viewMode'

export default function TraceDetailPage() {
  const { traceId } = useParams()
  const { underTheHood } = useViewMode()
  const [trace, setTrace] = useState<TraceDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!traceId) return
    getTrace(Number(traceId)).then(setTrace).catch((e) => setError(String(e)))
  }, [traceId])

  const speedup = trace ? retrievalSpeedup(trace) : null
  const roles = trace ? perRoleCost(trace) : []

  return (
    <div className="viz space-y-4">
      <Link to="/observability" className="text-sm text-accent hover:underline">
        &larr; back to runs
      </Link>
      {error && <p className="text-sm text-destructive">{error}</p>}
      {!trace && !error && <p className="text-sm text-mutedForeground">Loading run…</p>}
      {trace && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h1 className="text-xl font-semibold text-foreground">
              Run #{trace.id} · {trace.name}
            </h1>
            {trace.langfuse_url && (
              <a
                href={trace.langfuse_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs text-foreground hover:border-accent/50"
              >
                <ArrowSquareOut size={14} weight="regular" />
                View in Langfuse
              </a>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <KpiCard label="Total cost" value={`$${trace.total_cost_usd.toFixed(6)}`}
              sub={trace.budgets ? `budget $${trace.budgets.cost_limit_usd.toFixed(4)}` : undefined}
              breach={trace.budgets?.cost_breach ?? false} />
            <KpiCard label="Duration" value={`${trace.duration_seconds.toFixed(2)}s`}
              sub={trace.budgets ? `budget ${trace.budgets.latency_limit_seconds.toFixed(1)}s` : undefined}
              breach={trace.budgets?.latency_breach ?? false} />
            <KpiCard label="Cache-hit" value={`${trace.cache_hit_pct.toFixed(1)}%`} />
            <KpiCard label="Total tokens" value={trace.total_tokens.toLocaleString()} />
          </div>

          {speedup && (
            <Badge tone="success">
              {speedup.speedup.toFixed(1)}× parallel speedup — {speedup.sequential.toFixed(2)}s of retrieval done in {speedup.parallel.toFixed(2)}s wall-clock
            </Badge>
          )}

          <section className="rounded-lg border border-border bg-primary/30 p-4">
            <h2 className="mb-3 text-sm font-medium text-foreground">Span waterfall</h2>
            <SpanWaterfall rows={spanTreeToRows(trace)} dense={underTheHood} />
          </section>

          {underTheHood && roles.length > 0 && (
            <section className="rounded-lg border border-border bg-primary/30 p-4">
              <h2 className="mb-3 text-sm font-medium text-foreground">Per-role cost</h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border text-left text-xs text-mutedForeground">
                      <th className="px-3 py-2 font-medium">Role</th>
                      <th className="px-3 py-2 font-medium text-right">Tokens</th>
                      <th className="px-3 py-2 font-medium text-right">Cost</th>
                    </tr>
                  </thead>
                  <tbody>
                    {roles.map((r) => (
                      <tr key={r.seriesKey} className="border-b border-border/60 last:border-0">
                        <td className="px-3 py-2">{r.label}</td>
                        <td className="px-3 py-2 text-right tabular-nums">{r.tokens.toLocaleString()}</td>
                        <td className="px-3 py-2 text-right tabular-nums">${r.cost.toFixed(6)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}
        </>
      )}
    </div>
  )
}
