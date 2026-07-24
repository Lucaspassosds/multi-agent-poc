import type { FailureTaxonomyBucket } from '../lib/types'

// Human labels for the spec-07 taxonomy keys; unknown keys fall back to the raw label.
const LABELS: Record<string, string> = {
  hallucinated_policy: 'Hallucinated policy',
  missed_citation: 'Missed citation',
  wrong_category: 'Wrong category',
  over_escalation: 'Over-escalation',
  under_escalation: 'Under-escalation',
}

export default function FailureTaxonomyBars({ buckets }: { buckets: FailureTaxonomyBucket[] }) {
  if (buckets.length === 0) {
    return <p className="text-sm text-mutedForeground">No failures recorded in this run.</p>
  }
  const max = Math.max(...buckets.map((b) => b.count), 1)
  return (
    <div className="space-y-2">
      {buckets.map((b) => (
        <div key={b.label} className="viz">
          <div className="mb-1 flex items-baseline justify-between">
            <span className="text-sm text-mutedForeground">{LABELS[b.label] ?? b.label}</span>
            <span className="text-sm font-semibold tabular-nums text-foreground">{b.count}</span>
          </div>
          <div className="h-2 rounded-full" style={{ background: 'var(--viz-gridline)' }}>
            <div
              className="h-full rounded-full"
              style={{ width: `${(b.count / max) * 100}%`, background: 'var(--status-critical)' }}
            />
          </div>
        </div>
      ))}
    </div>
  )
}
