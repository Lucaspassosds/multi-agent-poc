import { Eye, Wrench } from '@phosphor-icons/react'
import { useViewMode, type ViewMode } from '../lib/viewMode'

const OPTIONS: Array<{ value: ViewMode; label: string; icon: typeof Eye }> = [
  { value: 'client', label: 'Client view', icon: Eye },
  { value: 'under-the-hood', label: 'Under the hood', icon: Wrench },
]

export default function ViewModeToggle() {
  const { mode, setMode } = useViewMode()
  return (
    <div
      role="radiogroup"
      aria-label="Presentation density"
      className="inline-flex rounded-full border border-border bg-primary/40 p-0.5 text-xs"
    >
      {OPTIONS.map((o) => {
        const active = mode === o.value
        return (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => setMode(o.value)}
            className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent ${
              active ? 'bg-accent/15 text-accent' : 'text-mutedForeground hover:text-foreground'
            }`}
          >
            <o.icon size={13} weight="regular" />
            {o.label}
          </button>
        )
      })}
    </div>
  )
}
