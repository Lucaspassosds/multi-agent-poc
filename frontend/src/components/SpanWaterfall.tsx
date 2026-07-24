import { useState } from 'react'
import { SERIES_LABEL, SERIES_ORDER, type WaterfallRow } from '../lib/waterfall'

const SERIES_VAR: Record<string, string> = {
  agent: 'var(--series-1)',
  retriever: 'var(--series-2)',
  classifier: 'var(--series-3)',
  planner: 'var(--series-4)',
  resolver: 'var(--series-5)',
  critic: 'var(--series-6)',
  tool: 'var(--series-7)',
  llm_call: 'var(--series-8)',
}

function Legend({ seriesInUse }: { seriesInUse: Set<string> }) {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 mb-3 text-xs text-[var(--viz-text-secondary)]">
      {SERIES_ORDER.filter((k) => seriesInUse.has(k)).map((k) => (
        <span key={k} className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-sm inline-block" style={{ background: SERIES_VAR[k] }} />
          {SERIES_LABEL[k]}
        </span>
      ))}
    </div>
  )
}

export default function SpanWaterfall({ rows, dense = false }: { rows: WaterfallRow[]; dense?: boolean }) {
  const [selected, setSelected] = useState<string | null>(null)

  if (rows.length === 0) {
    return <p className="text-sm text-[var(--viz-text-muted)]">No spans yet.</p>
  }

  const totalSeconds = Math.max(...rows.map((r) => r.startOffset + (r.duration ?? 0.15)), 0.5)
  const seriesInUse = new Set(rows.map((r) => r.seriesKey))
  const selectedRow = rows.find((r) => r.id === selected) ?? null

  return (
    <div className="viz">
      <Legend seriesInUse={seriesInUse} />
      <div className="space-y-1.5">
        {rows.map((row) => {
          const leftPct = (row.startOffset / totalSeconds) * 100
          const widthPct = row.duration != null
            ? Math.max((row.duration / totalSeconds) * 100, 0.6)
            : 3
          const isPending = row.duration == null
          const isSelected = selected === row.id
          return (
            <div key={row.id} className="flex items-center gap-3">
              <span
                className="w-28 shrink-0 text-xs text-[var(--viz-text-secondary)] truncate"
                style={{ paddingLeft: row.depth * 16 }}
                title={row.label}
              >
                {row.label}
              </span>
              <button
                type="button"
                onClick={() => setSelected(isSelected ? null : row.id)}
                aria-pressed={isSelected}
                aria-label={`${row.label}: ${row.duration != null ? `${row.duration.toFixed(2)}s` : 'running'}`}
                className="relative flex-1 h-[22px] rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                style={{ background: 'var(--viz-gridline)' }}
              >
                <span
                  className={`absolute top-0 h-full rounded-[4px] transition-[width,left] duration-200 ${
                    isPending ? 'animate-pulse' : ''
                  } ${isSelected ? 'ring-2 ring-offset-1 ring-offset-[var(--viz-surface)] ring-white/60' : ''}`}
                  style={{
                    left: `${leftPct}%`,
                    width: `${widthPct}%`,
                    background: SERIES_VAR[row.seriesKey],
                    borderLeft: row.status === 'error' ? '3px solid var(--status-critical)' : undefined,
                  }}
                />
              </button>
              <span className="flex w-14 shrink-0 items-center justify-end gap-1 text-right text-xs tabular-nums text-[var(--viz-text-muted)]">
                {row.retries != null && row.retries > 0 && (
                  <span
                    className="rounded-sm bg-[var(--status-critical)]/20 px-1 text-[10px]"
                    style={{ color: 'var(--status-critical)' }}
                    title={`${row.retries} retr${row.retries === 1 ? 'y' : 'ies'}`}
                  >
                    ↻{row.retries}
                  </span>
                )}
                {row.duration != null ? `${row.duration.toFixed(2)}s` : '…'}
              </span>
              {dense && (
                <span className="w-16 shrink-0 text-right text-xs tabular-nums text-[var(--viz-text-muted)]">
                  {row.cost != null ? `$${row.cost.toFixed(6)}` : '—'}
                </span>
              )}
            </div>
          )
        })}
      </div>

      {selectedRow && (
        <div className="mt-3 rounded border border-border bg-primary/40 p-3 text-xs text-[var(--viz-text-secondary)]">
          <p className="font-medium text-foreground mb-1">{selectedRow.label}</p>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-0.5 tabular-nums">
            {selectedRow.model && <><dt>model</dt><dd>{selectedRow.model}</dd></>}
            {selectedRow.inputTokens != null && <><dt>input tokens</dt><dd>{selectedRow.inputTokens}</dd></>}
            {selectedRow.outputTokens != null && <><dt>output tokens</dt><dd>{selectedRow.outputTokens}</dd></>}
            {selectedRow.cacheReadTokens != null && <><dt>cache-read tokens</dt><dd>{selectedRow.cacheReadTokens}</dd></>}
            {selectedRow.retries != null && selectedRow.retries > 0 && <><dt>retries</dt><dd>{selectedRow.retries}</dd></>}
          </dl>
          {selectedRow.error && (
            <p className="mt-1 text-destructive">error: {selectedRow.error}</p>
          )}
        </div>
      )}
    </div>
  )
}
