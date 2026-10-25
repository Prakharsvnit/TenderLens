import { UserRound, X } from 'lucide-react'
import type { ReactNode } from 'react'
import { AGENT_BY_ID, type AgentId } from '../agents'
import type { RunView } from '../types'
import { CATEGORY_LABEL, Chip, StatusChip, cx, pct } from './ui'

function Stage({ agent, human, title, children }: { agent?: AgentId; human?: boolean; title: string; children: ReactNode }) {
  const a = agent ? AGENT_BY_ID[agent] : undefined
  return (
    <li className="relative pl-9">
      <span
        className={cx(
          'absolute left-0 top-0 flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-semibold text-white',
          a ? a.color : 'bg-amber-500',
        )}
      >
        {human ? <UserRound className="h-3.5 w-3.5" /> : a?.name[0]}
      </span>
      <div className="text-sm font-semibold text-slate-900">{title}</div>
      <div className="mt-1 space-y-1.5 text-sm text-slate-700">{children}</div>
    </li>
  )
}

const VERDICT_STYLE = {
  supported: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
  unsupported: 'bg-amber-50 text-amber-700 ring-amber-600/20',
  contradicted: 'bg-rose-50 text-rose-700 ring-rose-600/20',
}

/** One requirement's path through the team: extracted, confirmed, assessed, answered, verified, scored. */
export function RequirementJourney({
  view,
  requirementId,
  onClose,
  onEvidence,
}: {
  view: RunView
  requirementId: string | null
  onClose: () => void
  onEvidence: (id: string) => void
}) {
  const req = view.RequirementSet?.requirements.find((r) => r.id === requirementId)
  if (!req) return null
  const assessment = view.AssessmentBatch?.assessments.find((a) => a.requirement_id === req.id)
  const gap = view.AssessmentBatch?.gaps.find((g) => g.requirement_id === req.id)
  const claims = (view.DraftMessage?.sections ?? []).flatMap((s) => s.claims).filter((c) => c.requirement_ids.includes(req.id))
  const verdicts = Object.fromEntries((view.ClaimVerdicts?.verdicts ?? []).map((v) => [v.claim_id, v]))
  const decision = view.BidRecommendation?.decision
  const knockOut = decision?.knock_outs.find((k) => k.requirement_id === req.id)
  const scoreLine = req.criterion ? decision?.score_lines.find((l) => l.criterion === req.criterion) : undefined
  const edited = (view.audit ?? []).some(
    (a) => a.action === 'confirm_requirements' && JSON.stringify(a.detail).includes(`"${req.id}"`),
  )

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-slate-900/20" onClick={onClose}>
      <aside
        role="dialog"
        aria-label={`Journey of requirement ${req.id}`}
        className="h-full w-full max-w-lg overflow-y-auto bg-white p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Requirement {req.id} · journey</div>
            <p className="mt-1 text-base font-medium text-slate-900">“{req.quote}”</p>
          </div>
          <button onClick={onClose} aria-label="Close" className="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700">
            <X className="h-5 w-5" />
          </button>
        </div>

        <ol className="mt-6 space-y-6 border-l-2 border-slate-100 [&>li]:-ml-3">
          <Stage agent="rfp_analyst" title="Extracted">
            <p>Quoted word for word from page {req.page} and checked against the PDF.</p>
            <div className="flex flex-wrap gap-1.5">
              <Chip>{CATEGORY_LABEL[req.category]}</Chip>
              <Chip>{req.obligation === 'mandatory' ? 'Mandatory' : 'Desirable'}</Chip>
              {req.critical && <Chip className="bg-rose-50 text-rose-700 ring-rose-600/20">Pass/fail</Chip>}
              {req.criterion && <Chip className="bg-brand-50 text-brand-700 ring-brand-600/20">Scored: {req.criterion}</Chip>}
            </div>
          </Stage>

          <Stage human title="Confirmed by the bid manager">
            <p>{edited ? 'Corrected at the checkpoint, then confirmed.' : 'Confirmed as extracted.'}</p>
          </Stage>

          <Stage agent="compliance_analyst" title="Assessed against the evidence">
            {assessment ? (
              <>
                <div className="flex items-center gap-2">
                  <StatusChip status={assessment.status} />
                  <span className="text-xs text-slate-500">confidence {pct(assessment.confidence)}</span>
                </div>
                <p>{assessment.rationale}</p>
                {assessment.evidence_ids.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {assessment.evidence_ids.map((id) => (
                      <button key={id} onClick={() => onEvidence(id)}
                        className="rounded-md bg-slate-100 px-2 py-0.5 font-mono text-xs text-brand-700 hover:bg-brand-50">
                        {id}
                      </button>
                    ))}
                  </div>
                )}
                {gap && (
                  <p className="rounded-lg bg-amber-50 p-2 text-xs text-amber-900">
                    <span className="font-medium capitalize">{gap.severity} gap:</span> {gap.description}
                    {gap.mitigation && <> · Mitigation: {gap.mitigation.description}</>}
                  </p>
                )}
              </>
            ) : (
              <p className="text-slate-500">Not assessed yet.</p>
            )}
          </Stage>

          <Stage agent="proposal_writer" title="Answered in the draft">
            {claims.length ? (
              claims.map((c) => <p key={c.id} className="rounded-lg bg-slate-50 p-2 text-xs"><span className="font-mono text-slate-400">{c.id}</span> {c.text}</p>)
            ) : (
              <p className="text-slate-500">{view.DraftMessage ? 'No claim answers this requirement.' : 'Not drafted yet.'}</p>
            )}
          </Stage>

          <Stage agent="claim_verifier" title="Verified">
            {claims.length && view.ClaimVerdicts ? (
              claims.map((c) => {
                const v = verdicts[c.id]
                return v ? (
                  <div key={c.id} className="flex flex-wrap items-center gap-2 text-xs">
                    <span className="font-mono text-slate-400">{c.id}</span>
                    <Chip className={VERDICT_STYLE[v.verdict]}>{v.verdict}</Chip>
                    <span className="text-slate-500">grounding {v.grounding_score.toFixed(2)}</span>
                    {v.note && <span className="text-slate-600">{v.note}</span>}
                  </div>
                ) : null
              })
            ) : (
              <p className="text-slate-500">Nothing to verify.</p>
            )}
          </Stage>

          <Stage agent="bid_strategist" title="Counted in the decision">
            {decision ? (
              <>
                {knockOut && (
                  <p>
                    Knock-out check <span className="font-medium">{knockOut.description}</span>: {knockOut.outcome}.
                  </p>
                )}
                {scoreLine ? (
                  <p>
                    Feeds “{scoreLine.criterion}”: {scoreLine.earned} of {scoreLine.points} points.
                  </p>
                ) : (
                  !knockOut && <p className="text-slate-500">Not tied to a scored criterion or knock-out rule.</p>
                )}
              </>
            ) : (
              <p className="text-slate-500">Not decided yet.</p>
            )}
          </Stage>
        </ol>
      </aside>
    </div>
  )
}
