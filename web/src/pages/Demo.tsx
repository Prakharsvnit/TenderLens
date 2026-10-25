import { useEffect, useState } from 'react'
import { publicApi } from '../api'
import { Empty, ErrorState, Skeleton } from '../components/ui'
import type { Run } from '../types'
import { RunTable } from './Runs'

/** The public demo: shared runs, read-only, no sign-in. */
export function DemoPage() {
  const [runs, setRuns] = useState<Run[] | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    publicApi
      .runs()
      .then(setRuns)
      .catch((e) => setError(e instanceof Error ? e.message : 'Could not load the demo runs'))
  }, [])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Demo runs</h1>
        <p className="mt-1 text-sm text-slate-500">
          Completed runs on real public RFPs, read-only. The bidder, Cobalt Harbor IT Services, is fictional.
        </p>
      </div>
      {error ? (
        <ErrorState title="Could not load the demo runs" message={error} onRetry={() => location.reload()} />
      ) : runs === null ? (
        <Skeleton rows={2} />
      ) : runs.length === 0 ? (
        <Empty>No demo runs are shared yet.</Empty>
      ) : (
        <RunTable runs={runs} base="/demo/runs" />
      )}
    </div>
  )
}
