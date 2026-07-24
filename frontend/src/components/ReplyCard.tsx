import { CheckCircle, PaperPlaneTilt, PencilSimple, ShieldWarning } from '@phosphor-icons/react'
import { useState, type ReactNode } from 'react'
import type { CitedChunk, TriageResult } from '../lib/types'
import EscalationGate from './EscalationGate'
import SkillBadge from './SkillBadge'

export default function ReplyCard({
  result,
  underTheHood,
  renderReply,
}: {
  result: TriageResult
  underTheHood: boolean
  renderReply: (text: string, cited: CitedChunk[]) => ReactNode
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(result.final_reply)
  const [sent, setSent] = useState(false)
  const [gateOpen, setGateOpen] = useState(false)
  // The gate is only offered when the pipeline actually proposed an escalation AND the proposal
  // carries the `tickets` row id the write needs. A trace id is NOT a ticket id — approving with
  // one would either 422 or, worse, flip an unrelated ticket to 'escalated'. When the field is
  // absent (today's triage result never carries a proposal) the button hides, same graceful
  // degradation every other optional-field consumer uses.
  const escalationTicketId = result.escalation?.ticket_id
  const canEscalate =
    result.escalation?.proposed === true && typeof escalationTicketId === 'number'

  return (
    <section className="space-y-3">
      {result.skill_invocation && (
        <div className="flex flex-wrap gap-2">
          <SkillBadge skill={result.skill_invocation} />
        </div>
      )}

      <div className="rounded-lg border border-border bg-primary p-4">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-sm font-medium text-foreground">
            <CheckCircle size={16} weight="regular" className="text-accent" />
            {sent ? 'Reply sent' : 'Suggested reply'}
          </h2>
          {underTheHood && (
            <span className="text-xs text-mutedForeground tabular-nums">
              {result.total_seconds}s · ${result.cost_usd.toFixed(6)} ·{' '}
              {result.usage.input_tokens + result.usage.output_tokens} tok ·{' '}
              {result.parallelism.speedup ?? '—'}× parallel
            </span>
          )}
        </div>

        {editing ? (
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={6}
            className="w-full rounded-lg border border-border bg-background p-3 text-sm text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
          />
        ) : (
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground/90">
            {renderReply(draft, result.evidence.flatMap((e) => e.cited))}
          </p>
        )}

        {result.revised && !editing && (
          <p className="mt-2 text-xs text-mutedForeground">Revised once after critic feedback.</p>
        )}

        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setSent(true)}
            disabled={sent}
            className="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-background disabled:opacity-50"
          >
            <PaperPlaneTilt size={14} weight="bold" />
            {sent ? 'Sent' : 'Send'}
          </button>
          <button
            type="button"
            onClick={() => setEditing((v) => !v)}
            className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs text-foreground hover:border-accent/50"
          >
            <PencilSimple size={14} weight="regular" />
            {editing ? 'Done editing' : 'Edit'}
          </button>
          {canEscalate && (
            <button
              type="button"
              onClick={() => setGateOpen(true)}
              className="inline-flex items-center gap-1.5 rounded-md border border-warning/60 px-3 py-1.5 text-xs text-warning"
            >
              <ShieldWarning size={14} weight="regular" />
              Escalate (recommended)
            </button>
          )}
        </div>
      </div>

      {gateOpen && canEscalate && escalationTicketId != null && (
        <EscalationGate
          proposal={result.escalation ?? null}
          ticketId={escalationTicketId}
          ticketText={result.ticket}
          onClose={() => setGateOpen(false)}
        />
      )}
    </section>
  )
}
