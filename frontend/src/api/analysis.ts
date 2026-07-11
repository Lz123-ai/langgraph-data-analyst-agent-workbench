import type { AnalysisCancelResponse, AnalysisTaskResponse, TaskEvent } from './types'
import { apiHeaders, apiUrl, eventSourceUrl } from './client'

export async function createAnalysisTask(datasetId: string, question: string): Promise<AnalysisTaskResponse> {
  const response = await fetch(apiUrl('/api/analysis/tasks'), {
    method: 'POST',
    headers: apiHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ dataset_id: datasetId, question })
  })
  if (!response.ok) {
    throw new Error(await readError(response))
  }
  return response.json()
}

export function subscribeToTask(taskId: string, onEvent: (event: TaskEvent) => void, onError: (message: string) => void): EventSource {
  const source = new EventSource(eventSourceUrl(`/api/analysis/tasks/${taskId}/events`))
  const eventTypes = ['task_started', 'task_resumed', 'node_completed', 'task_completed', 'task_failed', 'task_cancelled', 'heartbeat']
  for (const type of eventTypes) {
    source.addEventListener(type, (raw) => {
      const message = raw as MessageEvent<string>
      onEvent(JSON.parse(message.data) as TaskEvent)
    })
  }
  source.onerror = () => {
    onError('SSE 连接中断。')
  }
  return source
}

export async function cancelAnalysisTask(taskId: string): Promise<AnalysisCancelResponse> {
  const response = await fetch(apiUrl(`/api/analysis/tasks/${taskId}/cancel`), {
    method: 'POST',
    headers: apiHeaders()
  })
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
