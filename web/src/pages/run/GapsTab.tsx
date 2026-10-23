import { ShieldAlert } from 'lucide-react'
import { Card, Chip, Empty } from '../../components/ui'
import type { RunView } from '../../types'

const SEVERITY: Record<string, string> = {
  critical: 'bg-rose-50 text-rose-700 ring-rose-600/20',
  high: 'bg-orange-50 text-orange-700 ring-orange-600/20',
  medium: 'bg-amber-50 text-amber-700 ring-amber-600/20',
  low: 'bg-slate-100 text-slate-600 ring-slate-500/20',
}

export function GapsTab({ view }: { view: RunView }) {
  const gaps = view.AssessmentBatch?.gaps
  if (!gaps) return <Empty>Gaps appear once the requirements have been assessed.</Empty>
  if (gaps.length === 0) return <Empty>No gaps: the bidder's evidence covers every assessed requirement.</Empty>
  const quote = Object.fromEntries((view.RequirementSet?.requirements ?? []).map((r) => [r.id, r]))
  const order = ['critical', 'high', 'medium', 'low']
  const sorted = [...gaps].sort((a, b) => order.indexOf(a.severity) - order.indexOf(b.severity))

  return (
    <div className="grid gap-3 md:grid-cols-2">
      {sorted.map((g) => (
        <Card key={g.id} className="p-4">
          <div className="flex flex-wrap items-center gap-2">
            <Chip className={SEVERITY[g.severity]}>{g.severity}</Chip>
            {g.knock_out && (
              <Chip className="bg-rose-600 text-white ring-rose-600">
                <ShieldAlert className="h-3 w-3" /> Knock-out
              </Chip>
            )}
            <span className="font-mono text-xs text-slate-400">{g.requirement_id}</span>
            {quote[g.requirement_id] && <span className="text-xs text-slate-400">p.{quote[g.requirement_id].page}</span>}
          </div>
          <p className="mt-2 text-sm text-slate-800">{g.description}</p>
          {quote[g.requirement_id] && (
            <p className="mt-2 border-l-2 border-slate-200 pl-3 text-xs text-slate-500">{quote[g.requirement_id].quote}</p>
          )}
          {g.mitigation && (
            <div className="mt-3 rounded-lg bg-brand-50 px-3 py-2 text-sm text-brand-700">
              <span className="font-medium capitalize">{g.mitigation.type.replace(/_/g, ' ')}:</span> {g.mitigation.description}
            </div>
          )}
        </Card>
      ))}
    </div>
  )
}
