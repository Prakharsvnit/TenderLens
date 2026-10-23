export interface AppConfig {
  apiUrl: string
  local?: boolean
  region?: string
  userPoolId?: string
  userPoolClientId?: string
}

let cached: AppConfig | null = null

/** config.json is written at deploy time (API URL, Cognito ids); the dev copy points at the local server. */
export async function loadConfig(): Promise<AppConfig> {
  if (!cached) {
    const response = await fetch('/config.json', { cache: 'no-store' })
    cached = (await response.json()) as AppConfig
    cached.apiUrl = cached.apiUrl.replace(/\/$/, '')
  }
  return cached
}

export function config(): AppConfig {
  if (!cached) throw new Error('config not loaded')
  return cached
}
