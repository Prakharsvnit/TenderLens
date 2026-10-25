import { StrictMode, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Navigate, Route, Routes, useNavigate, useParams } from 'react-router-dom'
import { currentEmail, signOut } from './auth'
import { loadConfig } from './config'
import './index.css'
import { AppLayout, PublicLayout } from './components/layout'
import { ToastProvider } from './components/toast'
import { Spinner } from './components/ui'
import { DemoPage } from './pages/Demo'
import { LandingPage } from './pages/Landing'
import { LoginPage } from './pages/Login'
import { NotFoundPage } from './pages/NotFound'
import { RunPage } from './pages/Run'
import { RunsPage } from './pages/Runs'

/** The signed-in app under /app: sign-in first, then runs. */
function SignedInApp() {
  const navigate = useNavigate()
  const [email, setEmail] = useState<string | null | undefined>(undefined)

  useEffect(() => {
    currentEmail().then(setEmail)
  }, [])

  if (email === undefined) return <Spinner label="Loading" />
  if (email === null) return <LoginPage onSignedIn={setEmail} />
  return (
    <AppLayout
      email={email}
      onSignOut={() => {
        signOut()
        setEmail(null)
        navigate('/app')
      }}
    >
      <Routes>
        <Route index element={<RunsPage />} />
        <Route path="runs/:runId" element={<RunPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </AppLayout>
  )
}

function OldRunLink() {
  const { runId } = useParams()
  return <Navigate to={`/app/runs/${runId}`} replace />
}

function App() {
  const [ready, setReady] = useState(false)
  useEffect(() => {
    loadConfig().finally(() => setReady(true))
  }, [])
  if (!ready)
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner label="Loading" />
      </div>
    )
  return (
    <Routes>
      <Route path="/" element={<PublicLayout><LandingPage /></PublicLayout>} />
      <Route path="/demo" element={<PublicLayout><DemoPage /></PublicLayout>} />
      <Route path="/demo/runs/:runId" element={<PublicLayout><RunPage publicMode /></PublicLayout>} />
      <Route path="/app/*" element={<SignedInApp />} />
      <Route path="/runs/:runId" element={<OldRunLink />} />
      <Route path="*" element={<PublicLayout><NotFoundPage /></PublicLayout>} />
    </Routes>
  )
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <ToastProvider>
        <App />
      </ToastProvider>
    </BrowserRouter>
  </StrictMode>,
)
