import { CircleCheck, CircleX, Wrench } from 'lucide-react'
import { Card, DECISION_LABEL, DecisionBadge, Empty, StatusChip, cx, pct } from '../../components/ui'
import type { RunView } from '../../types'

const OUTCOME = {
  met: { icon: CircleCheck, style: 'text-emerald-600', label: 'Met' },
  fixable: { icon: Wrench, style: 'text-amber-600', label: 'Fixable' },
  fatal: { icon: CircleX, style: 'text-rose-600', label: 'Fatal' },
}

export function DecisionTab({ view, onEvidence }: { view: RunView; onEvidence: (id: string) => void }) {
  const d = view.BidRecommendation?.decision
  if (!d) return <Empty>The Bid Strategist has not scored the bid yet.</Empty>

  return (
    <div className="space-y-5">
      <Card className="p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Recommendation</div>
            <div className="mt-2 flex flex-wrap items-center gap-3">
              <DecisionBadge decision={d.decision} large />
              <span className="text-sm text-slate-600 tabular">
                {d.score} of {d.max_score} points ({pct(d.score_pct)})
              </span>
            </div>
          </div>
          {view.approval && (
            <div className="rounded-lg bg-slate-50 px-4 py-2 text-sm text-slate-600">
              {view.approval.accepted ? 'Approved' : 'Overridden to'}{' '}
              {!view.approval.accepted && <b>{DECISION_LABEL[view.approval.final_decision]} </b>}
              by {view.approval.approver}
              {view.approval.reason && <div className="text-xs text-slate-500">Reason: {view.approval.reason}</div>}
            </div>
          )}
        </div>
        {d.rationale && <p className="mt-4 text-sm leading-relaxed text-slate-700">{d.rationale}</p>}
        <p className="mt-3 text-xs text-slate-400">
          Knock-outs first, then a score weighted by the RFP's own points. Computed in code from the bid policy; the
          model only explains it.
        </p>
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card className="p-5">
          <h3 className="text-sm font-semibold text-slate-900">Knock-out checks</h3>
          <ul className="mt-3 space-y-3">
            {d.knock_outs.map((k) => {
              const o = OUTCOME[k.outcome]
              return (
                <li key={k.rule_id} className="flex gap-3 text-sm">
                  <o.icon className={cx('mt-0.5 h-5 w-5 flex-none', o.style)} />
                  <div>
                    <div className="font-medium text-slate-800">
                      {k.description} <span className={cx('text-xs font-semibold', o.style)}>{o.label}</span>
                    </div>
                    {k.fix && <div className="text-slate-600">{k.fix}</div>}
                    <div className="mt-0.5 flex flex-wrap gap-1">
                      {k.evidence_ids.map((id) => (
                        <button key={id} onClick={() => onEvidence(id)} className="font-mono text-[11px] text-brand-700 hover:underline">
                          {id}
                        </button>
                      ))}
                    </div>
                  </div>
                </li>
              )
            })}
            {d.knock_outs.length === 0 && <li className="text-sm text-slate-500">No knock-out rule applies to this RFP.</li>}
          </ul>
        </Card>

        <Card className="p-5">
          <h3 className="text-sm font-semibold text-slate-900">Score by evaluation criterion</h3>
          <div className="mt-3 space-y-2.5">
            {d.score_lines.map((line) => (
              <div key={line.criterion} className="text-sm">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-slate-700">{line.criterion}</span>
                  <span className="flex items-center gap-2">
                    <StatusChip status={line.status} />
                    <span className="w-14 text-right tabular text-slate-900">{line.earned}/{line.points}</span>
                  </span>
                </div>
                <div className="mt-1 h-1.5 rounded-full bg-slate-100">
                  <div className="h-1.5 rounded-full bg-brand-500" style={{ width: `${(line.earned / line.points) * 100}%` }} />
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {(d.conditions.length > 0 || d.what_ifs.length > 0) && (
        <div className="grid gap-5 lg:grid-cols-2">
          {d.conditions.length > 0 && (
            <Card className="p-5">
              <h3 className="text-sm font-semibold text-slate-900">Conditions before submitting</h3>
              <ul className="mt-3 list-disc space-y-1.5 pl-5 text-sm text-slate-700">
                {d.conditions.map((c, i) => <li key={i}>{c}</li>)}
              </ul>
            </Card>
          )}
          {d.what_ifs.length > 0 && (
            <Card className="p-5">
              <h3 className="text-sm font-semibold text-slate-900">What-ifs tested by the Strategist</h3>
              <ul className="mt-3 space-y-2 text-sm">
                {d.what_ifs.map((w, i) => (
                  <li key={i} className="flex items-center justify-between gap-3 rounded-lg bg-slate-50 px-3 py-2">
                    <span className="text-slate-700">{w.change}</span>
                    <span className="flex flex-none items-center gap-2 tabular">
                      {pct(w.score_pct)} <DecisionBadge decision={w.decision} />
                    </span>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>
      )}
    </div>
  )
}
