import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <div className="mx-auto max-w-md py-20 text-center">
      <p className="text-sm font-semibold text-brand-600">404</p>
      <h1 className="mt-2 text-2xl font-semibold text-slate-900">Page not found</h1>
      <p className="mt-2 text-sm text-slate-500">The link may be old, or the run is not shared.</p>
      <div className="mt-6 flex justify-center gap-3 text-sm">
        <Link to="/" className="rounded-lg bg-brand-600 px-3 py-2 font-medium text-white hover:bg-brand-700">Home</Link>
        <Link to="/demo" className="rounded-lg px-3 py-2 font-medium text-slate-700 ring-1 ring-slate-300 hover:bg-slate-50">Demo runs</Link>
      </div>
    </div>
  )
}
