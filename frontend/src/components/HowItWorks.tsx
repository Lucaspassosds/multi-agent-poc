import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowsClockwise,
  CaretDown,
  ChartLineUp,
  Lightning,
  MagnifyingGlass,
  PencilSimpleLine,
  Quotes,
  ShieldCheck,
  Tag,
  type Icon,
} from '@phosphor-icons/react'

const STORAGE_KEY = 'triage-how-it-works-collapsed'

interface Step {
  icon: Icon
  title: string
  badge?: string
  description: string
}

const STEPS: Step[] = [
  {
    icon: Tag,
    title: 'Classify',
    description: "Figures out what kind of issue this is: category, priority, and how the customer's feeling.",
  },
  {
    icon: MagnifyingGlass,
    title: 'Retrieve',
    badge: 'parallel',
    description: "Searches Stripe's documentation and past tickets at once, from a few different angles.",
  },
  {
    icon: PencilSimpleLine,
    title: 'Resolve',
    description: 'Drafts a reply grounded in what it found — no invented policy, every claim traceable.',
  },
  {
    icon: ShieldCheck,
    title: 'Critique',
    description: 'A second pass checks the draft for unsupported claims or gaps, and revises if needed.',
  },
]

interface Capability {
  icon: Icon
  label: string
  to?: string
}

const CAPABILITIES: Capability[] = [
  { icon: Quotes, label: 'Grounded in Stripe docs (RAG + citations)' },
  { icon: Lightning, label: 'Parallel retrieval' },
  { icon: ArrowsClockwise, label: 'Self-critiques & revises' },
  { icon: ChartLineUp, label: 'Every run fully traced', to: '/observability' },
]

function readCollapsed(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === '1'
  } catch {
    return false
  }
}

export default function HowItWorks() {
  const [collapsed, setCollapsed] = useState(readCollapsed)

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, collapsed ? '1' : '0')
    } catch {
      // localStorage unavailable (private mode, etc.) — collapse state just won't persist.
    }
  }, [collapsed])

  return (
    <section className="rounded-lg border border-border bg-primary/30">
      <button
        type="button"
        onClick={() => setCollapsed((v) => !v)}
        aria-expanded={!collapsed}
        className="flex w-full items-center justify-between px-4 py-3 text-sm font-medium text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-accent rounded-lg"
      >
        How it works
        <CaretDown
          size={16}
          className={`text-mutedForeground transition-transform duration-200 ${collapsed ? '-rotate-90' : ''}`}
        />
      </button>
      {!collapsed && (
        <div className="space-y-4 px-4 pb-4">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((s) => (
              <div key={s.title} className="rounded-lg border border-border bg-primary p-3">
                <div className="mb-1.5 flex items-center gap-2">
                  <s.icon size={18} weight="regular" className="text-accent shrink-0" />
                  <span className="text-sm font-medium text-foreground">{s.title}</span>
                  {s.badge && (
                    <span className="rounded-full bg-accent/15 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-accent">
                      {s.badge}
                    </span>
                  )}
                </div>
                <p className="text-xs leading-relaxed text-mutedForeground">{s.description}</p>
              </div>
            ))}
          </div>
          <div className="flex flex-wrap gap-2">
            {CAPABILITIES.map((c) => {
              const inner = (
                <>
                  <c.icon size={14} weight="regular" />
                  {c.label}
                </>
              )
              return c.to ? (
                <Link
                  key={c.label}
                  to={c.to}
                  className="inline-flex items-center gap-1.5 rounded-full border border-border px-2.5 py-1 text-xs text-mutedForeground transition-colors hover:border-accent/50 hover:text-accent"
                >
                  {inner}
                </Link>
              ) : (
                <span
                  key={c.label}
                  className="inline-flex items-center gap-1.5 rounded-full border border-border px-2.5 py-1 text-xs text-mutedForeground"
                >
                  {inner}
                </span>
              )
            })}
          </div>
        </div>
      )}
    </section>
  )
}
