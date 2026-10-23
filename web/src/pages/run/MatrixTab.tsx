import { useMemo, useState } from 'react'
import { CATEGORY_LABEL, Card, Chip, Empty, STATUS_LABEL, StatusChip, cx } from '../../components/ui'
import type { RunView, Status } from '../../types'

export function MatrixTab({ view, onEvidence }: { view: RunView; onEvidence: (id: string) => void }) {
  const [filter, setFilter] = useState<Status | 'all'>('all')
  const batch = view.AssessmentBatch
  const reqs = view.RequirementSet?.requirements ?? []
  const byReq = useMemo(() => Object.fromEntries((batch?.assessments ?? []).map((a) => [a.requirement_id, a])), [batch])
  const docTitle = useMemo(() => Object.fromEntries((batch?.evidence ?? []).map((e) => [e.id, e.doc_title])), [batch])
  if (!batch) return <Empty>The Compliance Analyst is still searching the evidence.</Empty>

  const rows = reqs.filter((r) => filter === 'all' || byReq[r.id]?.status === filter)
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {(['all', 'met', 'partial', 'not_met', 'no_evidence'] as const).map((s) => (
          <button key={s} onClick={() => setFilter(s)}
            className={cx('rounded-full px-3 py-1 text-xs font-medium ring-1 ring-inset',
              filter === s ? 'bg-brand-600 text-white ring-brand-600' : 'bg-white text-slate-600 ring-slate-300 hover:bg-slate-50')}>
            {s === 'all' ? 'All' : STATUS_LABEL[s]}
          </button>
        ))}
      </div>
      <Card className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-3 py-3">ID</th>
              <th className="px-3 py-3">Requirement</th>
              <th className="px-3 py-3">Status</th>
              <th className="px-3 py-3">Evidence</th>
              <th className="px-3 py-3">Rationale</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 align-top">
            {rows.map((r) => {
              const a = byReq[r.id]
              return (
                <tr key={r.id}>
                  <td className="px-3 py-2.5 font-mono text-xs text-slate-500">
                    {r.id}
                    <div className="mt-0.5 font-sans">p.{r.page}</div>
                  </td>
                  <td className="max-w-md px-3 py-2.5 text-slate-800">
                    {r.quote}
                    <div className="mt-1 flex flex-wrap gap-1">
                      <Chip>{CATEGORY_LABEL[r.category]}</Chip>
                      {r.critical && <Chip className="bg-rose-50 text-rose-700 ring-rose-600/20">Pass/fail</Chip>}
                    </div>
                  </td>
                  <td className="px-3 py-2.5">
                    {a ? <StatusChip status={a.status} /> : '—'}
                    {a && <div className="mt-1 text-xs text-slate-400 tabular">{Math.round(a.confidence * 100)}% sure</div>}
                  </td>
                  <td className="px-3 py-2.5">
                    <div className="flex flex-col gap-1">
                      {a?.evidence_ids.map((id) => (
                        <button key={id} onClick={() => onEvidence(id)}
                          className="text-left text-xs font-medium text-brand-700 hover:underline">
                          {id} <span className="font-normal text-slate-500">{docTitle[id]}</span>
                        </button>
                      ))}
                    </div>
                  </td>
                  <td className="max-w-sm px-3 py-2.5 text-slate-600">{a?.rationale}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </Card>
    </div>
  )
}
