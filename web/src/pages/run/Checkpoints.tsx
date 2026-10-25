import { useState } from 'react'
import { AGENT_BY_ID } from '../../agents'
import { api } from '../../api'
import { useToast } from '../../components/toast'
import { Button, Card, DECISION_LABEL, DecisionBadge, cx, pct } from '../../components/ui'
import type { DecisionKind, RunView } from '../../types'

function Speaker({ agent }: { agent: 'rfp_analyst' | 'bid_strategist' }) {
  const a = AGENT_BY_ID[agent]
  return (
    <span className={cx('flex h-8 w-8 flex-none items-center justify-center rounded-full text-sm font-semibold text-white', a.color)}>
      {a.name[0]}
    </span>
  )
}

/** Checkpoint 1: the bid manager confirms (and optionally corrects) the extracted requirements. */
export function ConfirmBanner({
  view,
  edits,
  onDone,
  onReview,
}: {
  view: RunView
  edits: Record<string, Record<string, unknown>>
  onDone: () => void
  onReview: () => void
}) {
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const set = view.RequirementSet!
  const critical = set.requirements.filter((r) => r.critical).length

  async function confirm() {
    setBusy(true)
    try {
      await api.confirm(view.run.run_id, Object.entries(edits).map(([id, e]) => ({ id, ...e })))
      toast('success', 'Requirements confirmed. The Compliance Analyst is starting.')
      onDone()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not confirm')
      toast('error', err instanceof Error ? err.message : 'Could not confirm')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="border-amber-200 bg-amber-50/60 p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <Speaker agent="rfp_analyst" />
          <div className="text-sm">
            <div className="font-semibold text-slate-900">RFP Analyst · your turn</div>
            <div className="mt-0.5 text-slate-700">
              I found {set.requirements.length} requirements, {critical} of them pass/fail.
              {set.possible_misses.length > 0 && ` My scan flagged ${set.possible_misses.length} possible misses.`} Fix any
              category or pass/fail flag, then confirm and I’ll hand them to the Compliance Analyst.
            </div>
            <div className="mt-0.5 text-xs text-slate-500">Continues on its own after 2 minutes.</div>
            {Object.keys(edits).length > 0 && (
              <div className="mt-1 text-amber-800">{Object.keys(edits).length} correction(s) will be saved.</div>
            )}
            {error && <div className="mt-1 text-rose-600">{error}</div>}
          </div>
        </div>
        <div className="flex flex-none gap-2">
          <Button variant="secondary" onClick={onReview}>Review list</Button>
          <Button onClick={confirm} loading={busy}>Confirm requirements</Button>
        </div>
      </div>
    </Card>
  )
}

/** Checkpoint 2: the approver accepts the recommendation or overrides it with a reason. */
export function ApproveBanner({ view, onDone, onReview }: { view: RunView; onDone: () => void; onReview: () => void }) {
  const decision = view.BidRecommendation!.decision
  const [override, setOverride] = useState(false)
  const [final, setFinal] = useState<DecisionKind>(decision.decision)
  const [reason, setReason] = useState('')
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function submit(accepted: boolean) {
    setBusy(true)
    setError('')
    try {
      await api.approve(view.run.run_id, accepted ? { accepted } : { accepted, final_decision: final, reason })
      toast('success', accepted ? 'Decision approved. Writing the exports.' : 'Override recorded. Writing the exports.')
      onDone()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not record the approval')
      toast('error', err instanceof Error ? err.message : 'Could not record the approval')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="border-amber-200 bg-amber-50/60 p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-start gap-3">
          <Speaker agent="bid_strategist" />
          <div className="text-sm">
            <div className="flex flex-wrap items-center gap-2 font-semibold text-slate-900">
              Bid Strategist · your turn <DecisionBadge decision={decision.decision} />
              <span className="font-normal text-slate-500 tabular">{pct(decision.score_pct)} of available points</span>
            </div>
            <div className="mt-0.5 text-slate-700">
              I scored this with the knock-out rules and the RFP’s own points, in code. Approve it, or override with a
              reason for the audit log.
            </div>
            {override && (
              <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                <select value={final} onChange={(e) => setFinal(e.target.value as DecisionKind)}
                  className="rounded-lg border-0 px-3 py-2 text-sm ring-1 ring-inset ring-slate-300">
                  {(Object.keys(DECISION_LABEL) as DecisionKind[]).map((d) => (
                    <option key={d} value={d}>{DECISION_LABEL[d]}</option>
                  ))}
                </select>
                <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Reason for the override"
                  className="flex-1 rounded-lg border-0 px-3 py-2 text-sm ring-1 ring-inset ring-slate-300" />
              </div>
            )}
            {error && <div className="mt-1 text-rose-600">{error}</div>}
          </div>
        </div>
        <div className="flex flex-none gap-2">
          <Button variant="secondary" onClick={onReview}>Review decision</Button>
          {override ? (
            <Button variant="danger" onClick={() => submit(false)} loading={busy} disabled={!reason.trim()}>
              Record override
            </Button>
          ) : (
            <>
              <Button variant="secondary" onClick={() => setOverride(true)}>Override</Button>
              <Button onClick={() => submit(true)} loading={busy}>Approve</Button>
            </>
          )}
        </div>
      </div>
    </Card>
  )
}
