import { useEffect, useState } from 'react'
import { publicApi } from '../api'
import { Card, Empty, Spinner } from '../components/ui'
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
        <h1 className="text-xl font-semibold text-slate-900">TenderLens demo</h1>
        <p className="mt-1 max-w-3xl text-sm text-slate-500">
          Five AI agents on AWS read a public RFP, extract every requirement, check each one against a bidder's
          capability library, draft a cited response, verify every claim and recommend whether to bid, with two human
          checkpoints. These are completed runs, read-only. Open one and look at the Architecture, Agent trace and
          Quality & controls tabs for how it works.
        </p>
      </div>
      <Card className="p-4 text-sm text-slate-600">
        The bidder, Cobalt Harbor IT Services, is fictional. The RFP is a real public solicitation.
      </Card>
      {error && <p className="text-sm text-rose-600">{error}</p>}
      {runs === null ? (
        <Spinner label="Loading runs" />
      ) : runs.length === 0 ? (
        <Empty>No demo runs are shared yet.</Empty>
      ) : (
        <RunTable runs={runs} base="/demo/runs" />
      )}
    </div>
  )
}
