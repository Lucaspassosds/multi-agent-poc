// Anonymous per-visitor history key. No auth — just a stable random id in localStorage so a
// browser sees only its own past tickets (server filters by it). Cleared with site data by design.
const KEY = 'triage_session_id'

export function getOrCreateSessionId(): string {
  let id = localStorage.getItem(KEY)
  if (!id) {
    id = crypto.randomUUID()
    localStorage.setItem(KEY, id)
  }
  return id
}
