import { StrictMode, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Link, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { LogOut, ScanSearch } from 'lucide-react'
import { currentEmail, signOut } from './auth'
import { loadConfig } from './config'
import './index.css'
import { DemoPage } from './pages/Demo'
import { LoginPage } from './pages/Login'
import { RunPage } from './pages/Run'
import { RunsPage } from './pages/Runs'
import { Spinner } from './components/ui'

function Shell({ email, onSignOut }: { email: string; onSignOut: () => void }) {
  const navigate = useNavigate()
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 sm:px-6">
          <Link to="/" className="flex items-center gap-2 font-semibold text-slate-900">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-600 text-white">
              <ScanSearch className="h-4 w-4" />
            </span>
            TenderLens
            <span className="hidden text-sm font-normal text-slate-400 sm:inline">RFP compliance agents</span>
          </Link>
          <div className="flex items-center gap-3 text-sm text-slate-600">
            <span className="hidden sm:inline">{email}</span>
            <button
              onClick={() => {
                onSignOut()
                navigate('/')
              }}
              className="rounded-md p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              title="Sign out"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
        <Routes>
          <Route path="/" element={<RunsPage />} />
          <Route path="/runs/:runId" element={<RunPage />} />
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </main>
    </div>
  )
}

/** The public demo: no sign-in, read-only views of shared runs. */
function DemoShell() {
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 sm:px-6">
          <Link to="/demo" className="flex items-center gap-2 font-semibold text-slate-900">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-600 text-white">
              <ScanSearch className="h-4 w-4" />
            </span>
            TenderLens
            <span className="hidden text-sm font-normal text-slate-400 sm:inline">RFP compliance agents</span>
          </Link>
          <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600">
            Public demo · read-only
          </span>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
        <Routes>
          <Route path="/demo" element={<DemoPage />} />
          <Route path="/demo/runs/:runId" element={<RunPage publicMode />} />
          <Route path="*" element={<Navigate to="/demo" />} />
        </Routes>
      </main>
    </div>
  )
}

function App() {
  const location = useLocation()
  const [ready, setReady] = useState(false)
  const [email, setEmail] = useState<string | null>(null)

  useEffect(() => {
    loadConfig()
      .then(() => currentEmail())
      .then((e) => setEmail(e))
      .finally(() => setReady(true))
  }, [])

  if (!ready)
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner label="Loading" />
      </div>
    )
  if (location.pathname.startsWith('/demo')) return <DemoShell />
  if (!email) return <LoginPage onSignedIn={(e) => setEmail(e)} />
  return (
    <Shell
      email={email}
      onSignOut={() => {
        signOut()
        setEmail(null)
      }}
    />
  )
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
)
