import type { AgentOpsSummary, AgentTaskDetailResponse, AgentTaskListResponse, EvalRunListResponse, EvalRunRecord } from './types'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

export async function getAgentOpsSummary(): Promise<AgentOpsSummary> {
  const response = await fetch(`${API_BASE}/api/ops/summary`)
  if (!response.ok) throw new Error(await readError(response))
  return response.json()
}

export async function listAgentTasks(limit = 20): Promise<AgentTaskListResponse> {
  const response = await fetch(`${API_BASE}/api/ops/tasks?limit=${limit}`)
  if (!response.ok) throw new Error(await readError(response))
  return response.json()
}

export async function getAgentTask(taskId: string): Promise<AgentTaskDetailResponse> {
  const response = await fetch(`${API_BASE}/api/ops/tasks/${taskId}`)
  if (!response.ok) throw new Error(await readError(response))
  return response.json()
}

export async function listEvalRuns(limit = 10): Promise<EvalRunListResponse> {
  const response = await fetch(`${API_BASE}/api/ops/eval-runs?limit=${limit}`)
  if (!response.ok) throw new Error(await readError(response))
  return response.json()
}

export async function importLatestEvalRun(): Promise<EvalRunRecord> {
  const response = await fetch(`${API_BASE}/api/ops/eval-runs/import`, { method: 'POST' })
  if (!response.ok) throw new Error(await readError(response))
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
