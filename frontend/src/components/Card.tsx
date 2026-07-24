import type { ReactNode } from 'react'

type Tone = 'default' | 'muted' | 'breach'

const TONE: Record<Tone, string> = {
  default: 'border-border bg-surface',
  muted: 'border-border bg-surface/30',
  breach: 'border-destructive/50 bg-destructive/5',
}

export default function Card({
  children,
  tone = 'default',
  className = '',
}: {
  children: ReactNode
  tone?: Tone
  className?: string
}) {
  return <div className={`rounded-lg border p-4 ${TONE[tone]} ${className}`}>{children}</div>
}
