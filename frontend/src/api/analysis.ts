import type { AnalysisTaskResponse, TaskEvent } from './types'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

export async function createAnalysisTask(datasetId: string, question: string): Promise<AnalysisTaskResponse> {
  const response = await fetch(`${API_BASE}/api/analysis/tasks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dataset_id: datasetId, question })
  })
  if (!response.ok) {
    throw new Error(await readError(response))
  }
  return response.json()
}

export function subscribeToTask(taskId: string, onEvent: (event: TaskEvent) => void, onError: (message: string) => void): EventSource {
  const source = new EventSource(`${API_BASE}/api/analysis/tasks/${taskId}/events`)
  const eventTypes = ['task_started', 'node_completed', 'task_completed', 'task_failed', 'heartbeat']
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

async function readError(response: Response): Promise<string> {
  try {
    const data = await response.json()
    return data.detail ?? response.statusText
  } catch {
    return response.statusText
  }
}
