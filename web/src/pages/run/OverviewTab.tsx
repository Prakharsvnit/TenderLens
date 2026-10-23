import { Card, DecisionBadge, Empty, STATUS_LABEL, Stat, cx, duration, pct, usd } from '../../components/ui'
import type { RunView, Status, TraceEvent } from '../../types'

const BAR: Record<Status, string> = {
  met: 'bg-emerald-500',
  partial: 'bg-amber-400',
  not_met: 'bg-rose-500',
  no_evidence: 'bg-slate-300',
}

export function OverviewTab({ view, trace }: { view: RunView; trace: TraceEvent[] }) {
  const { run } = view
  const k = run.kpis
  const counts = run.status_counts
  const total = counts ? Object.values(counts).reduce((a, b) => a + b, 0) : 0
  const decision = view.BidRecommendation?.decision
  const agents = new Set(trace.map((e) => e.agent).filter((a) => a !== 'guardrails'))
  const toolCalls = trace.filter((e) => e.kind === 'tool_call').length

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Time to first draft" value={duration(k?.time_to_first_draft_s)} hint="Machine time, excluding the human checkpoint" />
        <Stat label="Requirement coverage" value={pct(k?.requirement_coverage)} hint={k ? `${pct(k.mandatory_coverage)} of mandatory answered` : 'Answered with a supported claim'} />
        <Stat label="Evidence-backed claims" value={pct(k?.evidence_backed_claim_rate)} hint={run.claims ? `${run.claims} claims checked by the Verifier` : 'Claims the evidence supports'} />
        <Stat label="Critical requirements" value={run.critical_count ?? '—'} hint={`${run.possible_misses ?? 0} possible misses flagged for review`} />
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        <Card className="p-5 lg:col-span-2">
          <h3 className="text-sm font-semibold text-slate-900">Compliance position</h3>
          {counts && total > 0 ? (
            <>
              <div className="mt-4 flex h-3 overflow-hidden rounded-full bg-slate-100">
                {(Object.keys(BAR) as Status[]).map((s) =>
                  counts[s] ? <div key={s} className={BAR[s]} style={{ width: `${(counts[s] / total) * 100}%` }} /> : null,
                )}
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
                {(Object.keys(BAR) as Status[]).map((s) => (
                  <div key={s} className="flex items-center gap-2">
                    <span className={cx('h-2.5 w-2.5 rounded-sm', BAR[s])} />
                    <span className="text-slate-600">{STATUS_LABEL[s]}</span>
                    <span className="ml-auto font-medium tabular text-slate-900">{counts[s] ?? 0}</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <p className="mt-3 text-sm text-slate-500">Appears once the Compliance Analyst has assessed the requirements.</p>
          )}
        </Card>

        <Card className="p-5">
          <h3 className="text-sm font-semibold text-slate-900">Recommendation</h3>
          {decision ? (
            <div className="mt-3 space-y-2">
              <DecisionBadge decision={run.final_decision ?? decision.decision} large />
              <div className="text-sm text-slate-600 tabular">
                {decision.score} of {decision.max_score} points ({pct(decision.score_pct)})
              </div>
              {view.approval && (
                <div className="text-xs text-slate-500">
                  {view.approval.accepted ? 'Approved' : 'Overridden'} by {view.approval.approver}
                </div>
              )}
            </div>
          ) : (
            <p className="mt-3 text-sm text-slate-500">Appears once the Bid Strategist has scored the bid.</p>
          )}
        </Card>
      </div>

      {trace.length > 0 ? (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Stat label="Agents involved" value={agents.size} />
          <Stat label="Tool calls" value={toolCalls} />
          <Stat label="Tokens" value={(run.tokens_used ?? 0).toLocaleString()} />
          <Stat label="Model cost" value={usd(run.cost_usd)} hint="Amazon Nova on Bedrock" />
        </div>
      ) : (
        <Empty>The run is starting. Progress appears here as each agent finishes.</Empty>
      )}
    </div>
  )
}
