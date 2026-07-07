import type { ImprovementLogCreate, ImprovementLogEntry, ImprovementLogListResponse } from './types'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

export async function listImprovementLogs(limit = 20): Promise<ImprovementLogListResponse> {
  const response = await fetch(`${API_BASE}/api/improvements?limit=${limit}`)
  if (!response.ok) {
    throw new Error(await readError(response))
  }
  return response.json()
}

export async function createImprovementLog(payload: ImprovementLogCreate): Promise<ImprovementLogEntry> {
  const response = await fetch(`${API_BASE}/api/improvements`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
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
