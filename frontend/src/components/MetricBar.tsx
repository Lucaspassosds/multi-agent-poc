function bandColor(value: number): string {
  if (value >= 0.8) return 'var(--status-good)'
  if (value >= 0.5) return '#c98500' // warning step, same family as the categorical "yellow" slot
  return 'var(--status-critical)'
}

export default function MetricBar({ label, value }: { label: string; value: number }) {
  const pct = Math.max(0, Math.min(1, value)) * 100
  return (
    <div className="viz">
      <div className="flex items-baseline justify-between mb-1">
        <span className="text-sm text-mutedForeground">{label}</span>
        <span className="text-sm font-semibold text-foreground tabular-nums">{value.toFixed(2)}</span>
      </div>
      <div className="h-2 rounded-full" style={{ background: 'var(--viz-gridline)' }}>
        <div
          className="h-full rounded-full transition-[width] duration-300"
          style={{ width: `${pct}%`, background: bandColor(value) }}
        />
      </div>
    </div>
  )
}
