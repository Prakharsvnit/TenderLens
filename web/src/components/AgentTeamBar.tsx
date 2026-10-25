import { ArrowRight, Check, FileCheck2, Loader2, RotateCcw, UserRound } from 'lucide-react'
import type { ReactNode } from 'react'
import { AGENT_BY_ID, type AgentId } from '../agents'
import { DECISION_LABEL, cx, pct } from './ui'
import type { Run, TraceEvent } from '../types'
import { currentIndex, STEPS } from './steps'

type State = 'idle' | 'working' | 'waiting' | 'done' | 'failed'

interface Member {
  key: string
  step: string
  agent?: AgentId
  human?: string
  title: string
  handoff?: string
}

/** The team in workflow order: five agents, two human checkpoints, then publish. */
const TEAM: Member[] = [
  { key: 'rfp', step: 'extract', agent: 'rfp_analyst', title: 'RFP Analyst', handoff: 'requirements' },
  { key: 'confirm', step: 'confirm', human: 'You', title: 'Confirm requirements', handoff: 'confirmed list' },
  { key: 'comp', step: 'assess', agent: 'compliance_analyst', title: 'Compliance Analyst', handoff: 'matrix + gaps' },
  { key: 'writer', step: 'draft', agent: 'proposal_writer', title: 'Proposal Writer', handoff: 'cited claims' },
  { key: 'verifier', step: 'verify', agent: 'claim_verifier', title: 'Claim Verifier', handoff: 'verdicts' },
  { key: 'strategist', step: 'decide', agent: 'bid_strategist', title: 'Bid Strategist', handoff: 'recommendation' },
  { key: 'approve', step: 'approve', human: 'You', title: 'Approve decision', handoff: 'decision' },
  { key: 'publish', step: 'publish', title: 'Published' },
]

function stateOf(run: Run, step: string): State {
  const index = STEPS.findIndex((s) => s.id === step)
  const current = currentIndex(run)
  if (run.status === 'failed' && index === current) return 'failed'
  if (index < current) return 'done'
  if (index === current && run.status !== 'complete') {
    return run.status === 'awaiting_confirmation' || run.status === 'awaiting_approval' ? 'waiting' : 'working'
  }
  return run.status === 'complete' ? 'done' : 'idle'
}

/** One line on what the member is doing now, or what it produced. */
function line(m: Member, state: State, run: Run, trace: TraceEvent[]): string {
  const finished = (agent: string) => trace.filter((e) => e.kind === 'agent_end' && e.agent === agent).length
  if (state === 'idle') return m.agent ? AGENT_BY_ID[m.agent].input + ' →' : 'Not yet'
  if (state === 'waiting') return m.key === 'confirm' ? 'Review and confirm' : 'Accept or override'
  if (state === 'failed') return 'Stopped. See the error above.'
  const c = run.status_counts
  switch (m.key) {
    case 'rfp':
      return state === 'working'
        ? `Reading pages · ${Math.max(0, finished('rfp_analyst') - 1)} of ${run.pages ?? '?'} done`
        : `${run.requirement_count ?? 0} requirements, ${run.critical_count ?? 0} pass/fail`
    case 'confirm':
      return 'Confirmed'
    case 'comp':
      return state === 'working'
        ? `Searching evidence · ${finished('compliance_analyst')} of ${run.assess_batches ?? '?'} batches`
        : c
          ? `${c.met ?? 0} met · ${c.partial ?? 0} partial · ${c.not_met ?? 0} not met`
          : 'Assessed'
    case 'writer':
      return state === 'working' ? `Drafting · round ${(run.rewrite_rounds ?? 0) + 1}` : `${run.claims ?? 0} claims drafted`
    case 'verifier':
      return state === 'working'
        ? 'Checking each claim against its evidence'
        : `${(run.claims ?? 0) - (run.unsupported_claims ?? 0)} of ${run.claims ?? 0} supported`
    case 'strategist':
      return state === 'working'
        ? 'Scoring against the bid policy'
        : run.decision
          ? `${DECISION_LABEL[run.decision]} · ${pct(run.score_pct)}`
          : 'Decided'
    case 'approve':
      return run.final_decision ? `Final: ${DECISION_LABEL[run.final_decision]}` : 'Approved'
    default:
      return state === 'done' ? 'Matrix + draft ready' : 'Writing exports'
  }
}

const RING: Record<State, string> = {
  idle: 'border-slate-200 bg-white',
  working: 'border-transparent bg-white ring-2 ring-brand-500 shadow-md',
  waiting: 'border-transparent bg-amber-50 ring-2 ring-amber-500 shadow-md',
  done: 'border-slate-200 bg-white',
  failed: 'border-transparent bg-rose-50 ring-2 ring-rose-500',
}

function Badge({ state }: { state: State }) {
  const text = { idle: 'Idle', working: 'Working', waiting: 'Your turn', done: 'Done', failed: 'Failed' }[state]
  const style = {
    idle: 'text-slate-400',
    working: 'text-brand-700',
    waiting: 'text-amber-700',
    done: 'text-emerald-700',
    failed: 'text-rose-700',
  }[state]
  const icon: ReactNode =
    state === 'working' ? <Loader2 className="h-3 w-3 animate-spin" /> : state === 'done' ? <Check className="h-3 w-3" /> : null
  return <span className={cx('inline-flex items-center gap-1 text-[11px] font-medium uppercase tracking-wide', style)}>{icon}{text}</span>
}

/** Who is doing what right now: the agent team and the two human checkpoints, in hand-off order. */
export function AgentTeamBar({ run, trace }: { run: Run; trace: TraceEvent[] }) {
  const rounds = run.rewrite_rounds ?? 0
  return (
    <div>
      <ol className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-8">
        {TEAM.map((m, i) => {
          const state = stateOf(run, m.step)
          const agent = m.agent ? AGENT_BY_ID[m.agent] : undefined
          return (
            <li key={m.key} className="relative">
              <div className={cx('h-full rounded-xl border p-3 transition', RING[state], state === 'idle' && 'opacity-70')}>
                <div className="flex items-center gap-2">
                  <span
                    className={cx(
                      'flex h-6 w-6 flex-none items-center justify-center rounded-full text-white',
                      agent ? agent.color : m.human ? 'bg-amber-500' : 'bg-slate-500',
                    )}
                  >
                    {m.human ? <UserRound className="h-3.5 w-3.5" /> : agent ? <span className="text-[11px] font-semibold">{agent.name[0]}</span> : <FileCheck2 className="h-3.5 w-3.5" />}
                  </span>
                  <Badge state={state} />
                </div>
                <div className="mt-2 text-sm font-semibold leading-tight text-slate-900">{m.title}</div>
                <div className="mt-1 text-xs leading-snug text-slate-600">{line(m, state, run, trace)}</div>
                {m.key === 'verifier' && rounds > 0 && (
                  <div className="mt-1.5 inline-flex items-center gap-1 text-[11px] font-medium text-amber-700">
                    <RotateCcw className="h-3 w-3" /> {rounds} rewrite round{rounds === 1 ? '' : 's'} with the Writer
                  </div>
                )}
              </div>
              {m.handoff && i < TEAM.length - 1 && (
                <span className="pointer-events-none absolute -right-2 top-1/2 z-10 hidden -translate-y-1/2 rounded-full bg-slate-50 text-slate-300 lg:block" title={`Hands over: ${m.handoff}`}>
                  <ArrowRight className="h-4 w-4" />
                </span>
              )}
            </li>
          )
        })}
      </ol>
    </div>
  )
}
