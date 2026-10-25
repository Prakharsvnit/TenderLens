import { Code, LogOut, ScanSearch } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { config } from '../config'

export const REPO_URL = 'https://github.com/Prakharsvnit/TenderLens'

function Logo({ to }: { to: string }) {
  return (
    <Link to={to} className="flex items-center gap-2 font-semibold text-slate-900">
      <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-600 text-white">
        <ScanSearch className="h-4 w-4" />
      </span>
      TenderLens
    </Link>
  )
}

function Footer() {
  const region = config().region ?? 'local'
  return (
    <footer className="border-t border-slate-200">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-2 px-4 py-4 text-xs text-slate-500 sm:px-6">
        <span>TenderLens · agentic RFP compliance on AWS</span>
        <span className="font-mono">
          v{__BUILD__.version} · {__BUILD__.sha} · {region}
        </span>
      </div>
    </footer>
  )
}

function Frame({ header, children }: { header: ReactNode; children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-7xl items-center justify-between gap-3 px-4 sm:px-6">{header}</div>
      </header>
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6">{children}</main>
      <Footer />
    </div>
  )
}

/** Pages anyone can open: the landing, the public demo and not-found. */
export function PublicLayout({ children }: { children: ReactNode }) {
  return (
    <Frame
      header={
        <>
          <Logo to="/" />
          <nav className="flex items-center gap-1 text-sm sm:gap-3">
            <Link to="/demo" className="whitespace-nowrap rounded-md px-2 py-1.5 text-slate-600 hover:text-slate-900">
              Demo runs
            </Link>
            <a href={REPO_URL} target="_blank" rel="noreferrer" aria-label="Source code"
              className="inline-flex items-center gap-1 rounded-md px-2 py-1.5 text-slate-600 hover:text-slate-900">
              <Code className="h-4 w-4" /> <span className="hidden sm:inline">Code</span>
            </a>
            <Link to="/app" className="whitespace-nowrap rounded-lg bg-brand-600 px-3 py-1.5 font-medium text-white hover:bg-brand-700">
              Open app
            </Link>
          </nav>
        </>
      }
    >
      {children}
    </Frame>
  )
}

/** The signed-in app. */
export function AppLayout({ email, onSignOut, children }: { email: string; onSignOut: () => void; children: ReactNode }) {
  return (
    <Frame
      header={
        <>
          <Logo to="/app" />
          <div className="flex items-center gap-3 text-sm text-slate-600">
            <Link to="/" className="hidden text-slate-500 hover:text-slate-900 sm:inline">About</Link>
            <span className="hidden sm:inline">{email}</span>
            <button onClick={onSignOut} title="Sign out" aria-label="Sign out"
              className="rounded-md p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700">
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </>
      }
    >
      {children}
    </Frame>
  )
}
