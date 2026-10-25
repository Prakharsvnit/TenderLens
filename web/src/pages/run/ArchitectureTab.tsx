import {
  Bot,
  Check,
  Cloud,
  Database,
  FileText,
  GitBranch,
  Loader2,
  Lock,
  RotateCcw,
  ShieldCheck,
  UserRound,
  Workflow,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { currentIndex, STEPS } from '../../components/steps'
import { Card, Chip, cx, usd } from '../../components/ui'
import type { Run, TraceEvent } from '../../types'

type StepId = (typeof STEPS)[number]['id']

interface StepInfo {
  agent?: string
  lambda: string
  what: string
  models?: string[]
  tools?: string[]
}

/** What each Step Functions state runs. Kept in step with backend/tenderlens/pipeline and infra/. */
const INFO: Record<StepId, StepInfo> = {
  parse: {
    lambda: 'ParseStep',
    what: 'pdfplumber splits the PDF into pages; Bedrock Guardrails screens each page for prompt injection.',
    models: ['Guardrails · prompt attack'],
  },
  extract: {
    agent: 'RFP Analyst',
    lambda: 'ExtractStep',
    what: 'Nova Lite reads the scoring criteria. Nova Pro extracts requirements page by page, four in parallel. A shall/must scanner flags misses; every quote is checked against the PDF.',
    models: ['Nova Pro', 'Nova Lite'],
    tools: ['get_section'],
  },
  confirm: {
    lambda: 'Checkpoint (task token)',
    what: 'Paused on a Step Functions task token until the bid manager confirms; the API resumes the run.',
  },
  assess: {
    agent: 'Compliance Analyst',
    lambda: 'AssessStep × Map',
    what: 'A Map state fans out batches of ten. Hybrid search (BM25 + Titan embeddings) finds evidence; Nova Pro rules on each requirement with validated citations.',
    models: ['Nova Pro', 'Titan Embeddings V2'],
    tools: ['search_evidence', 'get_passage'],
  },
  draft: {
    agent: 'Proposal Writer',
    lambda: 'DraftStep',
    what: 'Nova Pro drafts claims tied to requirements and evidence. On a rewrite round it fixes or drops rejected claims.',
    models: ['Nova Pro'],
    tools: ['get_evidence'],
  },
  verify: {
    agent: 'Claim Verifier',
    lambda: 'VerifyStep',
    what: 'Guardrails grounding scores each claim; Nova Lite gives the verdict. Unsupported claims go back to the Writer, up to twice.',
    models: ['Nova Lite', 'Guardrails · grounding'],
    tools: ['check_grounding'],
  },
  decide: {
    agent: 'Bid Strategist',
    lambda: 'DecideStep',
    what: 'Applies the bid policy: knock-outs, a weighted score and what-ifs. Nova Pro explains the result.',
    models: ['Nova Pro'],
    tools: ['list_gaps', 'get_bid_policy', 'compute_score'],
  },
  approve: {
    lambda: 'Checkpoint (task token)',
    what: 'Paused again until a person approves or overrides with a reason; logged for audit.',
  },
  publish: {
    lambda: 'PublishStep',
    what: 'Writes the XLSX matrix and DOCX draft to S3; sends KPIs to CloudWatch.',
  },
}

const PLATFORM: { icon: ReactNode; title: string; body: string }[] = [
  { icon: <Cloud className="h-4 w-4" />, title: 'Web', body: 'React + Vite on S3 behind CloudFront' },
  { icon: <Lock className="h-4 w-4" />, title: 'Auth & API', body: 'API Gateway HTTP API with a Cognito JWT authorizer; read-only public routes for shared runs' },
  { icon: <Workflow className="h-4 w-4" />, title: 'Orchestration', body: 'Step Functions Standard: Map fan-out, task-token checkpoints, retries, failure handler' },
  { icon: <Bot className="h-4 w-4" />, title: 'Agents', body: 'LangGraph agents on Lambda with typed Pydantic hand-offs and per-agent call limits' },
  { icon: <Bot className="h-4 w-4" />, title: 'Models', body: 'Amazon Bedrock: Nova Pro, Nova Lite (APAC inference profiles), Titan Text Embeddings V2' },
  { icon: <ShieldCheck className="h-4 w-4" />, title: 'Safety', body: 'Bedrock Guardrails: prompt-attack filter on input, contextual grounding on claims' },
  { icon: <Database className="h-4 w-4" />, title: 'Data', body: 'S3 for PDFs, agent messages and exports; DynamoDB for runs, traces and quotas' },
  { icon: <FileText className="h-4 w-4" />, title: 'Operations', body: 'CloudWatch dashboard and alarm, X-Ray, per-run token budget, daily run cap, live switch in SSM' },
  { icon: <GitBranch className="h-4 w-4" />, title: 'Delivery', body: 'AWS CDK (Python) for all infrastructure; GitHub Actions runs lint, offline tests and synth' },
]

interface StepStats {
  model: number
  tools: number
  tokens: number
  cost: number
  ms: number
  instances: number
}

function stepStats(trace: TraceEvent[]): Record<string, StepStats> {
  const by: Record<string, StepStats & { names: Set<string> }> = {}
  for (const e of trace) {
    const id = e.step.split('-')[0]
    const s = (by[id] ??= { model: 0, tools: 0, tokens: 0, cost: 0, ms: 0, instances: 0, names: new Set() })
    s.names.add(e.step)
    if (e.kind === 'model_call') {
      s.model += 1
      s.tokens += e.tokens_in + e.tokens_out
      s.cost += e.cost_usd
    } else if (e.kind === 'tool_call') s.tools += 1
    else if (e.kind === 'agent_end') s.ms += e.latency_ms
  }
  return Object.fromEntries(Object.entries(by).map(([k, v]) => [k, { ...v, instances: v.names.size }]))
}

type State = 'done' | 'active' | 'waiting' | 'pending' | 'failed'

function StateIcon({ state, human }: { state: State; human: boolean }) {
  const ring = {
    done: 'bg-brand-600 text-white ring-brand-600',
    active: 'bg-white text-brand-700 ring-brand-500',
    waiting: 'bg-amber-50 text-amber-700 ring-amber-500',
    pending: 'bg-white text-slate-400 ring-slate-200',
    failed: 'bg-rose-50 text-rose-700 ring-rose-500',
  }[state]
  return (
    <span className={cx('flex h-8 w-8 flex-none items-center justify-center rounded-full ring-2', ring)}>
      {state === 'done' ? (
        <Check className="h-4 w-4" />
      ) : state === 'active' ? (
        <Loader2 className="h-4 w-4 animate-spin" />
      ) : human ? (
        <UserRound className="h-4 w-4" />
      ) : (
        <Workflow className="h-4 w-4" />
      )}
    </span>
  )
}

/** The system as built: every Step Functions state with what it runs, lit up by this run's progress and trace. */
export function ArchitectureTab({ run, trace }: { run: Run; trace: TraceEvent[] }) {
  const current = currentIndex(run)
  const failed = run.status === 'failed'
  const stats = stepStats(trace)
  const rounds = run.rewrite_rounds ?? 0

  return (
    <div className="grid gap-5 lg:grid-cols-3">
      <div className="space-y-3 lg:col-span-2">
        <Card className="p-4 text-sm text-slate-600">
          <span className="font-medium text-slate-900">Request path: </span>
          Browser → CloudFront → API Gateway (Cognito JWT) → API Lambda → PDF uploaded to S3 by presigned URL → Step
          Functions execution starts. Each state below is its own Lambda; agents hand off typed messages through S3.
        </Card>
        <ol className="space-y-3">
          {STEPS.map((step, index) => {
            const info = INFO[step.id]
            const human = 'human' in step
            const state: State =
              failed && index === current
                ? 'failed'
                : index < current
                  ? 'done'
                  : index === current && run.status !== 'complete'
                    ? human
                      ? 'waiting'
                      : 'active'
                    : 'pending'
            const s = stats[step.id]
            return (
              <li key={step.id}>
                <Card
                  className={cx(
                    'flex gap-3 p-4',
                    state === 'active' && 'border-brand-400 ring-2 ring-brand-100',
                    state === 'waiting' && 'border-amber-300 ring-2 ring-amber-100',
                    state === 'failed' && 'border-rose-300',
                  )}
                >
                  <StateIcon state={state} human={human} />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                      <span className="font-semibold text-slate-900">{step.label}</span>
                      {info.agent && <Chip className="bg-brand-50 text-brand-700 ring-brand-600/20">{info.agent}</Chip>}
                      {human && <Chip className="bg-amber-50 text-amber-700 ring-amber-600/20">Human in the loop</Chip>}
                      <span className="font-mono text-[11px] text-slate-400">{info.lambda}</span>
                    </div>
                    <p className="mt-1 text-sm text-slate-600">{info.what}</p>
                    {(info.models || info.tools) && (
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {info.models?.map((m) => (
                          <Chip key={m} className="bg-violet-50 text-violet-700 ring-violet-600/20">{m}</Chip>
                        ))}
                        {info.tools?.map((t) => (
                          <Chip key={t} className="bg-sky-50 font-mono text-sky-700 ring-sky-600/20">{t}</Chip>
                        ))}
                      </div>
                    )}
                    {s && s.model + s.tools > 0 && (
                      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500 tabular">
                        {s.instances > 1 && <span>{s.instances} parallel or repeated instances</span>}
                        <span>{s.model} model calls</span>
                        <span>{s.tools} tool calls</span>
                        <span>{s.tokens.toLocaleString()} tokens</span>
                        <span>{usd(s.cost)}</span>
                        <span>{(s.ms / 1000).toFixed(1)}s agent time</span>
                      </div>
                    )}
                    {step.id === 'verify' && rounds > 0 && (
                      <div className="mt-2 inline-flex items-center gap-1 text-xs text-amber-700">
                        <RotateCcw className="h-3.5 w-3.5" /> {rounds} rewrite round{rounds === 1 ? '' : 's'} back to the
                        Proposal Writer
                      </div>
                    )}
                  </div>
                </Card>
              </li>
            )
          })}
        </ol>
      </div>

      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-slate-900">Platform</h3>
        {PLATFORM.map((p) => (
          <Card key={p.title} className="flex gap-3 p-4">
            <span className="mt-0.5 text-brand-600">{p.icon}</span>
            <div>
              <div className="text-sm font-medium text-slate-900">{p.title}</div>
              <div className="mt-0.5 text-sm text-slate-600">{p.body}</div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  )
}
