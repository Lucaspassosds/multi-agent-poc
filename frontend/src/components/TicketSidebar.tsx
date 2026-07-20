import { ClockCounterClockwise, Plus } from '@phosphor-icons/react'
import type { TicketListItem } from '../lib/types'

function timeAgo(iso: string): string {
  const secs = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000)
  if (secs < 60) return 'just now'
  const mins = Math.floor(secs / 60)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

export default function TicketSidebar({
  tickets,
  selectedId,
  disabled,
  onSelect,
  onNew,
}: {
  tickets: TicketListItem[]
  selectedId: number | null
  disabled: boolean
  onSelect: (id: number) => void
  onNew: () => void
}) {
  return (
    <aside className="w-64 shrink-0 space-y-3">
      <button
        type="button"
        onClick={onNew}
        disabled={disabled}
        className="flex w-full items-center gap-2 rounded-md border border-border px-3 py-2 text-sm font-medium text-foreground hover:border-accent/50 disabled:cursor-not-allowed disabled:opacity-40"
      >
        <Plus size={16} weight="bold" />
        New ticket
      </button>

      <div className="flex items-center gap-2 px-1 text-xs font-semibold uppercase tracking-wide text-mutedForeground">
        <ClockCounterClockwise size={14} weight="regular" />
        History
      </div>

      {tickets.length === 0 ? (
        <p className="px-1 text-xs text-mutedForeground">No past tickets yet.</p>
      ) : (
        <ul className="space-y-1">
          {tickets.map((t) => {
            const isSelected = t.id === selectedId
            return (
              <li key={t.id}>
                <button
                  type="button"
                  onClick={() => onSelect(t.id)}
                  disabled={disabled}
                  aria-pressed={isSelected}
                  className={`w-full rounded-md border px-3 py-2 text-left text-xs transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
                    isSelected
                      ? 'border-accent/60 bg-primary'
                      : 'border-transparent hover:border-border hover:bg-primary/40'
                  }`}
                >
                  <span className="line-clamp-2 text-foreground/90">{t.ticket_text}</span>
                  <span className="mt-1 flex items-center justify-between text-[10px] text-mutedForeground">
                    <span className="truncate">{t.category ?? 'uncategorized'}</span>
                    <span className="tabular-nums">{timeAgo(t.created_at)}</span>
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </aside>
  )
}
