import { useState } from 'react'
import type { CitedChunk } from '../lib/types'

export default function CitationBadge({ citation }: { citation: CitedChunk }) {
  const [open, setOpen] = useState(false)
  return (
    <span className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="inline-flex items-center rounded border border-accent/40 bg-accent/10 px-1.5 py-0.5 text-xs text-accent hover:bg-accent/20 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
      >
        [{citation.title}]
      </button>
      {open && (
        <div className="absolute z-10 mt-1 w-72 rounded-lg border border-border bg-primary p-3 text-xs shadow-lg">
          <p className="font-medium text-foreground mb-1">{citation.title}</p>
          <p className="text-mutedForeground mb-2 uppercase tracking-wide text-[10px]">{citation.source_type}</p>
          <p className="text-foreground/90 leading-relaxed">{citation.snippet}</p>
        </div>
      )}
    </span>
  )
}
