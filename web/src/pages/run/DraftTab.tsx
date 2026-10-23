import { CircleAlert, PenLine } from 'lucide-react'
import { useMemo } from 'react'
import { Card, Empty, cx } from '../../components/ui'
import type { RunView } from '../../types'

export function DraftTab({ view, onEvidence }: { view: RunView; onEvidence: (id: string) => void }) {
  const draft = view.DraftMessage
  const verdicts = useMemo(
    () => Object.fromEntries((view.ClaimVerdicts?.verdicts ?? []).map((v) => [v.claim_id, v])),
    [view.ClaimVerdicts],
  )
  if (!draft) return <Empty>The Proposal Writer has not drafted the response yet.</Empty>
  const flagged = Object.values(verdicts).filter((v) => v.verdict !== 'supported').length

  return (
    <div className="space-y-4">
      <Card className="flex flex-wrap items-center gap-x-6 gap-y-1 px-5 py-3 text-sm text-slate-600">
        <span>
          <span className="font-semibold text-slate-900">{Object.keys(verdicts).length}</span> claims verified
        </span>
        <span>
          <span className={cx('font-semibold', flagged ? 'text-rose-600' : 'text-emerald-600')}>{flagged}</span> unsupported
        </span>
        <span>Rewrite rounds: {view.run.rewrite_rounds ?? 0}</span>
        <span className="text-xs text-slate-400">Click a citation to see its passage. Hover a red claim for the Verifier's note.</span>
      </Card>
      {draft.sections.map((section) => (
        <Card key={section.id} className="p-5">
          <h3 className="font-semibold text-slate-900">{section.title}</h3>
          {section.rfp_reference && <div className="text-xs text-slate-500">Answers: {section.rfp_reference}</div>}
          <p className="mt-3 text-sm leading-7 text-slate-700">
            {section.claims.map((claim) => {
              const v = verdicts[claim.id]
              const bad = v && v.verdict !== 'supported'
              return (
                <span key={claim.id} title={bad ? `${v.verdict}: ${v.note}` : v ? `grounding ${v.grounding_score}` : undefined}
                  className={cx(bad && 'rounded bg-rose-50 text-rose-800 underline decoration-rose-300 decoration-wavy')}>
                  {claim.text}{' '}
                  {claim.evidence_ids.map((id) => (
                    <button key={id} onClick={() => onEvidence(id)}
                      className="mr-1 rounded bg-slate-100 px-1 font-mono text-[10px] text-slate-600 hover:bg-brand-100 hover:text-brand-700">
                      {id}
                    </button>
                  ))}
                </span>
              )
            })}
          </p>
          {section.sme_placeholders.length > 0 && (
            <ul className="mt-3 space-y-1.5">
              {section.sme_placeholders.map((p, i) => (
                <li key={i} className="flex items-start gap-2 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
                  <PenLine className="mt-0.5 h-4 w-4 flex-none" />
                  <span><span className="font-medium">SME input needed:</span> {p}</span>
                </li>
              ))}
            </ul>
          )}
          {section.claims.length === 0 && section.sme_placeholders.length === 0 && (
            <p className="mt-2 flex items-center gap-1.5 text-sm text-slate-400"><CircleAlert className="h-4 w-4" /> Empty section</p>
          )}
        </Card>
      ))}
    </div>
  )
}
