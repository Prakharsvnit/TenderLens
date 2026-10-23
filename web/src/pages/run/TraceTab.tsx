import { Bot, ShieldCheck, Wrench } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Card, Chip, Empty, cx, usd } from '../../components/ui'
import type { TraceEvent } from '../../types'

const AGENTS: Record<string, string> = {
  rfp_analyst: 'RFP Analyst',
  compliance_analyst: 'Compliance Analyst',
  proposal_writer: 'Proposal Writer',
  claim_verifier: 'Claim Verifier',
  bid_strategist: 'Bid Strategist',
  guardrails: 'Guardrails',
}

const KIND_STYLE: Record<string, string> = {
  model_call: 'bg-brand-50 text-brand-700 ring-brand-600/20',
  tool_call: 'bg-sky-50 text-sky-700 ring-sky-600/20',
  guardrail: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
  validation: 'bg-amber-50 text-amber-700 ring-amber-600/20',
  error: 'bg-rose-50 text-rose-700 ring-rose-600/20',
}

/** Every model call, tool call and validation, per agent: the observability view of the run. */
export function TraceTab({ events }: { events: TraceEvent[] }) {
  const [agent, setAgent] = useState<string>('all')
  const summary = useMemo(() => {
    const by: Record<string, { model: number; tools: number; tokens: number; cost: number; ms: number; checks: number }> = {}
    for (const e of events) {
      const s = (by[e.agent] ??= { model: 0, tools: 0, tokens: 0, cost: 0, ms: 0, checks: 0 })
      if (e.kind === 'model_call') {
        s.model += 1
        s.tokens += e.tokens_in + e.tokens_out
        s.cost += e.cost_usd
      }
      if (e.kind === 'tool_call') s.tools += 1
      if (e.kind === 'validation') s.checks += 1
      if (e.kind === 'agent_end') s.ms += e.latency_ms
    }
    return by
  }, [events])
  if (events.length === 0) return <Empty>No trace yet.</Empty>

  const shown = events.filter((e) => e.kind !== 'agent_start' && (agent === 'all' || e.agent === agent))
  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {Object.entries(summary).map(([name, s]) => (
          <button key={name} onClick={() => setAgent(agent === name ? 'all' : name)}
            className={cx('rounded-xl border bg-white p-4 text-left shadow-sm transition', agent === name ? 'border-brand-500 ring-2 ring-brand-100' : 'border-slate-200 hover:border-slate-300')}>
            <div className="flex items-center gap-2 font-semibold text-slate-900">
              {name === 'guardrails' ? <ShieldCheck className="h-4 w-4 text-emerald-600" /> : <Bot className="h-4 w-4 text-brand-600" />}
              {AGENTS[name] ?? name}
            </div>
            <dl className="mt-2 grid grid-cols-3 gap-1 text-xs text-slate-500">
              <div><dt>Model calls</dt><dd className="text-sm font-medium text-slate-900 tabular">{s.model}</dd></div>
              <div><dt>Tool calls</dt><dd className="text-sm font-medium text-slate-900 tabular">{s.tools}</dd></div>
              <div><dt>Checks</dt><dd className="text-sm font-medium text-slate-900 tabular">{s.checks}</dd></div>
              <div><dt>Tokens</dt><dd className="text-sm font-medium text-slate-900 tabular">{s.tokens.toLocaleString()}</dd></div>
              <div><dt>Cost</dt><dd className="text-sm font-medium text-slate-900 tabular">{usd(s.cost)}</dd></div>
              <div><dt>Time</dt><dd className="text-sm font-medium text-slate-900 tabular">{(s.ms / 1000).toFixed(1)}s</dd></div>
            </dl>
          </button>
        ))}
      </div>

      <Card className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-3 py-2.5">Step</th>
              <th className="px-3 py-2.5">Agent</th>
              <th className="px-3 py-2.5">Event</th>
              <th className="px-3 py-2.5">Detail</th>
              <th className="px-3 py-2.5 text-right">Tokens</th>
              <th className="px-3 py-2.5 text-right">ms</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 align-top">
            {shown.map((e, i) => (
              <tr key={i}>
                <td className="px-3 py-2 font-mono text-xs text-slate-500">{e.step}</td>
                <td className="px-3 py-2 text-slate-700">{AGENTS[e.agent] ?? e.agent}</td>
                <td className="px-3 py-2">
                  <Chip className={KIND_STYLE[e.kind]}>
                    {e.kind === 'tool_call' && <Wrench className="h-3 w-3" />}
                    {e.kind.replace('_', ' ')}
                  </Chip>
                  {e.name && <div className="mt-0.5 font-mono text-[11px] text-slate-500">{e.name}</div>}
                </td>
                <td className="max-w-lg px-3 py-2 text-xs text-slate-600 break-words">{e.detail}</td>
                <td className="px-3 py-2 text-right tabular text-slate-600">{e.tokens_in + e.tokens_out || ''}</td>
                <td className="px-3 py-2 text-right tabular text-slate-600">{e.latency_ms || ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  )
}
