import { Loader2 } from 'lucide-react'
import type { ButtonHTMLAttributes, ReactNode } from 'react'
import type { Category, DecisionKind, Status } from '../types'

export function cx(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(' ')
}

export const STATUS_LABEL: Record<Status, string> = {
  met: 'Met',
  partial: 'Partial',
  not_met: 'Not met',
  no_evidence: 'No evidence',
}

const STATUS_STYLE: Record<Status, string> = {
  met: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
  partial: 'bg-amber-50 text-amber-700 ring-amber-600/20',
  not_met: 'bg-rose-50 text-rose-700 ring-rose-600/20',
  no_evidence: 'bg-slate-100 text-slate-600 ring-slate-500/20',
}

export const DECISION_LABEL: Record<DecisionKind, string> = {
  bid: 'Bid',
  bid_with_conditions: 'Bid with conditions',
  no_bid: 'No-bid',
}

const DECISION_STYLE: Record<DecisionKind, string> = {
  bid: 'bg-emerald-600 text-white',
  bid_with_conditions: 'bg-amber-500 text-white',
  no_bid: 'bg-rose-600 text-white',
}

export const CATEGORY_LABEL: Record<Category, string> = {
  technical: 'Technical services',
  security_compliance: 'Security & compliance',
  staffing: 'Staffing',
  service_levels: 'Service levels',
  insurance_legal: 'Insurance & legal',
  commercial: 'Commercial',
  submission: 'Submission',
}

export function Chip({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span
      className={cx(
        'inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset whitespace-nowrap',
        className ?? 'bg-slate-100 text-slate-700 ring-slate-500/20',
      )}
    >
      {children}
    </span>
  )
}

export function StatusChip({ status }: { status: Status }) {
  return <Chip className={STATUS_STYLE[status]}>{STATUS_LABEL[status]}</Chip>
}

export function DecisionBadge({ decision, large }: { decision: DecisionKind; large?: boolean }) {
  return (
    <span
      className={cx(
        'inline-flex items-center rounded-lg font-semibold',
        large ? 'px-4 py-2 text-lg' : 'px-2.5 py-1 text-xs',
        DECISION_STYLE[decision],
      )}
    >
      {DECISION_LABEL[decision]}
    </span>
  )
}

export function RunStatusChip({ status }: { status: string }) {
  const map: Record<string, [string, string]> = {
    uploading: ['Uploading', 'bg-slate-100 text-slate-600 ring-slate-500/20'],
    queued: ['Queued', 'bg-slate-100 text-slate-600 ring-slate-500/20'],
    running: ['Running', 'bg-brand-50 text-brand-700 ring-brand-600/20'],
    awaiting_confirmation: ['Needs confirmation', 'bg-amber-50 text-amber-700 ring-amber-600/20'],
    awaiting_approval: ['Needs approval', 'bg-amber-50 text-amber-700 ring-amber-600/20'],
    complete: ['Complete', 'bg-emerald-50 text-emerald-700 ring-emerald-600/20'],
    failed: ['Failed', 'bg-rose-50 text-rose-700 ring-rose-600/20'],
  }
  const [label, style] = map[status] ?? [status, undefined]
  return <Chip className={style}>{label}</Chip>
}

export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cx('rounded-xl border border-slate-200 bg-white shadow-sm', className)}>{children}</div>
}

export function Button({
  variant = 'primary',
  loading,
  children,
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'danger'; loading?: boolean }) {
  const styles = {
    primary: 'bg-brand-600 text-white hover:bg-brand-700 disabled:bg-brand-600/50',
    secondary: 'bg-white text-slate-700 ring-1 ring-inset ring-slate-300 hover:bg-slate-50 disabled:opacity-50',
    danger: 'bg-rose-600 text-white hover:bg-rose-700 disabled:opacity-50',
  }
  return (
    <button
      {...props}
      disabled={props.disabled || loading}
      className={cx(
        'inline-flex items-center justify-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition-colors',
        styles[variant],
        className,
      )}
    >
      {loading && <Loader2 className="h-4 w-4 animate-spin" />}
      {children}
    </button>
  )
}

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: ReactNode }) {
  return (
    <Card className="p-4">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-slate-900 tabular">{value}</div>
      {hint && <div className="mt-1 text-xs text-slate-500">{hint}</div>}
    </Card>
  )
}

export function Tabs<T extends string>({
  tabs,
  active,
  onChange,
}: {
  tabs: { id: T; label: string; count?: number }[]
  active: T
  onChange: (id: T) => void
}) {
  return (
    <div className="flex gap-1 overflow-x-auto overflow-y-hidden border-b border-slate-200">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className={cx(
            '-mb-px whitespace-nowrap border-b-2 px-3 py-2.5 text-sm font-medium transition-colors',
            tab.id === active
              ? 'border-brand-600 text-brand-700'
              : 'border-transparent text-slate-500 hover:text-slate-800',
          )}
        >
          {tab.label}
          {tab.count !== undefined && (
            <span className="ml-1.5 rounded-full bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600">{tab.count}</span>
          )}
        </button>
      ))}
    </div>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="rounded-xl border border-dashed border-slate-300 p-10 text-center text-sm text-slate-500">{children}</div>
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-slate-500">
      <Loader2 className="h-4 w-4 animate-spin" />
      {label}
    </div>
  )
}

export const pct = (value: number | undefined, digits = 0) =>
  value === undefined || value === null ? '—' : `${(value * 100).toFixed(digits)}%`

export const usd = (value: number | undefined) =>
  value === undefined ? '—' : value < 0.01 ? `$${value.toFixed(4)}` : `$${value.toFixed(2)}`

export function duration(seconds: number | undefined): string {
  if (seconds === undefined) return '—'
  if (seconds < 60) return `${Math.round(seconds)}s`
  return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`
}

/** Grey placeholder blocks shown while data loads. */
export function Skeleton({ rows = 3, className }: { rows?: number; className?: string }) {
  return (
    <div className={cx('animate-pulse space-y-3', className)} aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="h-16 rounded-xl bg-slate-200/70" />
      ))}
    </div>
  )
}

/** A readable failure with a way to try again. */
export function ErrorState({ title, message, onRetry }: { title: string; message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-6 text-sm">
      <div className="font-semibold text-rose-800">{title}</div>
      <p className="mt-1 text-rose-700">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="mt-3 rounded-lg bg-white px-3 py-1.5 font-medium text-rose-700 ring-1 ring-rose-300 hover:bg-rose-100">
          Try again
        </button>
      )}
    </div>
  )
}
