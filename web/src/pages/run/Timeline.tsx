import { Card, cx } from '../../components/ui'
import type { TraceEvent } from '../../types'

const AGENT_COLOR: Record<string, string> = {
  rfp_analyst: 'bg-brand-500',
  compliance_analyst: 'bg-sky-500',
  proposal_writer: 'bg-violet-500',
  claim_verifier: 'bg-emerald-500',
  bid_strategist: 'bg-amber-500',
}
const MAX_GAP_S = 8 // idle time longer than this (mostly human checkpoints) is drawn as a short break

interface Interval {
  step: string
  agent: string
  start: number
  end: number
}

/** Seconds on screen for a wall-clock time, with long idle gaps squeezed to MAX_GAP_S. */
function compressor(intervals: Interval[]) {
  const sorted = [...intervals].sort((a, b) => a.start - b.start)
  const busy: [number, number][] = []
  for (const i of sorted) {
    const last = busy[busy.length - 1]
    if (last && i.start <= last[1]) last[1] = Math.max(last[1], i.end)
    else busy.push([i.start, i.end])
  }
  const breaks: { at: number; waited: number }[] = []
  const offsets: number[] = [] // seconds removed before each busy period
  let removed = 0
  busy.forEach(([start], k) => {
    if (k > 0) {
      const gap = start - busy[k - 1][1]
      if (gap > MAX_GAP_S) {
        removed += gap - MAX_GAP_S
        breaks.push({ at: start - removed - MAX_GAP_S / 2, waited: gap })
      }
    }
    offsets.push(removed)
  })
  const t0 = busy[0]?.[0] ?? 0
  const map = (t: number) => {
    let k = busy.length - 1
    while (k > 0 && t < busy[k][0]) k--
    return t - offsets[k] - t0
  }
  const total = busy.length ? map(busy[busy.length - 1][1]) : 0
  return { map, total, breaks: breaks.map((b) => ({ ...b, at: b.at - t0 })) }
}

function lanes(items: Interval[]): Interval[][] {
  const out: Interval[][] = []
  for (const i of [...items].sort((a, b) => a.start - b.start)) {
    const lane = out.find((l) => l[l.length - 1].end <= i.start)
    if (lane) lane.push(i)
    else out.push([i])
  }
  return out
}

function human(seconds: number): string {
  if (seconds < 90) return `${Math.round(seconds)}s`
  if (seconds < 5400) return `${Math.round(seconds / 60)}m`
  return `${(seconds / 3600).toFixed(1)}h`
}

/** Every agent run on one time axis: parallel instances side by side, human waits shown as breaks. */
export function Timeline({ events }: { events: TraceEvent[] }) {
  const intervals: Interval[] = events
    .filter((e) => e.kind === 'agent_end' && e.latency_ms > 0)
    .map((e) => {
      const end = new Date(e.at).getTime() / 1000
      return { step: e.step, agent: e.agent, start: end - e.latency_ms / 1000, end }
    })
  if (intervals.length === 0) return null
  const { map, total, breaks } = compressor(intervals)
  const groups = new Map<string, Interval[]>()
  for (const i of [...intervals].sort((a, b) => a.start - b.start)) {
    const id = i.step.split('-')[0]
    groups.set(id, [...(groups.get(id) ?? []), i])
  }
  const x = (t: number) => `${(map(t) / total) * 100}%`

  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold text-slate-900">Timeline</h3>
        <span className="text-xs text-slate-500">
          Each bar is one agent run. Stacked bars ran in parallel. Gaps longer than {MAX_GAP_S}s are shortened and
          labelled.
        </span>
      </div>
      <div className="mt-4 space-y-2">
        {[...groups.entries()].map(([step, items]) => (
          <div key={step} className="flex items-start gap-3">
            <div className="w-16 flex-none pt-0.5 font-mono text-xs text-slate-500">{step}</div>
            <div className="relative flex-1 space-y-0.5">
              {lanes(items).map((lane, k) => (
                <div key={k} className="relative h-2.5">
                  {lane.map((i, n) => (
                    <div
                      key={n}
                      title={`${i.step} · ${i.agent.replace('_', ' ')} · ${human(i.end - i.start)}`}
                      className={cx('absolute h-full rounded-sm', AGENT_COLOR[i.agent] ?? 'bg-slate-400')}
                      style={{ left: x(i.start), width: `max(2px, calc(${x(i.end)} - ${x(i.start)}))` }}
                    />
                  ))}
                </div>
              ))}
            </div>
          </div>
        ))}
        <div className="relative ml-[4.75rem] h-4 border-t border-slate-200">
          {breaks.map((b, k) => (
            <span
              key={k}
              className="absolute -translate-x-1/2 whitespace-nowrap pt-0.5 text-[10px] text-amber-700"
              style={{ left: `${(b.at / total) * 100}%` }}
            >
              ⋯ {human(b.waited)} wait
            </span>
          ))}
        </div>
      </div>
      <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-500">
        {Object.entries(AGENT_COLOR).map(([agent, color]) => (
          <span key={agent} className="inline-flex items-center gap-1.5">
            <span className={cx('h-2.5 w-2.5 rounded-sm', color)} />
            {agent.replace('_', ' ')}
          </span>
        ))}
        <span className="ml-auto tabular">{human(total)} shown</span>
      </div>
    </Card>
  )
}
