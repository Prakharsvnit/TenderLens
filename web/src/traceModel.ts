import type { TraceEvent } from './types'

/** One agent invocation: its model turns, tool calls and checks, as recorded in the trace. */
export interface Invocation {
  id: number
  step: string
  agent: string
  events: TraceEvent[]
  at: string
  seconds: number
}

export interface Turn {
  model: TraceEvent
  tools: TraceEvent[]
}

/**
 * Splits the trace into invocations. An agent writes its whole message history as one block when it finishes,
 * followed by its checks and an agent_end, so a block runs from the first event for a step/agent to its agent_end.
 */
export function invocations(trace: TraceEvent[]): Invocation[] {
  const out: Invocation[] = []
  const open = new Map<string, Invocation>()
  for (const e of trace) {
    if (e.kind === 'agent_start') continue
    const key = `${e.step}|${e.agent}`
    let inv = open.get(key)
    if (!inv) {
      inv = { id: out.length, step: e.step, agent: e.agent, events: [], at: e.at, seconds: 0 }
      out.push(inv)
      open.set(key, inv)
    }
    if (e.kind === 'agent_end') {
      inv.seconds = e.latency_ms / 1000
      inv.at = e.at
      open.delete(key)
    } else inv.events.push(e)
  }
  return out
}

/** Model turns with the tool calls each one asked for (the agent loop: think, act, observe). */
export function turns(inv: Invocation): Turn[] {
  const result: Turn[] = []
  for (const e of inv.events) {
    if (e.kind === 'model_call') result.push({ model: e, tools: [] })
    else if (e.kind === 'tool_call' && result.length) result[result.length - 1].tools.push(e)
  }
  return result
}

export const isAnswer = (e: TraceEvent) => e.detail.startsWith('Returning structured response')
export const isBlocked = (e: TraceEvent) => e.detail.startsWith('Tool call limit exceeded')

export interface Correction {
  key: string
  label: string
  examples: string[]
}

/** Everything the system caught and fixed on its own, grouped by kind. */
export function corrections(trace: TraceEvent[], rewriteRounds = 0): Correction[] {
  const groups: Record<string, Correction> = {}
  const add = (key: string, label: string, example: string) => {
    const g = (groups[key] ??= { key, label, examples: [] })
    g.examples.push(example)
  }
  const labels: Record<string, string> = {
    quote_rejected: 'Quotes rejected: not found in the PDF',
    citation_rejected: 'Citations dropped: evidence never retrieved',
    status_downgraded: 'Statuses downgraded: no valid evidence',
    missing_assessment: 'Requirements caught unassessed',
    verdict_overridden: 'Verdicts overridden: grounding too low',
    claim_dropped: 'Claims dropped after review',
    claim_to_sme: 'Claims routed to a subject expert',
  }
  for (const e of trace) {
    if (e.kind === 'validation' && labels[e.name]) add(e.name, labels[e.name], e.detail)
    else if (e.kind === 'validation' && e.name === 'schema' && e.detail.startsWith('no '))
      add('retry', 'Answers retried: wrong format', `${e.agent}: ${e.detail}`)
    else if (e.kind === 'tool_call' && isBlocked(e))
      add('blocked', 'Tool calls blocked: budget spent', `${e.agent} · ${e.step}: ${e.name}`)
    else if (e.kind === 'validation' && e.name === 'screened' && !e.detail.includes(' 0 flagged'))
      add('screened', 'Pages withheld by Guardrails', e.detail)
  }
  const list = Object.values(groups)
  if (rewriteRounds > 0)
    list.push({ key: 'rewrite', label: 'Draft rewrite rounds', examples: Array(rewriteRounds).fill('Unsupported claims sent back to the Writer') })
  return list.sort((a, b) => b.examples.length - a.examples.length)
}
