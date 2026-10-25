export type Status = 'met' | 'partial' | 'not_met' | 'no_evidence'
export type DecisionKind = 'bid' | 'bid_with_conditions' | 'no_bid'
export type Category =
  | 'technical'
  | 'security_compliance'
  | 'staffing'
  | 'service_levels'
  | 'insurance_legal'
  | 'commercial'
  | 'submission'

export interface Kpis {
  time_to_first_draft_s: number
  requirement_coverage: number
  mandatory_coverage: number
  evidence_backed_claim_rate: number
  critical_requirements: number
  possible_misses: number
  cost_usd: number
  tokens: number
}

export interface Run {
  run_id: string
  owner?: string
  rfp_name?: string
  rfp_title?: string
  buyer?: string
  pages?: number
  status: string
  step?: string
  created_at: string
  started_at?: string
  requirement_count?: number
  critical_count?: number
  possible_misses?: number
  status_counts?: Record<Status, number>
  gap_count?: number
  claims?: number
  unsupported_claims?: number
  rewrite_rounds?: number
  assess_batches?: number
  decision?: DecisionKind
  final_decision?: DecisionKind
  score_pct?: number
  cost_usd?: number
  tokens_used?: number
  kpis?: Kpis
  error?: string
  shared?: boolean
  flagged_pages?: number[]
}

export interface Requirement {
  id: string
  section_id: string
  page: number
  quote: string
  summary: string
  obligation: 'mandatory' | 'desirable'
  category: Category
  critical: boolean
  criterion?: string | null
}

export interface Evidence {
  id: string
  doc_id: string
  doc_title: string
  section: string
  text: string
  score: number
}

export interface Assessment {
  requirement_id: string
  status: Status
  evidence_ids: string[]
  rationale: string
  confidence: number
}

export interface Gap {
  id: string
  requirement_id: string
  severity: 'critical' | 'high' | 'medium' | 'low'
  knock_out: boolean
  description: string
  mitigation?: { type: string; description: string } | null
}

export interface Claim {
  id: string
  section_id: string
  text: string
  requirement_ids: string[]
  evidence_ids: string[]
}

export interface DraftSection {
  id: string
  title: string
  rfp_reference: string
  claims: Claim[]
  sme_placeholders: string[]
}

export interface ClaimVerdict {
  claim_id: string
  verdict: 'supported' | 'unsupported' | 'contradicted'
  grounding_score: number
  note: string
}

export interface ScoreLine {
  criterion: string
  points: number
  status: Status
  earned: number
}

export interface KnockOut {
  rule_id: string
  requirement_id: string | null
  description: string
  outcome: 'met' | 'fixable' | 'fatal'
  evidence_ids: string[]
  fix: string
}

export interface BidDecision {
  decision: DecisionKind
  score: number
  max_score: number
  score_pct: number
  knock_outs: KnockOut[]
  score_lines: ScoreLine[]
  conditions: string[]
  what_ifs: { change: string; score_pct: number; decision: DecisionKind }[]
  rationale: string
}

export interface RunView {
  run: Run
  RequirementSet?: {
    rfp: { title: string; buyer: { name: string }; page_count: number; evaluation_criteria: { name: string; points: number }[] }
    requirements: Requirement[]
    possible_misses: string[]
  }
  AssessmentBatch?: { assessments: Assessment[]; evidence: Evidence[]; gaps: Gap[] }
  DraftMessage?: { sections: DraftSection[]; round: number }
  ClaimVerdicts?: { verdicts: ClaimVerdict[]; round: number }
  BidRecommendation?: { decision: BidDecision }
  approval?: { approver: string; accepted: boolean; final_decision: DecisionKind; reason: string; at: string }
  audit?: AuditEvent[]
  eval?: EvalReport
  limits?: { run_token_budget: number; grounding_threshold: number }
}

export interface TraceEvent {
  run_id: string
  step: string
  agent: string
  kind: string
  name: string
  tokens_in: number
  tokens_out: number
  cost_usd: number
  latency_ms: number
  detail: string
  args?: string
  at: string
}

export interface EvalReport {
  run_id: string
  metrics: Record<string, number>
  targets: Record<string, number>
  gold_size: number
  decision: DecisionKind | null
  expected_decision: DecisionKind | null
  score_pct: number | null
  missed_critical: string[]
  missed: { gold: string; page: number; quote: string }[]
  not_in_gold: { id: string; page: number; quote: string }[]
  wrong_status: { gold: string; got: Status | null; expected: Status[] }[]
}

export interface AuditEvent {
  at: string
  actor: string
  action: string
  detail: Record<string, unknown>
}

export interface ApiConfig {
  live_runs: boolean
  live_until: string | null
  daily_cap: number
  user: string
  viewer?: boolean
}
