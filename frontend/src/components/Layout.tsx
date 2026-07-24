import { NavLink, Outlet } from 'react-router-dom'
import ViewModeToggle from './ViewModeToggle'

const links = [
  { to: '/', label: 'Triage', end: true },
  { to: '/observability', label: 'Run Inspector' },
  { to: '/evals', label: 'Quality Dashboard' },
]

export default function Layout() {
  return (
    <div className="min-h-dvh flex flex-col">
      <header className="border-b border-border">
        <nav className="max-w-6xl mx-auto flex items-center gap-1 px-4 py-3">
          <span className="mr-4 flex items-baseline gap-2 text-sm font-semibold tracking-wide text-foreground">
            Stripe Payments Support Triage
            <span className="text-[10px] font-normal uppercase tracking-wider text-mutedForeground">
              agent POC
            </span>
          </span>
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.end}
              className={({ isActive }) =>
                `rounded-md px-3 py-1.5 text-sm transition-colors ${
                  isActive
                    ? 'bg-accent/15 text-accent'
                    : 'text-mutedForeground hover:text-foreground hover:bg-primary'
                }`
              }
            >
              {l.label}
            </NavLink>
          ))}
          <div className="ml-auto">
            <ViewModeToggle />
          </div>
        </nav>
      </header>
      <main className="flex-1 max-w-6xl w-full mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
