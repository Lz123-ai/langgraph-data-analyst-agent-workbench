import type { DatasetPreviewResponse, DatasetUploadResponse } from './types'
import { apiHeaders, apiUrl } from './client'

export async function uploadDataset(file: File): Promise<DatasetUploadResponse> {
  const form = new FormData()
  form.append('file', file)
  const response = await fetch(apiUrl('/api/datasets/upload'), {
    method: 'POST',
    headers: apiHeaders(),
    body: form
  })
  if (!response.ok) {
    throw new Error(await readError(response))
  }
  return response.json()
}

export async function getDatasetPreview(datasetId: string, limit = 20): Promise<DatasetPreviewResponse> {
  const response = await fetch(apiUrl(`/api/datasets/${datasetId}/preview`, { limit }), { headers: apiHeaders() })
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
