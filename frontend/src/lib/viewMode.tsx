import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

export type ViewMode = 'client' | 'under-the-hood'

// Persisted like HowItWorks' collapse flag — a single stable localStorage key, best-effort.
const STORAGE_KEY = 'triage-view-mode'

function readMode(): ViewMode {
  try {
    return localStorage.getItem(STORAGE_KEY) === 'under-the-hood' ? 'under-the-hood' : 'client'
  } catch {
    return 'client'
  }
}

interface ViewModeContextValue {
  mode: ViewMode
  setMode: (m: ViewMode) => void
  underTheHood: boolean
}

const ViewModeContext = createContext<ViewModeContextValue | null>(null)

export function ViewModeProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<ViewMode>(readMode)

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, mode)
    } catch {
      // localStorage unavailable (private mode) — choice just won't persist across reloads.
    }
  }, [mode])

  return (
    <ViewModeContext.Provider value={{ mode, setMode, underTheHood: mode === 'under-the-hood' }}>
      {children}
    </ViewModeContext.Provider>
  )
}

export function useViewMode(): ViewModeContextValue {
  const ctx = useContext(ViewModeContext)
  if (!ctx) throw new Error('useViewMode must be used within a ViewModeProvider')
  return ctx
}
