export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

const session = typeof sessionStorage === 'undefined' ? null : sessionStorage
let ACCESS_TOKEN = session?.getItem('api_access_token') ?? import.meta.env.VITE_API_ACCESS_TOKEN ?? ''

export function setApiAccessToken(value: string): void {
  ACCESS_TOKEN = value.trim()
  if (ACCESS_TOKEN) session?.setItem('api_access_token', ACCESS_TOKEN)
  else session?.removeItem('api_access_token')
}

export function hasApiAccessToken(): boolean {
  return Boolean(ACCESS_TOKEN)
}

export function apiHeaders(headers: HeadersInit = {}): HeadersInit {
  return ACCESS_TOKEN ? { ...headers, Authorization: `Bearer ${ACCESS_TOKEN}` } : headers
}

export function apiUrl(path: string, query: Record<string, string | number> = {}): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) params.set(key, String(value))
  const suffix = params.toString()
  return `${API_BASE}${path}${suffix ? `?${suffix}` : ''}`
}

export function eventSourceUrl(path: string): string {
  return apiUrl(path, ACCESS_TOKEN ? { access_token: ACCESS_TOKEN } : {})
}
