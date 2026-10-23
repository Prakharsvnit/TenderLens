import { idToken } from './auth'
import { config } from './config'
import type { ApiConfig, DecisionKind, Run, RunView, TraceEvent } from './types'

export class ApiError extends Error {}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = await idToken()
  const response = await fetch(`${config().apiUrl}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token && !config().local ? { Authorization: token } : {}),
      ...(init.headers ?? {}),
    },
  })
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw new ApiError(body.message ?? `Request failed (${response.status})`)
  return body as T
}

export const api = {
  config: () => request<ApiConfig>('/config'),
  runs: () => request<{ runs: Run[] }>('/runs').then((r) => r.runs),
  run: (id: string) => request<RunView>(`/runs/${id}`),
  trace: (id: string) => request<{ events: TraceEvent[] }>(`/runs/${id}/trace`).then((r) => r.events),
  confirm: (id: string, edits: Record<string, unknown>[]) =>
    request(`/runs/${id}/confirm`, { method: 'POST', body: JSON.stringify({ edits }) }),
  approve: (id: string, body: { accepted: boolean; final_decision?: DecisionKind; reason?: string }) =>
    request(`/runs/${id}/approve`, { method: 'POST', body: JSON.stringify(body) }),
  exportUrl: (id: string, kind: 'matrix' | 'draft') =>
    request<{ url: string }>(`/runs/${id}/exports/${kind}`).then((r) => r.url),

  /** Creates a run, uploads the PDF straight to storage, then starts the workflow. */
  async startRun(file: File): Promise<string> {
    const created = await request<{ run_id: string; upload_url: string }>('/runs', {
      method: 'POST',
      body: JSON.stringify({ filename: file.name }),
    })
    const upload = await fetch(created.upload_url, {
      method: 'PUT',
      body: file,
      headers: { 'Content-Type': 'application/pdf' },
    })
    if (!upload.ok) throw new ApiError(`Upload failed (${upload.status})`)
    await request(`/runs/${created.run_id}/start`, { method: 'POST', body: '{}' })
    return created.run_id
  },
}
