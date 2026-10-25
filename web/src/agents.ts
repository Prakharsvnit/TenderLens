/** The agent team, described once for the landing page, the team bar and the activity feed. */
export type AgentId = 'rfp_analyst' | 'compliance_analyst' | 'proposal_writer' | 'claim_verifier' | 'bid_strategist'

export interface AgentInfo {
  id: AgentId
  name: string
  job: string
  input: string
  output: string
  model: string
  tools: string[]
  /** Workflow step ids this agent works in (trace steps start with these). */
  steps: string[]
  color: string
  ring: string
  text: string
}

export const AGENTS: AgentInfo[] = [
  {
    id: 'rfp_analyst',
    name: 'RFP Analyst',
    job: 'Reads every page and lists each requirement as a verbatim quote, with category and pass/fail flag.',
    input: 'RFP PDF',
    output: 'Requirements + scored criteria',
    model: 'Nova Pro, Nova Lite',
    tools: ['get_section'],
    steps: ['extract'],
    color: 'bg-brand-500',
    ring: 'ring-brand-500',
    text: 'text-brand-700',
  },
  {
    id: 'compliance_analyst',
    name: 'Compliance Analyst',
    job: 'Searches the company’s evidence for each requirement and rules met, partial or not met, with citations.',
    input: 'Confirmed requirements',
    output: 'Compliance matrix + gaps',
    model: 'Nova Pro, Titan Embeddings',
    tools: ['search_evidence', 'get_passage'],
    steps: ['assess'],
    color: 'bg-sky-500',
    ring: 'ring-sky-500',
    text: 'text-sky-700',
  },
  {
    id: 'proposal_writer',
    name: 'Proposal Writer',
    job: 'Drafts the response as claims, each tied to a requirement and the evidence behind it.',
    input: 'Matrix + evidence',
    output: 'Cited draft response',
    model: 'Nova Pro',
    tools: ['get_evidence'],
    steps: ['draft'],
    color: 'bg-violet-500',
    ring: 'ring-violet-500',
    text: 'text-violet-700',
  },
  {
    id: 'claim_verifier',
    name: 'Claim Verifier',
    job: 'Scores every claim against its evidence and sends unsupported ones back to the Writer.',
    input: 'Draft claims',
    output: 'Verdict per claim',
    model: 'Nova Lite + Guardrails grounding',
    tools: ['check_grounding'],
    steps: ['verify'],
    color: 'bg-emerald-500',
    ring: 'ring-emerald-500',
    text: 'text-emerald-700',
  },
  {
    id: 'bid_strategist',
    name: 'Bid Strategist',
    job: 'Applies knock-out rules and the RFP’s scoring, then recommends bid, bid with conditions or no bid.',
    input: 'Gaps + bid policy',
    output: 'Recommendation + what-ifs',
    model: 'Nova Pro',
    tools: ['list_gaps', 'get_bid_policy', 'compute_score'],
    steps: ['decide'],
    color: 'bg-amber-500',
    ring: 'ring-amber-500',
    text: 'text-amber-700',
  },
]

export const AGENT_BY_ID = Object.fromEntries(AGENTS.map((a) => [a.id, a])) as Record<AgentId, AgentInfo>

export function agentName(id: string): string {
  return id === 'guardrails' ? 'Guardrails' : (AGENT_BY_ID[id as AgentId]?.name ?? id)
}
