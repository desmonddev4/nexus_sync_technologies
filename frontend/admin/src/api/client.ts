const DEFAULT_API_BASE_URL = import.meta.env.PROD
  ? 'https://nexus-sync-backend.onrender.com/api/v1'
  : '/api/v1'
export function normalizeApiBaseUrl(value: string) {
  const baseUrl = value.replace(/\/+$/, '')
  if (!/^https?:\/\//i.test(baseUrl)) return baseUrl || '/api/v1'

  const url = new URL(baseUrl)
  const path = url.pathname.replace(/\/+$/, '')
  if (!path || path === '/') url.pathname = '/api/v1'
  else if (path !== '/api/v1' && !path.endsWith('/api/v1')) url.pathname = `${path}/api/v1`
  return `${url.origin}${url.pathname.replace(/\/+$/, '')}`
}

const API_BASE_URL = normalizeApiBaseUrl(import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE_URL)
const AUTH_STORAGE_KEY = 'nexus-sync-operations-token'
let authToken = readStoredToken()

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export function getAuthToken() {
  return authToken
}

export function saveAuthToken(token: string) {
  authToken = token
  try {
    window.sessionStorage.setItem(AUTH_STORAGE_KEY, token)
  } catch {
    // Keep the token in memory when browser storage is unavailable.
  }
}

export function clearAuthToken() {
  authToken = null
  try {
    window.sessionStorage.removeItem(AUTH_STORAGE_KEY)
  } catch {
    // The in-memory token is still cleared.
  }
}

function readStoredToken(): string | null {
  try {
    return typeof window === 'undefined' ? null : window.sessionStorage.getItem(AUTH_STORAGE_KEY)
  } catch {
    return null
  }
}

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  const token = getAuthToken()
  if (token) headers.set('Authorization', `Token ${token}`)
  if (init.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  const response = await fetch(`${API_BASE_URL}/${path.replace(/^\//, '')}`, {
    ...init,
    headers,
  })

  if (response.status === 204) return undefined as T

  const isJson = response.headers.get('content-type')?.includes('application/json')
  const payload: unknown = isJson ? await response.json() : await response.text()
  if (!response.ok) {
    throw new ApiError(extractErrorMessage(payload), response.status)
  }
  return payload as T
}

function extractErrorMessage(payload: unknown) {
  if (typeof payload === 'string' && payload) return payload
  if (payload && typeof payload === 'object') {
    const detail = 'detail' in payload ? payload.detail : undefined
    if (typeof detail === 'string') return detail
    return Object.entries(payload)
      .map(([field, value]) => `${field}: ${Array.isArray(value) ? value.join(', ') : String(value)}`)
      .join(' · ')
  }
  return 'The request could not be completed.'
}