import { FileText, X } from 'lucide-react'
import type { Evidence } from '../types'

/** Side panel showing the exact passage behind a citation. */
export function EvidencePanel({ evidence, onClose }: { evidence: Evidence | null; onClose: () => void }) {
  if (!evidence) return null
  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-slate-900/20" onClick={onClose}>
      <aside
        className="h-full w-full max-w-md overflow-y-auto bg-white p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Evidence {evidence.id}</div>
            <h3 className="mt-1 flex items-center gap-2 text-base font-semibold text-slate-900">
              <FileText className="h-4 w-4 text-brand-600" />
              {evidence.doc_title}
            </h3>
            <div className="mt-0.5 text-sm text-slate-500">{evidence.section}</div>
          </div>
          <button onClick={onClose} className="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="mt-5 whitespace-pre-wrap rounded-lg bg-slate-50 p-4 text-sm leading-relaxed text-slate-700">
          {evidence.text}
        </div>
        <p className="mt-4 text-xs text-slate-400">
          From the bidder's capability library. Cobalt Harbor IT Services is a fictional company.
        </p>
      </aside>
    </div>
  )
}
