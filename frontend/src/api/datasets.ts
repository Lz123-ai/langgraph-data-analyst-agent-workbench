import type { DatasetPreviewResponse, DatasetUploadResponse } from './types'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

export async function uploadDataset(file: File): Promise<DatasetUploadResponse> {
  const form = new FormData()
  form.append('file', file)
  const response = await fetch(`${API_BASE}/api/datasets/upload`, {
    method: 'POST',
    body: form
  })
  if (!response.ok) {
    throw new Error(await readError(response))
  }
  return response.json()
}

export async function getDatasetPreview(datasetId: string, limit = 20): Promise<DatasetPreviewResponse> {
  const response = await fetch(`${API_BASE}/api/datasets/${datasetId}/preview?limit=${limit}`)
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
