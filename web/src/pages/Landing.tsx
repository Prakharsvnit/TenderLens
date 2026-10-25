import {
  ArrowRight,
  BadgeCheck,
  Clock,
  Coins,
  FileSearch,
  Gauge,
  Layers,
  Lock,
  PlayCircle,
  ShieldCheck,
  ShieldAlert,
  UserRound,
  Workflow,
} from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { AGENTS } from '../agents'
import { publicApi } from '../api'
import { REPO_URL } from '../components/layout'
import { Card, cx, duration, pct, usd } from '../components/ui'
import type { Run } from '../types'

/** YouTube id of the unlisted demo video; the video section stays hidden until it is set. */
const VIDEO_ID = ''

const PROBLEMS = [
  { icon: <Clock className="h-5 w-5" />, title: 'Reading takes days', body: 'A 26-page RFP hides 100+ obligations across scope, legal terms and forms.' },
  { icon: <ShieldAlert className="h-5 w-5" />, title: 'One miss disqualifies', body: 'Skip a mandatory walkthrough, certification or insurance minimum and the bid is out.' },
  { icon: <FileSearch className="h-5 w-5" />, title: 'Claims lack proof', body: 'Drafts promise more than the company can evidence.' },
]

const PRODUCTION: { icon: ReactNode; title: string; body: string }[] = [
  { icon: <Workflow className="h-4 w-4" />, title: 'Orchestrated', body: 'Step Functions runs nine states with retries, parallel fan-out and a failure handler.' },
  { icon: <UserRound className="h-4 w-4" />, title: 'Human-approved', body: 'Two checkpoints pause the workflow. Every human decision is audit-logged.' },
  { icon: <ShieldCheck className="h-4 w-4" />, title: 'Guarded', body: 'Bedrock Guardrails screens input and grounds claims. Quotes and citations are checked in code.' },
  { icon: <Gauge className="h-4 w-4" />, title: 'Cost-capped', body: 'Per-run token budget, per-agent call limits, a daily run cap and a live switch.' },
  { icon: <BadgeCheck className="h-4 w-4" />, title: 'Measured', body: 'Every call traced. Runs scored against a hand-labelled gold set, in the app.' },
  { icon: <Lock className="h-4 w-4" />, title: 'Secured', body: 'Cognito sign-in, encrypted private buckets, scoped IAM roles, strict security headers.' },
  { icon: <Coins className="h-4 w-4" />, title: 'Serverless', body: 'Lambda, S3 and on-demand DynamoDB: nothing runs, or bills, between RFPs.' },
  { icon: <Layers className="h-4 w-4" />, title: 'Reproducible', body: 'All infrastructure in AWS CDK. CI runs lint, offline tests and a CDK synth.' },
]

const STACK = [
  'Amazon Bedrock · Nova Pro / Lite',
  'Titan Text Embeddings V2',
  'Bedrock Guardrails',
  'Step Functions',
  'Lambda (Python 3.12)',
  'LangGraph',
  'API Gateway + Cognito',
  'S3 + DynamoDB',
  'CloudFront',
  'CloudWatch + X-Ray',
  'AWS CDK',
  'React + TypeScript',
]

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div>
      <div className="text-2xl font-semibold tabular text-slate-900 sm:text-3xl">{value}</div>
      <div className="mt-1 text-sm text-slate-500">{label}</div>
    </div>
  )
}

function Heading({ eyebrow, title, children }: { eyebrow: string; title: string; children?: ReactNode }) {
  return (
    <div className="max-w-2xl">
      <p className="text-sm font-semibold text-brand-600">{eyebrow}</p>
      <h2 className="mt-1 text-2xl font-semibold text-slate-900">{title}</h2>
      {children && <p className="mt-2 text-slate-600">{children}</p>}
    </div>
  )
}

