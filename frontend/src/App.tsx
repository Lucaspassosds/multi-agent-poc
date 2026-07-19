import { Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import TriagePage from './pages/TriagePage'
import ObservabilityPage from './pages/ObservabilityPage'
import TraceDetailPage from './pages/TraceDetailPage'
import EvalsPage from './pages/EvalsPage'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<TriagePage />} />
        <Route path="/observability" element={<ObservabilityPage />} />
        <Route path="/observability/:traceId" element={<TraceDetailPage />} />
        <Route path="/evals" element={<EvalsPage />} />
      </Route>
    </Routes>
  )
}
