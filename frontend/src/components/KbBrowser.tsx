import { BookOpen } from '@phosphor-icons/react'
import { useEffect, useState } from 'react'
import { getKbDoc, getKbIndex } from '../lib/api'
import type { KbDocResource, KbIndexEntry } from '../lib/types'
import { useViewMode } from '../lib/viewMode'

export default function KbBrowser() {
  const { underTheHood } = useViewMode()
  const [index, setIndex] = useState<KbIndexEntry[] | null>(null)
  const [selected, setSelected] = useState<number | null>(null)
  const [doc, setDoc] = useState<KbDocResource | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [docError, setDocError] = useState<string | null>(null)

  useEffect(() => {
    getKbIndex()
      .then((r) => setIndex(r.resources))
      .catch((e) => setError(String(e)))
  }, [])

  async function open(id: number) {
    setSelected(id)
    setDoc(null)
    setDocError(null)
    try {
      setDoc(await getKbDoc(id))
    } catch (e) {
      setDocError(String(e))
    }
  }

  if (error) return null // MCP resources optional; hide the panel if the passthrough is down.

  return (
    <section className="rounded-lg border border-border bg-primary/30 p-4">
      <h2 className="mb-3 flex items-center gap-2 text-sm font-medium text-foreground">
        <BookOpen size={16} weight="regular" className="text-accent" />
        Knowledge base
        <span className="text-[10px] font-normal uppercase tracking-wide text-mutedForeground">via MCP kb://index</span>
      </h2>
      {!index && <p className="text-sm text-mutedForeground">Loading catalog…</p>}
      {index && (
        <div className="grid gap-4 sm:grid-cols-[16rem_1fr]">
          <ul className="max-h-72 space-y-1 overflow-y-auto">
            {index.map((r) => (
              <li key={r.id}>
                <button
                  type="button"
                  onClick={() => open(r.id)}
                  aria-pressed={selected === r.id}
                  className={`w-full rounded-md border px-3 py-2 text-left text-xs transition-colors ${
                    selected === r.id ? 'border-accent/60 bg-primary' : 'border-transparent hover:border-border hover:bg-primary/40'
                  }`}
                >
                  <span className="block text-foreground/90">{r.title}</span>
                  <span className="mt-0.5 block text-[10px] uppercase tracking-wide text-mutedForeground">
                    {r.source_type}
                    {underTheHood && <> · kb://doc/{r.id}</>}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          <div className="rounded-md border border-border bg-background p-3">
            {docError && <p className="text-xs text-destructive">{docError}</p>}
            {!doc && !docError && <p className="text-xs text-mutedForeground">Select a document to read it.</p>}
            {doc && (
              <>
                <p className="text-sm font-medium text-foreground">{doc.title}</p>
                {underTheHood && (
                  <p className="mb-2 text-[10px] uppercase tracking-wide text-mutedForeground">{doc.uri}</p>
                )}
                <pre className="mt-2 max-h-72 overflow-y-auto whitespace-pre-wrap text-xs leading-relaxed text-foreground/90">
                  {doc.markdown}
                </pre>
              </>
            )}
          </div>
        </div>
      )}
    </section>
  )
}
