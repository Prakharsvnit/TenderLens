import { CheckCircle2, ClipboardCheck, Gauge, ShieldCheck, XCircle } from 'lucide-react'
import { type ReactNode, useState } from 'react'
import { api } from '../../api'
import { Button, Card, Chip, DECISION_LABEL, Empty, cx, pct, usd } from '../../components/ui'
import type { EvalReport, RunView, TraceEvent } from '../../types'

const METRIC_LABEL: Record<string, string> = {
  extraction_recall: 'Requirement recall',
  critical_recall: 'Critical requirement recall',
  extraction_precision: 'Extraction precision',
  status_accuracy: 'Compliance status accuracy',
  citation_validity: 'Citation validity',
  evidence_backed_claim_rate: 'Evidence-backed claims',
  task_completion: 'Task completion',
  handoff_validity: 'Agent hand-off validity',
  redundant_tool_call_rate: 'Redundant tool calls',
}
const LOWER_IS_BETTER = new Set(['redundant_tool_call_rate'])

function passes(name: string, value: number, target: number) {
  return LOWER_IS_BETTER.has(name) ? value <= target : value >= target
}

function Section({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <Card className="p-5">
      <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-900">
        <span className="text-brand-600">{icon}</span>
        {title}
      </h3>
      <div className="mt-3">{children}</div>
    </Card>
  )
}

