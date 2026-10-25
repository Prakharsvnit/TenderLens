import type { Run } from '../types'

/** The workflow's Step Functions states in order, with the two human checkpoints marked. */
export const STEPS = [
  { id: 'parse', label: 'Parse & screen' },
  { id: 'extract', label: 'Extract' },
  { id: 'confirm', label: 'Confirm', human: true },
  { id: 'assess', label: 'Assess' },
  { id: 'draft', label: 'Draft' },
  { id: 'verify', label: 'Verify' },
  { id: 'decide', label: 'Decide' },
  { id: 'approve', label: 'Approve', human: true },
  { id: 'publish', label: 'Publish' },
] as const

export function currentIndex(run: Run): number {
  if (run.status === 'complete') return STEPS.length
  if (run.status === 'awaiting_confirmation') return 2
  if (run.status === 'awaiting_approval') return 7
  if (run.status === 'uploading' || run.status === 'queued') return 0
  const step = (run.step ?? 'parse').split('-')[0]
  const index = STEPS.findIndex((s) => s.id === step)
  return index < 0 ? 0 : index
}
