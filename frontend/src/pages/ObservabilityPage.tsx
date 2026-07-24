import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Warning } from '@phosphor-icons/react'
import Badge from '../components/Badge'
import KbBrowser from '../components/KbBrowser'
import { getTrace, getTraces } from '../lib/api'
import type { TraceDetail, TraceListItem } from '../lib/types'
import { useViewMode } from '../lib/viewMode'

const PAGE_SIZE = 20

export default function ObservabilityPage() {
  const { underTheHood } = useViewMode()
  const dashboardUrl = import.meta.env.VITE_LANGFUSE_DASHBOARD_URL as string | undefined
  const [traces, setTraces] = useState<TraceListItem[] | null>(null)
  const [total, setTotal] = useState(0)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState<'all' | 'ok' | 'error'>('all')
  const [nameFilter, setNameFilter] = useState('')
  const [compareIds, setCompareIds] = useState<number[]>([])
  const [compareData, setCompareData] = useState<TraceDetail[] | null>(null)
  const [comparing, setComparing] = useState(false)

  function toggleCompare(id: number) {
    setCompareIds((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id)
      if (prev.length >= 2) return [prev[1], id] // keep the last two picked
      return [...prev, id]
    })
    setCompareData(null)
  }

  async function runCompare() {
    if (compareIds.length !== 2) return
    setComparing(true)
    try {
      setCompareData(await Promise.all(compareIds.map((id) => getTrace(id))))
    } catch (e) {
      setError(String(e))
    } finally {
      setComparing(false)
    }
  }

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

  const filtered = useMemo(() => {
    if (!traces) return []
    const q = nameFilter.trim().toLowerCase()
    return traces.filter(
      (t) =>
        (statusFilter === 'all' || t.status === statusFilter) &&
        (q === '' || t.name.toLowerCase().includes(q)),
    )
  }, [traces, statusFilter, nameFilter])

  return (
    <div className="viz space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Run Inspector</h1>
        <p className="text-sm text-mutedForeground">
          Every triage run, fully traced — duration, tokens, cost, cache-hit, parallelism, retries.
          {underTheHood
            ? ' Open a run for the span waterfall, per-role cost, budget breaches, and the Langfuse deep link.'
            : ' Open a run to see how the pipeline spent its time.'}
        </p>
      </div>

      {/* The run list is this screen's subject, so it comes first — the Langfuse embed and the KB
          browser are supporting panels and render below it (both view modes). */}
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-xs text-mutedForeground">
          Status
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as 'all' | 'ok' | 'error')}
            className="ml-2 rounded border border-border bg-background px-2 py-1 text-xs text-foreground"
          >
            <option value="all">all</option>
            <option value="ok">ok</option>
            <option value="error">error</option>
          </select>
        </label>
        <input
          value={nameFilter}
          onChange={(e) => setNameFilter(e.target.value)}
          placeholder="filter by name…"
          className="rounded border border-border bg-background px-2 py-1 text-xs text-foreground placeholder:text-mutedForeground focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
        />
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}
      {!traces && !error && <p className="text-sm text-mutedForeground">Loading runs…</p>}
      {traces && traces.length === 0 && (
        <p className="text-sm text-mutedForeground">No runs yet — submit a ticket on the Triage screen first.</p>
      )}
      {traces && traces.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-mutedForeground">
                <th className="px-3 py-2 font-medium">⇄</th>
                <th className="px-3 py-2 font-medium">#</th>
                <th className="px-3 py-2 font-medium">Name</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2 font-medium text-right">Duration</th>
                <th className="px-3 py-2 font-medium text-right">Tokens</th>
                <th className="px-3 py-2 font-medium text-right">Cost</th>
                <th className="px-3 py-2 font-medium text-right">Cache-hit</th>
                {underTheHood && <th className="px-3 py-2 font-medium text-right">Retries</th>}
                <th className="px-3 py-2 font-medium">Budget</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((t) => {
                const breached = t.cost_breach || t.latency_breach
                return (
                  <tr key={t.id} className="border-b border-border/60 last:border-0 hover:bg-primary/40">
                    <td className="px-3 py-2">
                      <input
                        type="checkbox"
                        checked={compareIds.includes(t.id)}
                        onChange={() => toggleCompare(t.id)}
                        aria-label={`select run ${t.id} to compare`}
                      />
                    </td>
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
                          className="inline-block h-1.5 w-1.5 rounded-full"
                          style={{ background: t.status === 'ok' ? 'var(--status-good)' : 'var(--status-critical)' }}
                        />
                        {t.status}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">{t.duration_seconds.toFixed(2)}s</td>
                    <td className="px-3 py-2 text-right tabular-nums">{t.total_tokens.toLocaleString()}</td>
                    <td className="px-3 py-2 text-right tabular-nums">${t.total_cost_usd.toFixed(6)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{t.cache_hit_pct.toFixed(1)}%</td>
                    {underTheHood && <td className="px-3 py-2 text-right tabular-nums">{t.retries}</td>}
                    <td className="px-3 py-2">
                      {breached ? (
                        <Badge tone="destructive">
                          <Warning size={12} weight="fill" />
                          {t.cost_breach && t.latency_breach ? 'cost + latency' : t.cost_breach ? 'cost' : 'latency'}
                        </Badge>
                      ) : (
                        <span className="text-xs text-mutedForeground">—</span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          <div className="flex items-center justify-between border-t border-border px-3 py-2 text-xs text-mutedForeground">
            <span>Showing {filtered.length} of {total}</span>
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

      {compareIds.length > 0 && (
        <div className="rounded-lg border border-border bg-primary/30 p-4">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-medium text-foreground">
              Compare runs {compareIds.map((id) => `#${id}`).join(' vs ')}
            </h2>
            <button
              type="button"
              onClick={runCompare}
              disabled={compareIds.length !== 2 || comparing}
              className="rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-background disabled:opacity-40"
            >
              {comparing ? 'Loading…' : compareIds.length === 2 ? 'Compare' : 'Pick 2 runs'}
            </button>
          </div>
          {compareData && compareData.length === 2 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs text-mutedForeground">
                    <th className="px-3 py-2 font-medium">Metric</th>
                    <th className="px-3 py-2 font-medium text-right">#{compareData[0].id}</th>
                    <th className="px-3 py-2 font-medium text-right">#{compareData[1].id}</th>
                    <th className="px-3 py-2 font-medium text-right">Δ</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    { label: 'Cost ($)', a: compareData[0].total_cost_usd, b: compareData[1].total_cost_usd, dp: 6 },
                    { label: 'Duration (s)', a: compareData[0].duration_seconds, b: compareData[1].duration_seconds, dp: 2 },
                    { label: 'Cache-hit (%)', a: compareData[0].cache_hit_pct, b: compareData[1].cache_hit_pct, dp: 1 },
                    { label: 'Tokens', a: compareData[0].total_tokens, b: compareData[1].total_tokens, dp: 0 },
                  ].map((m) => {
                    const delta = m.b - m.a
                    return (
                      <tr key={m.label} className="border-b border-border/60 last:border-0">
                        <td className="px-3 py-2">{m.label}</td>
                        <td className="px-3 py-2 text-right tabular-nums">{m.a.toFixed(m.dp)}</td>
                        <td className="px-3 py-2 text-right tabular-nums">{m.b.toFixed(m.dp)}</td>
                        <td
                          className="px-3 py-2 text-right tabular-nums"
                          style={{ color: delta === 0 ? undefined : delta > 0 ? 'var(--status-critical)' : 'var(--status-good)' }}
                        >
                          {delta > 0 ? '+' : ''}{delta.toFixed(m.dp)}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      <section className="rounded-lg border border-border bg-primary/30 p-4">
        <h2 className="mb-3 flex items-center gap-2 text-sm font-medium text-foreground">
          Analytics
          <span className="text-[10px] font-normal uppercase tracking-wide text-mutedForeground">Langfuse</span>
        </h2>
        {dashboardUrl ? (
          <>
            <div className="overflow-hidden rounded-lg border border-border">
              <iframe
                title="Langfuse dashboard"
                src={dashboardUrl}
                className="h-[420px] w-full bg-background"
                loading="lazy"
              />
            </div>
            {underTheHood && (
              <p className="mt-2 break-all text-[11px] text-mutedForeground">embed: {dashboardUrl}</p>
            )}
          </>
        ) : (
          <p className="text-sm text-mutedForeground">
            Set <code className="text-foreground">VITE_LANGFUSE_DASHBOARD_URL</code> to a Langfuse shared-dashboard
            URL to embed cost/latency/token charts here. (Iframes can be brittle behind auth/CSP; the documented
            fallback is pulling aggregates via the Langfuse public API into a Recharts panel — spec 06.)
          </p>
        )}
      </section>

      <KbBrowser />
    </div>
  )
}
