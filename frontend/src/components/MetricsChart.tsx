import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { MetricsSeries } from '../lib/types'

interface MetricsChartProps {
  title: string
  series: MetricsSeries[]
  colors: string[] // one CSS color per series, same order as `series` — fixed, never cycled
  loading?: boolean
  emptyNote: string // shown when there is no data to plot at all
  formatValue?: (v: number) => string
}

interface Row {
  t: string
  [seriesLabel: string]: string | number
}

function mergeRows(series: MetricsSeries[]): Row[] {
  const byDate = new Map<string, Row>()
  for (const s of series) {
    for (const p of s.points) {
      const row = byDate.get(p.t) ?? { t: p.t }
      row[s.label] = p.v
      byDate.set(p.t, row)
    }
  }
  return [...byDate.values()].sort((a, b) => a.t.localeCompare(b.t))
}

function TooltipContent({
  active,
  payload,
  label,
  formatValue,
}: {
  active?: boolean
  payload?: { color?: string; name?: string; value?: number }[]
  label?: string
  formatValue: (v: number) => string
}) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-md border border-border bg-primary px-3 py-2 text-xs shadow-lg">
      <p className="mb-1 text-mutedForeground">{label}</p>
      {payload.map((p) => (
        <p key={p.name} className="flex items-center gap-1.5">
          <span className="inline-block h-0.5 w-3" style={{ background: p.color }} />
          <span className="font-semibold text-foreground tabular-nums">
            {p.value != null ? formatValue(p.value) : '—'}
          </span>
          <span className="text-mutedForeground">{p.name}</span>
        </p>
      ))}
    </div>
  )
}

export default function MetricsChart({
  title,
  series,
  colors,
  loading = false,
  emptyNote,
  formatValue = (v) => v.toLocaleString(),
}: MetricsChartProps) {
  const rows = mergeRows(series)
  const hasData = series.some((s) => s.points.length > 0)

  return (
    <div className="viz rounded-lg border border-border bg-background/40 p-3">
      <p className="mb-2 text-xs font-medium text-mutedForeground">{title}</p>
      {!hasData ? (
        <p className="flex h-40 items-center justify-center text-xs text-mutedForeground">{emptyNote}</p>
      ) : (
        <div style={{ opacity: loading ? 0.5 : 1 }} className="transition-opacity">
          <ResponsiveContainer width="100%" height={160}>
            <LineChart data={rows} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="var(--viz-gridline)" strokeDasharray="0" vertical={false} />
              <XAxis
                dataKey="t"
                tick={{ fill: 'var(--viz-text-muted)', fontSize: 10 }}
                axisLine={{ stroke: 'var(--viz-gridline)' }}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: 'var(--viz-text-muted)', fontSize: 10 }}
                axisLine={false}
                tickLine={false}
                width={44}
                tickFormatter={formatValue}
              />
              <Tooltip content={<TooltipContent formatValue={formatValue} />} />
              {series.length > 1 && (
                <Legend
                  wrapperStyle={{ fontSize: 11 }}
                  formatter={(value) => <span className="text-mutedForeground">{value}</span>}
                />
              )}
              {series.map((s, i) => (
                <Line
                  key={s.label}
                  dataKey={s.label}
                  name={s.label}
                  stroke={colors[i % colors.length]}
                  strokeWidth={2}
                  dot={{ r: 4, fill: colors[i % colors.length] }}
                  activeDot={{ r: 5 }}
                  connectNulls={false}
                  type="monotone"
                  isAnimationActive={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
