import type { ReactNode } from 'react'

type Tone = 'neutral' | 'accent' | 'success' | 'warning' | 'destructive'

const TONE: Record<Tone, string> = {
  neutral: 'border-border bg-primary text-foreground',
  accent: 'border-accent/40 bg-accent/10 text-accent',
  success: 'border-transparent bg-accent/15 text-accent',
  warning: 'border-transparent text-warning',
  destructive: 'border-destructive/40 bg-destructive/10 text-destructive',
}

export default function Badge({
  children,
  tone = 'neutral',
  dot,
  className = '',
}: {
  children: ReactNode
  tone?: Tone
  dot?: string
  className?: string
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs ${TONE[tone]} ${className}`}
    >
      {dot && <span className="inline-block h-2 w-2 rounded-full" style={{ background: dot }} />}
      {children}
    </span>
  )
}
