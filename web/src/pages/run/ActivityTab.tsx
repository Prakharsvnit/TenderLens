import { Ban, Brain, CheckCircle2, MessageSquareReply, ShieldCheck, Sparkles, UserRound, Wrench } from 'lucide-react'
import { useMemo, useState } from 'react'
import { AGENT_BY_ID, agentName, type AgentId } from '../../agents'
import { Card, Empty, cx } from '../../components/ui'
import { corrections, invocations, isAnswer, isBlocked, turns, type Invocation } from '../../traceModel'
import type { AuditEvent, Run, TraceEvent } from '../../types'

const VERB: Record<string, string> = {
  rfp_analyst: 'read the RFP',
  compliance_analyst: 'assessed a batch of requirements',
  proposal_writer: 'drafted the response',
  claim_verifier: 'checked claims against evidence',
  bid_strategist: 'scored the bid',
}

function dot(agent: string) {
  return AGENT_BY_ID[agent as AgentId]?.color ?? 'bg-slate-400'
}

function time(at: string) {
  return new Date(at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function summary(inv: Invocation): { text: string; facts: string[]; flags: string[] } {
  const loop = turns(inv)
  if (!loop.length) {
    const v = inv.events.find((e) => e.kind === 'validation' || e.kind === 'guardrail')
    return { text: `${agentName(inv.agent)}: ${v?.detail ?? v?.name ?? 'checked'}`, facts: [], flags: [] }
  }
  const calls = loop.flatMap((t) => t.tools).filter((t) => !isAnswer(t))
  const used = calls.filter((t) => !isBlocked(t))
  const blocked = calls.length - used.length
  const names = [...new Set(used.map((t) => t.name))]
  const tokens = loop.reduce((n, t) => n + t.model.tokens_in + t.model.tokens_out, 0)
  const rewrite = inv.agent === 'proposal_writer' && !inv.step.endsWith('-0')
  const text = `${agentName(inv.agent)} ${rewrite ? 'rewrote the flagged claims' : VERB[inv.agent] ?? 'ran'}`
  const facts = [
    `${loop.length} turn${loop.length === 1 ? '' : 's'}`,
    used.length ? `${used.length} tool call${used.length === 1 ? '' : 's'} (${names.join(', ')})` : 'no tools needed',
    `${tokens.toLocaleString()} tokens`,
    `${inv.seconds.toFixed(1)}s`,
  ]
  const flags = [
    ...(blocked ? [`${blocked} blocked by tool budget`] : []),
    ...inv.events.filter((e) => e.kind === 'validation' && e.name !== 'schema').map((e) => e.name.replace(/_/g, ' ')),
    ...inv.events.filter((e) => e.kind === 'validation' && e.name === 'schema' && e.detail.startsWith('no ')).map(() => 'answer retried'),
  ]
  return { text, facts, flags }
}

/** The agent loop for one invocation: each model turn (think), the tools it called (act) and what came back (observe). */
function LoopView({ inv }: { inv: Invocation }) {
  const loop = turns(inv)
  const checks = inv.events.filter((e) => e.kind === 'validation' || e.kind === 'guardrail')
  return (
    <Card className="p-5">
      <div className="flex items-center gap-2">
        <span className={cx('h-2.5 w-2.5 rounded-full', dot(inv.agent))} />
        <h3 className="font-semibold text-slate-900">{agentName(inv.agent)}</h3>
        <span className="font-mono text-xs text-slate-400">{inv.step}</span>
      </div>
      <p className="mt-1 text-xs text-slate-500">
        Each turn the model decides: call tools, or answer. Tool results go back into the next turn.
      </p>
      {loop.length === 0 && <p className="mt-4 text-sm text-slate-600">No model calls: a rule-based check.</p>}
      <ol className="mt-4 space-y-4">
        {loop.map((t, i) => {
          const answer = t.tools.find(isAnswer)
          const calls = t.tools.filter((x) => !isAnswer(x))
          return (
            <li key={i} className="relative border-l-2 border-slate-200 pl-4">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <Brain className="h-4 w-4 text-brand-600" />
                <span className="font-medium text-slate-900">Turn {i + 1} · think</span>
                <span className="font-mono text-[11px] text-slate-400">{t.model.name}</span>
                <span className="text-xs tabular text-slate-500">
                  {t.model.tokens_in.toLocaleString()} in · {t.model.tokens_out.toLocaleString()} out
                </span>
              </div>
              <div className="mt-1 text-xs text-slate-600">
                {answer ? 'Decided it had enough and answered.' : `Decided to call ${calls.length} tool${calls.length === 1 ? '' : 's'}.`}
              </div>
              {calls.length > 0 && (
                <ul className="mt-2 space-y-1.5">
                  {calls.map((c, k) => (
                    <li key={k} className={cx('rounded-lg p-2 text-xs', isBlocked(c) ? 'bg-rose-50' : 'bg-slate-50')}>
                      <div className="flex items-center gap-1.5 font-medium text-slate-800">
                        {isBlocked(c) ? <Ban className="h-3.5 w-3.5 text-rose-600" /> : <Wrench className="h-3.5 w-3.5 text-sky-600" />}
                        <span className="font-mono">{c.name}</span>
                        {isBlocked(c) && <span className="text-rose-700">blocked: tool budget spent</span>}
                      </div>
                      {c.args && <div className="mt-1 break-words font-mono text-[11px] text-slate-600">act: {c.args}</div>}
                      {!isBlocked(c) && <div className="mt-1 line-clamp-3 break-words text-slate-600">observe: {c.detail}</div>}
                    </li>
                  ))}
                </ul>
              )}
              {answer && (
                <div className="mt-2 flex items-start gap-1.5 rounded-lg bg-emerald-50 p-2 text-xs text-emerald-800">
                  <MessageSquareReply className="mt-0.5 h-3.5 w-3.5 flex-none" />
                  <span className="line-clamp-3 break-words">
                    <span className="font-medium">Answer ({answer.name}):</span> {answer.args || answer.detail}
                  </span>
                </div>
              )}
            </li>
          )
        })}
      </ol>
      {checks.length > 0 && (
        <div className="mt-4 border-t border-slate-100 pt-3">
          <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Checks on this output</div>
          <ul className="mt-1.5 space-y-1 text-xs text-slate-600">
            {checks.slice(0, 12).map((c, k) => (
              <li key={k} className="flex items-start gap-1.5">
                {c.kind === 'guardrail' ? <ShieldCheck className="mt-0.5 h-3.5 w-3.5 text-emerald-600" /> : <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 text-amber-600" />}
                <span>
                  <span className="font-mono">{c.name}</span> {c.detail}
                </span>
              </li>
            ))}
            {checks.length > 12 && <li className="text-slate-400">and {checks.length - 12} more</li>}
          </ul>
        </div>
      )}
    </Card>
  )
}

type FeedItem = { kind: 'agent'; at: string; inv: Invocation } | { kind: 'human'; at: string; event: AuditEvent }

/** What the agents did, in order, with what they caught and fixed, and the reasoning behind any step. */
export function ActivityTab({ run, trace, audit }: { run: Run; trace: TraceEvent[]; audit: AuditEvent[] }) {
  const all = useMemo(() => invocations(trace), [trace])
  const fixes = useMemo(() => corrections(trace, run.rewrite_rounds), [trace, run.rewrite_rounds])
  const [selected, setSelected] = useState<number | null>(null)
  const [open, setOpen] = useState<string | null>(null)
  if (trace.length === 0) return <Empty>The agents haven’t started yet.</Empty>

  const feed: FeedItem[] = [
    ...all.map((inv) => ({ kind: 'agent' as const, at: inv.at, inv })),
    ...audit.map((event) => ({ kind: 'human' as const, at: event.at, event })),
  ].sort((a, b) => a.at.localeCompare(b.at))
  const firstAgentRun = all.find((i) => turns(i).length > 0)
  const current = all.find((i) => i.id === selected) ?? firstAgentRun
  const live = !['complete', 'failed'].includes(run.status)

  return (
    <div className="space-y-5">
      <Card className="p-5">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-brand-600" />
          <h3 className="text-sm font-semibold text-slate-900">Caught and fixed by the system</h3>
        </div>
        {fixes.length === 0 ? (
          <p className="mt-2 text-sm text-slate-500">Nothing needed fixing yet.</p>
        ) : (
          <div className="mt-3 flex flex-wrap gap-2">
            {fixes.map((f) => (
              <button
                key={f.key}
                onClick={() => setOpen(open === f.key ? null : f.key)}
                aria-expanded={open === f.key}
                className={cx(
                  'rounded-lg px-3 py-1.5 text-left text-sm ring-1 ring-inset transition',
                  open === f.key ? 'bg-amber-100 ring-amber-400' : 'bg-amber-50 ring-amber-200 hover:ring-amber-300',
                )}
              >
                <span className="font-semibold tabular text-amber-800">{f.examples.length}</span>{' '}
                <span className="text-amber-900">{f.label}</span>
              </button>
            ))}
          </div>
        )}
        {open && (
          <ul className="mt-3 max-h-48 list-disc space-y-0.5 overflow-y-auto pl-5 text-xs text-slate-600">
            {fixes.find((f) => f.key === open)?.examples.map((x, i) => <li key={i} className="break-words">{x}</li>)}
          </ul>
        )}
      </Card>

      <div className="grid gap-5 lg:grid-cols-5">
        <div className="lg:col-span-2">
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-900">Activity</h3>
            {live && (
              <span className="inline-flex items-center gap-1.5 text-xs font-medium text-brand-700">
                <span className="h-2 w-2 animate-pulse rounded-full bg-brand-500" /> Live
              </span>
            )}
          </div>
          <ol className="max-h-[40rem] space-y-2 overflow-y-auto pr-1">
            {feed.map((item, i) => {
              if (item.kind === 'human')
                return (
                  <li key={`h${i}`} className="flex gap-2 rounded-lg bg-amber-50 p-3 text-sm ring-1 ring-amber-200">
                    <UserRound className="mt-0.5 h-4 w-4 flex-none text-amber-600" />
                    <div>
                      <div className="font-medium text-slate-900">
                        {item.event.actor} · {item.event.action.replaceAll('_', ' ')}
                      </div>
                      <div className="text-xs text-slate-500">{time(item.at)}</div>
                    </div>
                  </li>
                )
              const s = summary(item.inv)
              const active = current?.id === item.inv.id
              return (
                <li key={`a${item.inv.id}`}>
                  <button
                    onClick={() => setSelected(item.inv.id)}
                    className={cx(
                      'flex w-full gap-2 rounded-lg bg-white p-3 text-left text-sm ring-1 transition',
                      active ? 'ring-2 ring-brand-500' : 'ring-slate-200 hover:ring-slate-300',
                    )}
                  >
                    <span className={cx('mt-1.5 h-2 w-2 flex-none rounded-full', dot(item.inv.agent))} />
                    <div className="min-w-0">
                      <div className="text-slate-900">{s.text}</div>
                      {s.facts.length > 0 && <div className="mt-0.5 text-xs text-slate-500">{s.facts.join(' · ')}</div>}
                      {s.flags.length > 0 && (
                        <div className="mt-1 flex flex-wrap gap-1">
                          {[...new Set(s.flags)].map((f) => (
                            <span key={f} className="rounded bg-amber-50 px-1.5 py-0.5 text-[11px] text-amber-800">{f}</span>
                          ))}
                        </div>
                      )}
                      <div className="mt-0.5 font-mono text-[11px] text-slate-400">{item.inv.step} · {time(item.at)}</div>
                    </div>
                  </button>
                </li>
              )
            })}
          </ol>
        </div>
        <div className="lg:col-span-3">
          <h3 className="mb-2 text-sm font-semibold text-slate-900">Reasoning loop</h3>
          {current ? <LoopView inv={current} /> : <Empty>Pick an agent step on the left.</Empty>}
        </div>
      </div>
    </div>
  )
}
