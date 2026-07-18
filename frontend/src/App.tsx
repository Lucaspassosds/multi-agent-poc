import { useEffect, useState } from 'react'

const API = 'http://localhost:8000'

// Phase 0 placeholder: proves the full loop (browser → FastAPI → db + embeddings).
// The real, designed UI arrives in Phase 8 (built with the ui-ux-pro-max skill).
export default function App() {
  const [health, setHealth] = useState<unknown>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch(`${API}/health`)
      .then((r) => r.json())
      .then(setHealth)
      .catch((e) => setError(String(e)))
  }, [])

  return (
    <main style={{ fontFamily: 'system-ui, sans-serif', padding: 32, maxWidth: 640, margin: '0 auto' }}>
      <h1>Support Triage POC</h1>
      <p>Phase 0 — infrastructure scaffold. Live backend health:</p>
      {error && <pre style={{ color: 'crimson' }}>{error}</pre>}
      <pre style={{ background: '#f4f4f5', padding: 16, borderRadius: 8 }}>
        {health ? JSON.stringify(health, null, 2) : 'loading…'}
      </pre>
      <p style={{ color: '#71717a', fontSize: 14 }}>
        The real UI arrives in Phase 8, designed with the <code>ui-ux-pro-max</code> skill.
      </p>
    </main>
  )
}
