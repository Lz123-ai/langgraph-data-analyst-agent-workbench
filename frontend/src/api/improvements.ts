import type { ImprovementLogCreate, ImprovementLogEntry, ImprovementLogListResponse } from './types'
import { apiHeaders, apiUrl } from './client'

export async function listImprovementLogs(limit = 20): Promise<ImprovementLogListResponse> {
  const response = await fetch(apiUrl('/api/improvements', { limit }), { headers: apiHeaders() })
  if (!response.ok) {
    throw new Error(await readError(response))
  }
  return response.json()
}

export async function createImprovementLog(payload: ImprovementLogCreate): Promise<ImprovementLogEntry> {
  const response = await fetch(apiUrl('/api/improvements'), {
    method: 'POST',
    headers: apiHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(payload)
  })
  if (!response.ok) {
    throw new Error(await readError(response))
  }
  return response.json()
}

async function readError(response: Response): Promise<string> {
  try {
    const data = await response.json()
    return data.detail ?? response.statusText
  } catch {
    return response.statusText
  }
}
