import { ShieldWarning, Check, X } from '@phosphor-icons/react'
import { useState } from 'react'
import { approveEscalation } from '../lib/api'
import type { EscalationHandle, EscalationProposal } from '../lib/types'
import Card from './Card'

export default function EscalationGate({
  proposal,
  ticketId,
  ticketText,
  onClose,
}: {
  proposal: EscalationProposal | null
  ticketId: number
  ticketText: string
  onClose: () => void
}) {
  const reason = proposal?.reason ?? 'Manual escalation requested by agent operator.'
  const preview = proposal?.preview ?? `Escalate ticket #${ticketId}: "${ticketText.slice(0, 80)}…"`
  const [busy, setBusy] = useState(false)
  const [handle, setHandle] = useState<EscalationHandle | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function approve() {
    setBusy(true)
    setError(null)
    try {
      setHandle(await approveEscalation(ticketId, reason))
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  if (handle) {
    return (
      <Card tone="muted" className="border-accent/40">
        <p className="flex items-center gap-2 text-sm font-medium text-accent">
          <Check size={16} weight="bold" />
          Escalated · handle {handle.handle}
        </p>
        <p className="mt-1 text-xs text-mutedForeground">
          Ticket status is now <span className="font-medium text-foreground">{handle.status}</span>.
          Committed {new Date(handle.committed_at).toLocaleString()}.
        </p>
      </Card>
    )
  }

  return (
    <Card tone="breach">
      <p className="flex items-center gap-2 text-sm font-medium text-foreground">
        <ShieldWarning size={16} weight="regular" className="text-warning" />
        Human approval required to escalate
      </p>
      <p className="mt-2 text-xs text-mutedForeground">
        <span className="font-medium text-foreground">Reason:</span> {reason}
      </p>
      <p className="mt-1 text-xs text-mutedForeground">
        <span className="font-medium text-foreground">Write preview:</span> {preview}
      </p>
      <p className="mt-2 text-[11px] text-mutedForeground">
        This is a destructive tool (writes ticket status + creates a handle). Nothing is written until you approve.
      </p>
      {error && <p className="mt-2 text-xs text-destructive">{error}</p>}
      <div className="mt-3 flex gap-2">
        <button
          type="button"
          onClick={approve}
          disabled={busy}
          className="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-background disabled:opacity-50"
        >
          <Check size={14} weight="bold" />
          {busy ? 'Committing…' : 'Approve & commit'}
        </button>
        <button
          type="button"
          onClick={onClose}
          disabled={busy}
          className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs text-foreground hover:border-accent/50 disabled:opacity-50"
        >
          <X size={14} weight="bold" />
          Cancel
        </button>
      </div>
    </Card>
  )
}
