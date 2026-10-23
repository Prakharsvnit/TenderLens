import { CATEGORY_LABEL, Card, Chip, Empty } from '../../components/ui'
import type { Category, RunView } from '../../types'

type Edits = Record<string, Record<string, unknown>>

export function RequirementsTab({
  view,
  editable,
  edits,
  setEdits,
}: {
  view: RunView
  editable: boolean
  edits: Edits
  setEdits: (e: Edits) => void
}) {
  const set = view.RequirementSet
  if (!set) return <Empty>The RFP Analyst is still reading the RFP.</Empty>

  const value = <K extends string>(id: string, key: K, fallback: unknown) =>
    (edits[id]?.[key] ?? fallback) as never
  const change = (id: string, key: string, v: unknown) => setEdits({ ...edits, [id]: { ...edits[id], [key]: v } })

  return (
    <div className="space-y-5">
      <Card className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-3 py-3">ID</th>
              <th className="px-3 py-3">Page</th>
              <th className="px-3 py-3">Requirement (verbatim)</th>
              <th className="px-3 py-3">Category</th>
              <th className="px-3 py-3">Type</th>
              <th className="px-3 py-3">Pass/fail</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 align-top">
            {set.requirements.map((r) => (
              <tr key={r.id} className={edits[r.id] ? 'bg-amber-50/50' : undefined}>
                <td className="px-3 py-2.5 font-mono text-xs text-slate-500">{r.id}</td>
                <td className="px-3 py-2.5 tabular text-slate-500">{r.page}</td>
                <td className="max-w-xl px-3 py-2.5 text-slate-800">
                  {r.quote}
                  {r.criterion && <div className="mt-1 text-xs text-slate-500">Scored under: {r.criterion}</div>}
                </td>
                <td className="px-3 py-2.5">
                  {editable ? (
                    <select
                      value={value(r.id, 'category', r.category)}
                      onChange={(e) => change(r.id, 'category', e.target.value)}
                      className="rounded-md border-0 py-1 pl-2 pr-7 text-xs ring-1 ring-inset ring-slate-300"
                    >
                      {(Object.keys(CATEGORY_LABEL) as Category[]).map((c) => (
                        <option key={c} value={c}>{CATEGORY_LABEL[c]}</option>
                      ))}
                    </select>
                  ) : (
                    <Chip>{CATEGORY_LABEL[r.category]}</Chip>
                  )}
                </td>
                <td className="px-3 py-2.5 text-slate-600">{r.obligation === 'mandatory' ? 'Mandatory' : 'Desirable'}</td>
                <td className="px-3 py-2.5">
                  {editable ? (
                    <input type="checkbox" checked={value(r.id, 'critical', r.critical)}
                      onChange={(e) => change(r.id, 'critical', e.target.checked)} className="h-4 w-4 accent-brand-600" />
                  ) : r.critical ? (
                    <Chip className="bg-rose-50 text-rose-700 ring-rose-600/20">Pass/fail</Chip>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      {set.possible_misses.length > 0 && (
        <Card className="p-5">
          <h3 className="text-sm font-semibold text-slate-900">Possible misses from the shall/must scan</h3>
          <p className="mt-1 text-sm text-slate-500">
            Rule-based safety net: obligation sentences no extracted requirement covers. Review them at the checkpoint.
          </p>
          <ul className="mt-3 space-y-2 text-sm text-slate-700">
            {set.possible_misses.map((m, i) => (
              <li key={i} className="rounded-lg bg-slate-50 px-3 py-2">{m}</li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  )
}
