import type { Classification } from '../lib/types'

const PRIORITY_COLOR: Record<Classification['priority'], string> = {
  low: 'var(--status-good)',
  medium: '#c98500',
  high: 'var(--status-critical)',
}

const SENTIMENT_COLOR: Record<Classification['sentiment'], string> = {
  happy: 'var(--status-good)',
  neutral: 'var(--viz-text-muted)',
  angry: 'var(--status-critical)',
}

function Chip({ label, value, dot }: { label: string; value: string; dot?: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-primary px-3 py-1 text-xs text-foreground">
      {dot && <span className="w-2 h-2 rounded-full inline-block" style={{ background: dot }} />}
      <span className="text-mutedForeground">{label}</span>
      <span className="font-medium">{value}</span>
    </span>
  )
}

export default function ClassificationChips({ classification }: { classification: Classification }) {
  return (
    <div className="viz flex flex-wrap gap-2">
      <Chip label="category" value={classification.category} />
      <Chip label="priority" value={classification.priority} dot={PRIORITY_COLOR[classification.priority]} />
      <Chip label="sentiment" value={classification.sentiment} dot={SENTIMENT_COLOR[classification.sentiment]} />
    </div>
  )
}
