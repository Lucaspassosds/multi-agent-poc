import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Warning } from '@phosphor-icons/react'
import Badge from '../components/Badge'
import KbBrowser from '../components/KbBrowser'
import MetricsChart from '../components/MetricsChart'
import { getMetrics, getTrace, getTraces } from '../lib/api'
import type { MetricsChart as MetricsChartKey, MetricsChartResponse, TraceDetail, TraceListItem } from '../lib/types'
import { useViewMode } from '../lib/viewMode'

const PAGE_SIZE = 20

// One row per Analytics chart: which Langfuse Metrics API query it maps to (backend enum),
// how its value is formatted, and its color assignment. Latency is one measure at three
// depths (an ORDINAL scale) so it gets the sequential blue ramp; scores are independent
// named metrics (categorical identity) so they get the app's fixed categorical hue order —
// per the dataviz skill, hues are assigned by the job color does, never picked by eye.
const ANALYTICS_CHARTS: {
  key: MetricsChartKey
  title: string
  colors: string[]
  emptyNote: string
  formatValue: (v: number) => string
}[] = [
  {
    key: 'observations',
    title: 'Observations',
    colors: ['var(--series-1)'],
    emptyNote: 'No observations in this window.',
    formatValue: (v) => v.toLocaleString(),
  },
  {
    key: 'cost',
    title: 'Total cost (USD)',
    colors: ['var(--series-1)'],
    emptyNote: 'No cost data in this window.',
    formatValue: (v) => `$${v.toFixed(6)}`,
  },
  {
    key: 'latency',
    title: 'Latency — p50 / p95 / p99 (seconds)',
    colors: ['var(--seq-blue-300)', 'var(--seq-blue-450)', 'var(--seq-blue-600)'],
    emptyNote: 'No latency data in this window.',
    formatValue: (v) => `${v.toFixed(1)}s`,
  },
  {
    key: 'scores',
    title: 'Eval scores — average by name',
    colors: [
      'var(--series-1)', 'var(--series-2)', 'var(--series-3)', 'var(--series-4)',
      'var(--series-5)', 'var(--series-6)', 'var(--series-7)', 'var(--series-8)',
    ],
    emptyNote: 'No eval scores in this window — run an eval on the Quality Dashboard.',
    formatValue: (v) => v.toFixed(2),
  },
]

const RANGE_PRESETS = [
  { hours: 24, label: '24h' },
  { hours: 24 * 7, label: '7d' },
  { hours: 24 * 30, label: '30d' }, // capped at 30d — Langfuse Hobby-tier retention (spec 06)
]

export default function ObservabilityPage() {
  const { underTheHood } = useViewMode()
  const [traces, setTraces] = useState<TraceListItem[] | null>(null)
  const [total, setTotal] = useState(0)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState<'all' | 'ok' | 'error'>('all')
  const [nameFilter, setNameFilter] = useState('')
  const [compareIds, setCompareIds] = useState<number[]>([])
  const [compareData, setCompareData] = useState<TraceDetail[] | null>(null)
  const [comparing, setComparing] = useState(false)
  const [rangeHours, setRangeHours] = useState(24 * 7)
  const [granularity, setGranularity] = useState<'hour' | 'day'>('day')
  const [metricsData, setMetricsData] = useState<Record<MetricsChartKey, MetricsChartResponse | null>>({
    observations: null, cost: null, latency: null, scores: null,
  })
  const [metricsLoading, setMetricsLoading] = useState(false)

  useEffect(() => {
    setMetricsLoading(true)
    Promise.all(
      ANALYTICS_CHARTS.map((c) =>
        getMetrics(c.key, granularity, rangeHours).catch((e) => ({ available: false, reason: String(e) })),
      ),
    ).then((results) => {
      setMetricsData(Object.fromEntries(ANALYTICS_CHARTS.map((c, i) => [c.key, results[i]])) as Record<
        MetricsChartKey,
        MetricsChartResponse
      >)
      setMetricsLoading(false)
    })
  }, [rangeHours, granularity])

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

        {/* One filter row, above every chart it scopes — per the dataviz skill's convention. */}
        <div className="mb-3 flex flex-wrap items-center gap-3">
          <div className="flex gap-1">
            {RANGE_PRESETS.map((r) => (
              <button
                key={r.hours}
                type="button"
                onClick={() => setRangeHours(r.hours)}
                className={`rounded-full border px-3 py-1 text-xs ${
                  rangeHours === r.hours
                    ? 'border-accent/40 bg-accent/10 text-accent'
                    : 'border-border text-mutedForeground hover:text-foreground'
                }`}
              >
                {r.label}
              </button>
            ))}
          </div>
          <label className="text-xs text-mutedForeground">
            Granularity
            <select
              value={granularity}
              onChange={(e) => setGranularity(e.target.value as 'hour' | 'day')}
              className="ml-2 rounded border border-border bg-background px-2 py-1 text-xs text-foreground"
            >
              <option value="hour">hourly</option>
              <option value="day">daily</option>
            </select>
          </label>
        </div>

        {ANALYTICS_CHARTS.every((c) => metricsData[c.key]?.available === false) ? (
          <p className="text-sm text-mutedForeground">
            {metricsData.observations?.reason ?? 'Langfuse metrics are unavailable right now.'}
          </p>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {ANALYTICS_CHARTS.map((c) => {
              const data = metricsData[c.key]
              if (data && data.available === false) {
                return (
                  <div key={c.key} className="rounded-lg border border-border bg-background/40 p-3 text-xs text-mutedForeground">
                    {c.title}: {data.reason ?? 'unavailable'}
                  </div>
                )
              }
              return (
                <MetricsChart
                  key={c.key}
                  title={c.title}
                  series={data?.series ?? []}
                  colors={c.colors}
                  loading={metricsLoading}
                  emptyNote={c.emptyNote}
                  formatValue={c.formatValue}
                />
              )
            })}
          </div>
        )}

        {underTheHood && (
          <p className="mt-2 text-[11px] text-mutedForeground">
            window: last {RANGE_PRESETS.find((r) => r.hours === rangeHours)?.label} · granularity {granularity} ·{' '}
            {Object.values(metricsData).some((d) => d?.cached) ? 'cache hit' : 'fresh'}
          </p>
        )}
      </section>

      <KbBrowser />
    </div>
  )
}
