import { Warning } from '@phosphor-icons/react'
import Card from './Card'

export default function KpiCard({
  label,
  value,
  sub,
  breach = false,
}: {
  label: string
  value: string
  sub?: string
  breach?: boolean
}) {
  return (
    <Card tone={breach ? 'breach' : 'default'}>
      <p className="mb-1 flex items-center gap-1 text-xs text-mutedForeground">
        {label}
        {breach && <Warning size={12} weight="fill" className="text-destructive" />}
      </p>
      <p className={`text-2xl font-semibold ${breach ? 'text-destructive' : 'text-foreground'}`}>{value}</p>
      {sub && <p className="mt-0.5 text-[11px] text-mutedForeground tabular-nums">{sub}</p>}
    </Card>
  )
}
