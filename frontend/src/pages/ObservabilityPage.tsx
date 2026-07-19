import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getTraces } from '../lib/api'
import type { TraceListItem } from '../lib/types'

const PAGE_SIZE = 20

export default function ObservabilityPage() {
  const [traces, setTraces] = useState<TraceListItem[] | null>(null)
  const [total, setTotal] = useState(0)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getTraces(PAGE_SIZE, 0)
      .then((r) => { setTraces(r.traces); setTotal(r.total) })
      .catch((e) => setError(String(e)))
  }, [])

  async function loadMore() {
    if (!traces) return
    setLoadingMore(true)
    try {
      const r = await getTraces(PAGE_SIZE, traces.length)
      setTraces([...traces, ...r.traces])
      setTotal(r.total)
    } catch (e) {
      setError(String(e))
    } finally {
      setLoadingMore(false)
    }
  }

  return (
    <div className="viz space-y-4">
      <h1 className="text-lg font-semibold text-foreground">Observability</h1>
      {error && <p className="text-sm text-destructive">{error}</p>}
      {!traces && !error && <p className="text-sm text-mutedForeground">Loading traces…</p>}
      {traces && traces.length === 0 && (
        <p className="text-sm text-mutedForeground">No traces yet — submit a ticket on the Triage screen first.</p>
      )}
      {traces && traces.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-mutedForeground">
                <th className="px-3 py-2 font-medium">#</th>
                <th className="px-3 py-2 font-medium">Name</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2 font-medium text-right">Duration</th>
                <th className="px-3 py-2 font-medium text-right">Tokens</th>
                <th className="px-3 py-2 font-medium text-right">Cost</th>
                <th className="px-3 py-2 font-medium text-right">Cache-hit</th>
                <th className="px-3 py-2 font-medium text-right">Retries</th>
              </tr>
            </thead>
            <tbody>
              {traces.map((t) => (
                <tr key={t.id} className="border-b border-border/60 last:border-0 hover:bg-primary/40">
                  <td className="px-3 py-2">
                    <Link to={`/observability/${t.id}`} className="text-accent hover:underline">
                      {t.id}
                    </Link>
                  </td>
                  <td className="px-3 py-2">{t.name}</td>
                  <td className="px-3 py-2">
                    <span
                      className="inline-flex items-center gap-1.5 text-xs"
                      style={{ color: t.status === 'ok' ? 'var(--status-good)' : 'var(--status-critical)' }}
                    >
                      <span
                        className="w-1.5 h-1.5 rounded-full inline-block"
                        style={{ background: t.status === 'ok' ? 'var(--status-good)' : 'var(--status-critical)' }}
                      />
                      {t.status}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">{t.duration_seconds.toFixed(2)}s</td>
                  <td className="px-3 py-2 text-right tabular-nums">{t.total_tokens.toLocaleString()}</td>
                  <td className="px-3 py-2 text-right tabular-nums">${t.total_cost_usd.toFixed(6)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{t.cache_hit_pct.toFixed(1)}%</td>
                  <td className="px-3 py-2 text-right tabular-nums">{t.retries}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex items-center justify-between px-3 py-2 text-xs text-mutedForeground border-t border-border">
            <span>Showing {traces.length} of {total}</span>
            {traces.length < total && (
              <button
                type="button"
                onClick={loadMore}
                disabled={loadingMore}
                className="rounded-md border border-border px-3 py-1 text-foreground hover:border-accent/50 disabled:opacity-40"
              >
                {loadingMore ? 'Loading…' : 'Load more'}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
