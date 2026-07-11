import type { AgentOpsSummary, AgentTaskDetailResponse, AgentTaskListResponse, EvalRunListResponse, EvalRunRecord } from './types'
import { apiHeaders, apiUrl } from './client'

export async function getAgentOpsSummary(): Promise<AgentOpsSummary> {
  const response = await fetch(apiUrl('/api/ops/summary'), { headers: apiHeaders() })
  if (!response.ok) throw new Error(await readError(response))
  return response.json()
}

export async function listAgentTasks(limit = 20): Promise<AgentTaskListResponse> {
  const response = await fetch(apiUrl('/api/ops/tasks', { limit }), { headers: apiHeaders() })
  if (!response.ok) throw new Error(await readError(response))
  return response.json()
}

export async function getAgentTask(taskId: string): Promise<AgentTaskDetailResponse> {
  const response = await fetch(apiUrl(`/api/ops/tasks/${taskId}`), { headers: apiHeaders() })
  if (!response.ok) throw new Error(await readError(response))
  return response.json()
}

export async function listEvalRuns(limit = 10): Promise<EvalRunListResponse> {
  const response = await fetch(apiUrl('/api/ops/eval-runs', { limit }), { headers: apiHeaders() })
  if (!response.ok) throw new Error(await readError(response))
  return response.json()
}

export async function importLatestEvalRun(): Promise<EvalRunRecord> {
  const response = await fetch(apiUrl('/api/ops/eval-runs/import'), { method: 'POST', headers: apiHeaders() })
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
