import { FileUp, Info, Upload } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { Button, Card, DecisionBadge, Empty, RunStatusChip, Spinner, pct, usd } from '../components/ui'
import type { ApiConfig, Run } from '../types'

function NewRun({ live }: { live: ApiConfig | null }) {
  const navigate = useNavigate()
  const input = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const disabled = live !== null && !live.live_runs

  async function start() {
    if (!file) return
    setBusy(true)
    setError('')
    try {
      navigate(`/runs/${await api.startRun(file)}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not start the run')
      setBusy(false)
    }
  }

  return (
    <Card className="p-5">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
        <div className="flex-1">
          <h2 className="font-semibold text-slate-900">New run</h2>
          <p className="mt-1 text-sm text-slate-500">
            Upload an RFP PDF. Five agents extract the requirements, find the evidence, draft a cited response, check every
            claim and recommend whether to bid. You confirm the requirements and approve the decision.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <input ref={input} type="file" accept="application/pdf" className="hidden"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          <Button variant="secondary" onClick={() => input.current?.click()} disabled={disabled || busy}>
            <FileUp className="h-4 w-4" />
            {file ? file.name.slice(0, 28) : 'Choose PDF'}
          </Button>
          <Button onClick={start} disabled={!file || disabled} loading={busy}>
            <Upload className="h-4 w-4" />
            Start run
          </Button>
        </div>
      </div>
      {disabled && (
        <p className="mt-3 flex items-center gap-1.5 text-sm text-amber-700">
          <Info className="h-4 w-4" /> Live runs are switched off. Past runs below are still available.
        </p>
      )}
      {live && live.live_runs && (
        <p className="mt-3 text-xs text-slate-400">Up to {live.daily_cap} live runs a day, each with a token budget.</p>
      )}
      {error && <p className="mt-3 text-sm text-rose-600">{error}</p>}
    </Card>
  )
}

export function RunsPage() {
  const [runs, setRuns] = useState<Run[] | null>(null)
  const [live, setLive] = useState<ApiConfig | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    const load = () =>
      api.runs().then(setRuns).catch((e) => setError(e instanceof Error ? e.message : 'Could not load runs'))
    load()
    api.config().then(setLive).catch(() => undefined)
    const timer = setInterval(load, 5000)
    return () => clearInterval(timer)
  }, [])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">RFP runs</h1>
        <p className="mt-1 text-sm text-slate-500">Each run takes one RFP from upload to a bid/no-bid recommendation.</p>
      </div>
      <NewRun live={live} />
      {error && <p className="text-sm text-rose-600">{error}</p>}
      {runs === null ? (
        <Spinner label="Loading runs" />
      ) : runs.length === 0 ? (
        <Empty>No runs yet. Upload an RFP to start.</Empty>
      ) : (
        <Card className="overflow-hidden">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">RFP</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Recommendation</th>
                <th className="hidden px-4 py-3 md:table-cell">Requirements</th>
                <th className="hidden px-4 py-3 md:table-cell">Cost</th>
                <th className="hidden px-4 py-3 lg:table-cell">Started</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {runs.map((run) => (
                <tr key={run.run_id} className="hover:bg-slate-50">
                  <td className="px-4 py-3">
                    <Link to={`/runs/${run.run_id}`} className="font-medium text-slate-900 hover:text-brand-700">
                      {run.buyer ?? run.rfp_name ?? run.run_id}
                    </Link>
                    <div className="text-xs text-slate-500">{run.rfp_title ?? run.rfp_name}</div>
                  </td>
                  <td className="px-4 py-3"><RunStatusChip status={run.status} /></td>
                  <td className="px-4 py-3">
                    {run.final_decision || run.decision ? (
                      <span className="flex items-center gap-2">
                        <DecisionBadge decision={(run.final_decision ?? run.decision)!} />
                        <span className="text-xs text-slate-500 tabular">{pct(run.score_pct)}</span>
                      </span>
                    ) : (
                      <span className="text-slate-400">—</span>
                    )}
                  </td>
                  <td className="hidden px-4 py-3 tabular md:table-cell">{run.requirement_count ?? '—'}</td>
                  <td className="hidden px-4 py-3 tabular md:table-cell">{usd(run.cost_usd)}</td>
                  <td className="hidden px-4 py-3 text-slate-500 lg:table-cell">
                    {new Date(run.started_at ?? run.created_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  )
}
