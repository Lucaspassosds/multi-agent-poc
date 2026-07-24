import { ArrowSquareOut, X } from '@phosphor-icons/react'
import { useState } from 'react'
import { getKbDoc } from '../lib/api'
import type { CitedChunk, KbDocResource } from '../lib/types'
import { useViewMode } from '../lib/viewMode'

export default function CitationBadge({ citation }: { citation: CitedChunk }) {
  const { underTheHood } = useViewMode()
  const [open, setOpen] = useState(false)
  const [doc, setDoc] = useState<KbDocResource | null>(null)
  const [loadingDoc, setLoadingDoc] = useState(false)
  const [docError, setDocError] = useState<string | null>(null)

  async function openDoc() {
    if (citation.doc_id == null) return
    setLoadingDoc(true)
    setDocError(null)
    try {
      setDoc(await getKbDoc(citation.doc_id))
    } catch (e) {
      setDocError(String(e))
    } finally {
      setLoadingDoc(false)
    }
  }

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
          <p className="mb-1 font-medium text-foreground">{citation.title}</p>
          <p className="mb-2 text-[10px] uppercase tracking-wide text-mutedForeground">{citation.source_type}</p>
          <p className="leading-relaxed text-foreground/90">{citation.snippet}</p>

          {underTheHood && (
            <p className="mt-2 border-t border-border pt-2 text-[10px] text-mutedForeground tabular-nums">
              chunk #{citation.chunk_id}
              {citation.doc_id != null && <> · kb://doc/{citation.doc_id}</>}
            </p>
          )}

          {citation.doc_id != null && (
            <button
              type="button"
              onClick={openDoc}
              disabled={loadingDoc}
              className="mt-2 inline-flex items-center gap-1 text-accent hover:underline disabled:opacity-50"
            >
              <ArrowSquareOut size={12} weight="regular" />
              {loadingDoc ? 'Opening…' : underTheHood ? 'Open source span (kb://doc)' : 'Open source'}
            </button>
          )}
          {docError && <p className="mt-1 text-destructive">{docError}</p>}
        </div>
      )}

      {doc && (
        <div
          className="fixed inset-0 z-30 flex items-start justify-center overflow-y-auto bg-black/50 p-6"
          role="dialog"
          aria-modal="true"
          onClick={() => setDoc(null)}
        >
          <div
            className="mt-8 w-full max-w-2xl rounded-lg border border-border bg-primary p-5 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-3 flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-foreground">{doc.title}</p>
                <p className="text-[10px] uppercase tracking-wide text-mutedForeground">
                  {doc.source_type} · {doc.uri}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setDoc(null)}
                aria-label="Close"
                className="rounded p-1 text-mutedForeground hover:text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
              >
                <X size={16} weight="bold" />
              </button>
            </div>
            <pre className="max-h-[60vh] overflow-y-auto whitespace-pre-wrap text-xs leading-relaxed text-foreground/90">
              {doc.markdown}
            </pre>
          </div>
        </div>
      )}
    </span>
  )
}
