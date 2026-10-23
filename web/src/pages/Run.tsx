import { ArrowLeft, Download, TriangleAlert } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import { EvidencePanel } from '../components/EvidencePanel'
import { StepTracker } from '../components/StepTracker'
import { Button, Card, RunStatusChip, Spinner, Tabs } from '../components/ui'
import type { Evidence, RunView, TraceEvent } from '../types'
import { ApproveBanner, ConfirmBanner } from './run/Checkpoints'
import { DecisionTab } from './run/DecisionTab'
import { DraftTab } from './run/DraftTab'
import { GapsTab } from './run/GapsTab'
import { MatrixTab } from './run/MatrixTab'
import { OverviewTab } from './run/OverviewTab'
import { RequirementsTab } from './run/RequirementsTab'
import { TraceTab } from './run/TraceTab'

type TabId = 'overview' | 'requirements' | 'matrix' | 'gaps' | 'draft' | 'decision' | 'trace'
const ACTIVE = new Set(['uploading', 'queued', 'running', 'awaiting_confirmation', 'awaiting_approval'])

export function RunPage() {
  const { runId = '' } = useParams()
  const [view, setView] = useState<RunView | null>(null)
  const [trace, setTrace] = useState<TraceEvent[]>([])
  const [tab, setTab] = useState<TabId>('overview')
  const [evidence, setEvidence] = useState<Evidence | null>(null)
  const [error, setError] = useState('')
  const [edits, setEdits] = useState<Record<string, Record<string, unknown>>>({})

  const load = useCallback(async () => {
    try {
      const [v, t] = await Promise.all([api.run(runId), api.trace(runId)])
      setView(v)
      setTrace(t)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load the run')
    }
  }, [runId])

  useEffect(() => {
    load()
  }, [load])

  const status = view?.run.status
  useEffect(() => {
    if (!status || !ACTIVE.has(status)) return
    const timer = setInterval(load, 3000)
    return () => clearInterval(timer)
  }, [status, load])

  const evidenceById = useMemo(
    () => Object.fromEntries((view?.AssessmentBatch?.evidence ?? []).map((e) => [e.id, e])),
    [view],
  )
  const openEvidence = (id: string) => setEvidence(evidenceById[id] ?? null)

  if (error && !view) return <p className="text-sm text-rose-600">{error}</p>
  if (!view) return <Spinner label="Loading run" />

  const { run } = view
  const reqs = view.RequirementSet?.requirements ?? []
  const gaps = view.AssessmentBatch?.gaps ?? []
  const claims = view.DraftMessage?.sections.reduce((n, s) => n + s.claims.length, 0)

  async function download(kind: 'matrix' | 'draft') {
    window.open(await api.exportUrl(runId, kind), '_blank')
  }

  return (
    <div className="space-y-5">
      <Link to="/" className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800">
        <ArrowLeft className="h-4 w-4" /> All runs
      </Link>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-xl font-semibold text-slate-900">{run.buyer ?? run.rfp_name}</h1>
            <RunStatusChip status={run.status} />
          </div>
          <p className="mt-1 text-sm text-slate-500">
            {run.rfp_title ?? run.rfp_name}
            {run.pages ? ` · ${run.pages} pages` : ''} · bidder: Cobalt Harbor IT Services (fictional)
          </p>
        </div>
        {run.status === 'complete' && (
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => download('matrix')}>
              <Download className="h-4 w-4" /> Matrix (XLSX)
            </Button>
            <Button variant="secondary" onClick={() => download('draft')}>
              <Download className="h-4 w-4" /> Draft (DOCX)
            </Button>
          </div>
        )}
      </div>

      <Card className="p-5">
        <StepTracker run={run} />
      </Card>

      {run.status === 'failed' && (
        <Card className="flex items-start gap-3 border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
          <TriangleAlert className="mt-0.5 h-4 w-4 flex-none" />
          <div>
            <div className="font-medium">The run stopped</div>
            <div className="mt-0.5">{run.error}</div>
          </div>
        </Card>
      )}
      {run.status === 'awaiting_confirmation' && view.RequirementSet && (
        <ConfirmBanner view={view} edits={edits} onDone={() => { setEdits({}); load() }} onReview={() => setTab('requirements')} />
      )}
      {run.status === 'awaiting_approval' && view.BidRecommendation && (
        <ApproveBanner view={view} onDone={load} onReview={() => setTab('decision')} />
      )}

      <Tabs<TabId>
        active={tab}
        onChange={setTab}
        tabs={[
          { id: 'overview', label: 'Overview' },
          { id: 'requirements', label: 'Requirements', count: reqs.length || undefined },
          { id: 'matrix', label: 'Compliance matrix' },
          { id: 'gaps', label: 'Gaps', count: gaps.length || undefined },
          { id: 'draft', label: 'Draft', count: claims || undefined },
          { id: 'decision', label: 'Decision' },
          { id: 'trace', label: 'Agent trace', count: trace.length || undefined },
        ]}
      />

      {tab === 'overview' && <OverviewTab view={view} trace={trace} />}
      {tab === 'requirements' && (
        <RequirementsTab view={view} editable={run.status === 'awaiting_confirmation'} edits={edits} setEdits={setEdits} />
      )}
      {tab === 'matrix' && <MatrixTab view={view} onEvidence={openEvidence} />}
      {tab === 'gaps' && <GapsTab view={view} />}
      {tab === 'draft' && <DraftTab view={view} onEvidence={openEvidence} />}
      {tab === 'decision' && <DecisionTab view={view} onEvidence={openEvidence} />}
      {tab === 'trace' && <TraceTab events={trace} />}

      <EvidencePanel evidence={evidence} onClose={() => setEvidence(null)} />
    </div>
  )
}