/** The interactive team: pick an agent to see its job, input, output, model and tools. */
function AgentTeam() {
  const [active, setActive] = useState(0)
  const agent = AGENTS[active]
  return (
    <div className="mt-6">
      <ol className="grid grid-cols-2 gap-2 sm:grid-cols-5">
        {AGENTS.map((a, i) => (
          <li key={a.id}>
            <button
              onClick={() => setActive(i)}
              aria-pressed={i === active}
              className={cx(
                'flex w-full items-center gap-2 rounded-xl border bg-white p-3 text-left text-sm font-medium transition',
                i === active ? 'border-transparent ring-2 ' + a.ring : 'border-slate-200 text-slate-600 hover:border-slate-300',
              )}
            >
              <span className={cx('flex h-6 w-6 flex-none items-center justify-center rounded-full text-xs text-white', a.color)}>
                {i + 1}
              </span>
              <span className={i === active ? 'text-slate-900' : undefined}>{a.name}</span>
            </button>
          </li>
        ))}
      </ol>
      <Card className="mt-3 p-5">
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="sm:col-span-2">
            <div className={cx('text-sm font-semibold', agent.text)}>{agent.name}</div>
            <p className="mt-1 text-slate-700">{agent.job}</p>
            <p className="mt-3 text-sm text-slate-500">
              {agent.input} <ArrowRight className="inline h-3.5 w-3.5" /> <span className="text-slate-700">{agent.output}</span>
            </p>
          </div>
          <dl className="space-y-2 text-sm">
            <div>
              <dt className="text-slate-500">Model</dt>
              <dd className="text-slate-800">{agent.model}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Tools</dt>
              <dd className="font-mono text-xs text-slate-800">{agent.tools.join(', ')}</dd>
            </div>
          </dl>
        </div>
        <div className="mt-4 flex items-center justify-between border-t border-slate-100 pt-3 text-sm">
          <span className="text-slate-500">
            {active === 0 && 'Then you confirm the requirements.'}
            {active === 4 && 'Then you approve or override the decision.'}
            {active > 0 && active < 4 && 'Hands its output to the next agent.'}
          </span>
          <button
            onClick={() => setActive((active + 1) % AGENTS.length)}
            className="inline-flex items-center gap-1 font-medium text-brand-700 hover:underline"
          >
            {active === AGENTS.length - 1 ? 'Start over' : 'Next agent'} <ArrowRight className="h-4 w-4" />
          </button>
        </div>
      </Card>
    </div>
  )
}

