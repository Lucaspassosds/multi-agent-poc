import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import SpanWaterfall from '../components/SpanWaterfall'
import StatTile from '../components/StatTile'
import { getTrace } from '../lib/api'
import type { TraceDetail } from '../lib/types'
import { spanTreeToRows } from '../lib/waterfall'

export default function TraceDetailPage() {
  const { traceId } = useParams()
  const [trace, setTrace] = useState<TraceDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!traceId) return
    getTrace(Number(traceId)).then(setTrace).catch((e) => setError(String(e)))
  }, [traceId])

  return (
    <div className="space-y-4">
      <Link to="/observability" className="text-sm text-accent hover:underline">
        &larr; back to traces
      </Link>
      {error && <p className="text-sm text-destructive">{error}</p>}
      {!trace && !error && <p className="text-sm text-mutedForeground">Loading trace…</p>}
      {trace && (
        <>
          <h1 className="text-lg font-semibold text-foreground">
            Trace #{trace.id} · {trace.name}
          </h1>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatTile label="Total tokens" value={trace.total_tokens.toLocaleString()} />
            <StatTile label="Total cost" value={`$${trace.total_cost_usd.toFixed(6)}`} />
            <StatTile label="Cache-hit" value={`${trace.cache_hit_pct.toFixed(1)}%`} />
            <StatTile label="Duration" value={`${trace.duration_seconds.toFixed(2)}s`} />
          </div>
          <section className="rounded-lg border border-border bg-primary/30 p-4">
            <h2 className="text-sm font-medium text-foreground mb-3">Span waterfall</h2>
            <SpanWaterfall rows={spanTreeToRows(trace)} />
          </section>
        </>
      )}
    </div>
  )
}