function EvalSection({ report }: { report: EvalReport }) {
  const [open, setOpen] = useState<string | null>(null)
  const lists: [string, string[]][] = [
    ['Missed gold requirements', report.missed.map((m) => `${m.gold} (p${m.page}): ${m.quote}`)],
    ['Extracted but not a requirement in the gold set', report.not_in_gold.map((r) => `${r.id} (p${r.page}): ${r.quote}`)],
    ['Status mismatches', report.wrong_status.map((w) => `${w.gold}: got ${w.got ?? 'none'}, expected ${w.expected.join(' or ')}`)],
  ]
  return (
    <>
      <p className="text-sm text-slate-600">
        Scored against a hand-labelled gold set of {report.gold_size} key requirements. Decision{' '}
        <span className="font-medium text-slate-900">{report.decision ? DECISION_LABEL[report.decision] : '—'}</span>
        {report.expected_decision && (
          <>
            , expected <span className="font-medium text-slate-900">{DECISION_LABEL[report.expected_decision]}</span>
          </>
        )}
        .
      </p>
      <div className="mt-3 overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="text-left text-xs font-medium uppercase tracking-wide text-slate-500">
            <tr>
              <th className="py-2 pr-3">Metric</th>
              <th className="py-2 pr-3 text-right">Value</th>
              <th className="py-2 pr-3 text-right">Target</th>
              <th className="py-2" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {Object.entries(report.metrics).map(([name, value]) => {
              const target = report.targets[name]
              const ok = passes(name, value, target)
              return (
                <tr key={name}>
                  <td className="py-2 pr-3 text-slate-700">{METRIC_LABEL[name] ?? name}</td>
                  <td className="py-2 pr-3 text-right font-medium tabular text-slate-900">{pct(value)}</td>
                  <td className="py-2 pr-3 text-right tabular text-slate-500">
                    {LOWER_IS_BETTER.has(name) ? '≤' : '≥'} {pct(target)}
                  </td>
                  <td className="py-2">
                    {ok ? (
                      <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                    ) : (
                      <XCircle className="h-4 w-4 text-rose-500" />
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {report.missed_critical.length > 0 && (
        <p className="mt-3 text-sm text-rose-700">Missed critical requirements: {report.missed_critical.join(', ')}</p>
      )}
      <div className="mt-3 space-y-2">
        {lists.map(([title, items]) =>
          items.length ? (
            <div key={title}>
              <button className="text-sm font-medium text-brand-700 hover:underline" onClick={() => setOpen(open === title ? null : title)}>
                {open === title ? 'Hide' : 'Show'} {title.toLowerCase()} ({items.length})
              </button>
              {open === title && (
                <ul className="mt-1 max-h-64 list-disc space-y-0.5 overflow-y-auto pl-5 text-xs text-slate-600">
                  {items.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              )}
            </div>
          ) : null,
        )}
      </div>
    </>
  )
}

/** Evals, budgets, guardrails and the human audit trail: how the system is measured and kept in check. */
export function QualityTab({
  view,
  trace,
  canEvaluate,
  onEvaluated,
}: {
  view: RunView
  trace: TraceEvent[]
  canEvaluate: boolean
  onEvaluated: () => void
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const { run } = view
  const tokens = trace.filter((e) => e.kind === 'model_call').reduce((n, e) => n + e.tokens_in + e.tokens_out, 0)
  const cost = trace.reduce((n, e) => n + e.cost_usd, 0)
  const budget = view.limits?.run_token_budget ?? 0
  const threshold = view.limits?.grounding_threshold ?? 0.6
  const screened = trace.find((e) => e.kind === 'validation' && e.name === 'screened')
  const grounding = trace
    .filter((e) => e.kind === 'guardrail')
    .map((e) => Number(/grounding=([\d.]+)/.exec(e.detail)?.[1]))
    .filter((g) => !Number.isNaN(g))
  const grounded = grounding.filter((g) => g >= threshold).length
  const checks = Object.entries(
    trace
      .filter((e) => e.kind === 'validation')
      .reduce<Record<string, number>>((by, e) => ({ ...by, [e.name]: (by[e.name] ?? 0) + 1 }), {}),
  ).sort((a, b) => b[1] - a[1])

  async function evaluate() {
    setBusy(true)
    setError('')
    try {
      await api.evaluate(run.run_id)
      onEvaluated()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not run the eval')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <div className="lg:col-span-2">
        <Section icon={<ClipboardCheck className="h-4 w-4" />} title="Evaluation against the gold set">
          {view.eval ? <EvalSection report={view.eval} /> : <Empty>This run has not been evaluated yet.</Empty>}
          {canEvaluate && run.status === 'complete' && (
            <div className="mt-4 flex items-center gap-3">
              <Button variant="secondary" onClick={evaluate} loading={busy}>
                {view.eval ? 'Re-run eval' : 'Run eval'}
              </Button>
              <span className="text-xs text-slate-500">Scores the saved run. No model calls, no cost.</span>
            </div>
          )}
          {error && <p className="mt-2 text-sm text-rose-600">{error}</p>}
        </Section>
      </div>

      <Section icon={<Gauge className="h-4 w-4" />} title="Budget and cost">
        <div className="flex items-baseline justify-between text-sm">
          <span className="text-slate-600">Tokens used of the run budget</span>
          <span className="font-medium tabular text-slate-900">
            {tokens.toLocaleString()} / {budget.toLocaleString()}
          </span>
        </div>
        <div className="mt-2 h-2.5 overflow-hidden rounded-full bg-slate-100">
          <div
            className={cx('h-full', tokens / budget > 0.8 ? 'bg-amber-500' : 'bg-brand-600')}
            style={{ width: `${Math.min(100, budget ? (tokens / budget) * 100 : 0)}%` }}
          />
        </div>
        <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
          <div>
            <dt className="text-slate-500">Model cost</dt>
            <dd className="font-medium tabular text-slate-900">{usd(cost)}</dd>
          </div>
          <div>
            <dt className="text-slate-500">Model calls</dt>
            <dd className="font-medium tabular text-slate-900">{trace.filter((e) => e.kind === 'model_call').length}</dd>
          </div>
        </dl>
        <p className="mt-3 text-xs text-slate-500">
          A run stops when it reaches its token budget. Each agent also has model-call and tool-call limits, and once
          its tools are spent it can only give its answer.
        </p>
      </Section>

      <Section icon={<ShieldCheck className="h-4 w-4" />} title="Bedrock Guardrails">
        <p className="text-sm text-slate-600">
          <span className="font-medium text-slate-900">Input screening: </span>
          {screened?.detail ?? 'not recorded'} (prompt-attack filter on every page before any agent reads it).
        </p>
        <p className="mt-2 text-sm text-slate-600">
          <span className="font-medium text-slate-900">Contextual grounding: </span>
          {grounding.length
            ? `${grounded} of ${grounding.length} claim checks scored at or above ${threshold}; below that a claim can't be marked supported.`
            : 'no claims checked yet.'}
        </p>
        {grounding.length > 0 && (
          <div className="mt-3 flex h-10 items-end gap-px" title="Grounding score of each claim check">
            {grounding.map((g, i) => (
              <div
                key={i}
                className={cx('flex-1 rounded-t-sm', g >= threshold ? 'bg-emerald-500' : 'bg-rose-400')}
                style={{ height: `${Math.max(6, g * 100)}%` }}
              />
            ))}
          </div>
        )}
      </Section>

      <Section icon={<CheckCircle2 className="h-4 w-4" />} title="Automatic checks on agent output">
        {checks.length ? (
          <div className="flex flex-wrap gap-1.5">
            {checks.map(([name, n]) => (
              <Chip key={name} className="bg-amber-50 font-mono text-amber-700 ring-amber-600/20">
                {name} × {n}
              </Chip>
            ))}
          </div>
        ) : (
          <Empty>No checks recorded yet.</Empty>
        )}
        <p className="mt-3 text-xs text-slate-500">
          Every hand-off is validated against its schema. Quotes must exist in the PDF, citations must point at
          retrieved evidence, and verdicts are overridden when grounding is too low.
        </p>
      </Section>

      <Section icon={<ClipboardCheck className="h-4 w-4" />} title="Human decisions (audit log)">
        {view.audit?.length ? (
          <ul className="space-y-2 text-sm">
            {view.audit.map((a, i) => (
              <li key={i} className="flex flex-wrap items-baseline gap-x-2">
                <span className="font-mono text-xs text-slate-400">{new Date(a.at).toLocaleString()}</span>
                <span className="font-medium text-slate-900">{a.action.replaceAll('_', ' ')}</span>
                <span className="text-slate-500">by {a.actor}</span>
              </li>
            ))}
          </ul>
        ) : (
          <Empty>No human decisions yet.</Empty>
        )}
      </Section>
    </div>
  )
}