export function LandingPage() {
  const [run, setRun] = useState<Run | null>(null)

  useEffect(() => {
    publicApi
      .runs()
      .then((runs) => setRun(runs.find((r) => r.status === 'complete' && r.kpis) ?? null))
      .catch(() => setRun(null))
  }, [])

  const k = run?.kpis
  const runLink = run ? `/demo/runs/${run.run_id}` : '/demo'

  return (
    <div className="space-y-20 pb-10">
      <section className="pt-8 sm:pt-14">
        <p className="text-sm font-semibold text-brand-600">Agentic AI for public tenders</p>
        <h1 className="mt-2 max-w-3xl text-4xl font-semibold tracking-tight text-slate-900 sm:text-5xl">
          From RFP to a cited bid response in minutes.
        </h1>
        <p className="mt-4 max-w-2xl text-lg text-slate-600">
          Five AI agents read the RFP, check every requirement against your evidence, draft a cited response and
          recommend whether to bid. You approve each decision.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link to={runLink} className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2.5 font-medium text-white hover:bg-brand-700">
            See a real run <ArrowRight className="h-4 w-4" />
          </Link>
          {VIDEO_ID && (
            <a href="#video" className="inline-flex items-center gap-2 rounded-lg px-4 py-2.5 font-medium text-slate-700 ring-1 ring-slate-300 hover:bg-white">
              <PlayCircle className="h-4 w-4" /> Watch the demo
            </a>
          )}
          <Link to="/app" className="inline-flex items-center gap-2 rounded-lg px-4 py-2.5 font-medium text-slate-700 ring-1 ring-slate-300 hover:bg-white">
            Open app
          </Link>
        </div>

        {k && run && (
          <Card className="mt-10 p-6">
            <div className="grid grid-cols-2 gap-6 lg:grid-cols-4">
              <Stat value={`${run.requirement_count ?? '—'}`} label={`requirements found in a ${run.pages ?? ''}-page RFP`} />
              <Stat value={duration(k.time_to_first_draft_s)} label="to a verified first draft" />
              <Stat value={pct(k.evidence_backed_claim_rate)} label="of claims backed by evidence" />
              <Stat value={usd(k.cost_usd)} label="model cost for the run" />
            </div>
            <p className="mt-4 text-xs text-slate-500">
              Measured on a real run: {run.buyer ?? 'a public RFP'}, against a fictional bidder.{' '}
              <Link to={runLink} className="text-brand-700 hover:underline">Open it</Link>
            </p>
          </Card>
        )}
      </section>

      <section>
        <Heading eyebrow="The problem" title="Answering an RFP is slow and risky." />
        <div className="mt-6 grid gap-4 sm:grid-cols-3">
          {PROBLEMS.map((p) => (
            <Card key={p.title} className="p-5">
              <span className="text-rose-600">{p.icon}</span>
              <h3 className="mt-2 font-semibold text-slate-900">{p.title}</h3>
              <p className="mt-1 text-sm text-slate-600">{p.body}</p>
            </Card>
          ))}
        </div>
      </section>

      <section>
        <Heading eyebrow="The solution" title="An agent team that does the reading, checking and drafting.">
          Each agent has one job, its own tools and a typed hand-off to the next. Pick one.
        </Heading>
        <AgentTeam />
      </section>

      <section>
        <Heading eyebrow="What you get" title="Faster, safer bid decisions." />
        <div className="mt-6 grid gap-4 sm:grid-cols-3">
          <Card className="p-5">
            <Clock className="h-5 w-5 text-brand-600" />
            <h3 className="mt-2 font-semibold text-slate-900">Time</h3>
            <p className="mt-1 text-sm text-slate-600">
              A first draft and compliance matrix {k ? `in ${duration(k.time_to_first_draft_s)}` : 'in minutes'}. People
              review instead of read.
            </p>
          </Card>
          <Card className="p-5">
            <Coins className="h-5 w-5 text-brand-600" />
            <h3 className="mt-2 font-semibold text-slate-900">Money</h3>
            <p className="mt-1 text-sm text-slate-600">
              {k ? `${usd(k.cost_usd)} in model cost per RFP` : 'Cents per RFP in model cost'}, and no servers to pay for
              between bids. No-bid early on tenders you can’t win.
            </p>
          </Card>
          <Card className="p-5">
            <ShieldCheck className="h-5 w-5 text-brand-600" />
            <h3 className="mt-2 font-semibold text-slate-900">Risk</h3>
            <p className="mt-1 text-sm text-slate-600">
              Every pass/fail requirement flagged. Every claim cited and verified before it reaches the draft.
            </p>
          </Card>
        </div>
      </section>

      {VIDEO_ID && (
        <section id="video">
          <Heading eyebrow="Demo" title="Watch a full run." />
          <div className="mt-6 aspect-video overflow-hidden rounded-xl border border-slate-200 bg-black">
            <iframe
              className="h-full w-full"
              src={`https://www.youtube-nocookie.com/embed/${VIDEO_ID}?rel=0`}
              title="TenderLens demo"
              allow="encrypted-media; picture-in-picture"
              allowFullScreen
            />
          </div>
        </section>
      )}

      <section>
        <Heading eyebrow="How it is built" title="Production architecture on AWS." />
        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {PRODUCTION.map((p) => (
            <Card key={p.title} className="p-4">
              <div className="flex items-center gap-2 font-semibold text-slate-900">
                <span className="text-brand-600">{p.icon}</span>
                {p.title}
              </div>
              <p className="mt-1 text-sm text-slate-600">{p.body}</p>
            </Card>
          ))}
        </div>
        <div className="mt-6 flex flex-wrap gap-2">
          {STACK.map((s) => (
            <span key={s} className="rounded-full bg-white px-3 py-1 text-xs font-medium text-slate-700 ring-1 ring-slate-200">
              {s}
            </span>
          ))}
        </div>
      </section>

      <section>
        <Card className="flex flex-col items-start justify-between gap-4 p-6 sm:flex-row sm:items-center">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">See every step of a real run.</h2>
            <p className="mt-1 text-sm text-slate-600">Agents at work, their reasoning loops, the checks and the result.</p>
          </div>
          <div className="flex gap-3">
            <Link to={runLink} className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2.5 font-medium text-white hover:bg-brand-700">
              Open the run <ArrowRight className="h-4 w-4" />
            </Link>
            <a href={REPO_URL} target="_blank" rel="noreferrer" className="inline-flex items-center rounded-lg px-4 py-2.5 font-medium text-slate-700 ring-1 ring-slate-300 hover:bg-white">
              Source code
            </a>
          </div>
        </Card>
      </section>
    </div>
  )
}
