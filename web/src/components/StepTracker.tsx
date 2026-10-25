import { Check, Loader2, UserRound } from 'lucide-react'
import type { Run } from '../types'
import { currentIndex, STEPS } from './steps'
import { cx } from './ui'

/** The nine Step Functions states, with the two human checkpoints marked. */
export function StepTracker({ run }: { run: Run }) {
  const current = currentIndex(run)
  const failed = run.status === 'failed'
  return (
    <ol className="grid grid-cols-3 gap-2 sm:grid-cols-9">
      {STEPS.map((step, index) => {
        const done = index < current
        const active = index === current && !failed && run.status !== 'complete'
        const waiting = active && 'human' in step
        return (
          <li key={step.id} className="flex flex-col items-center gap-1.5 text-center">
            <span
              className={cx(
                'flex h-8 w-8 items-center justify-center rounded-full text-xs font-semibold ring-2',
                done && 'bg-brand-600 text-white ring-brand-600',
                active && !waiting && 'bg-white text-brand-700 ring-brand-500',
                waiting && 'bg-amber-50 text-amber-700 ring-amber-500',
                !done && !active && 'bg-white text-slate-400 ring-slate-200',
                failed && index === current && 'bg-rose-50 text-rose-700 ring-rose-500',
              )}
            >
              {done ? (
                <Check className="h-4 w-4" />
              ) : waiting ? (
                <UserRound className="h-4 w-4" />
              ) : active ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : 'human' in step ? (
                <UserRound className="h-4 w-4" />
              ) : (
                index + 1
              )}
            </span>
            <span className={cx('text-xs', done || active ? 'text-slate-800' : 'text-slate-400')}>{step.label}</span>
          </li>
        )
      })}
    </ol>
  )
}
