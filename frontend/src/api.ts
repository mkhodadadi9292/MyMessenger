import type { AuthTokens, MessageOut } from './types'

const API = '/api/v1'

let accessToken: string | null = localStorage.getItem('access_token')
let refreshToken: string | null = localStorage.getItem('refresh_token')

export function setTokens(tokens: AuthTokens) {
  accessToken = tokens.access_token
  refreshToken = tokens.refresh_token
  localStorage.setItem('access_token', accessToken)
  localStorage.setItem('refresh_token', refreshToken)
}

export function clearTokens() {
  accessToken = null
  refreshToken = null
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
}

export function hasSession(): boolean {
  return accessToken !== null
}

export function getAccessToken(): string | null {
  return accessToken
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message)
  }
}

async function tryRefresh(): Promise<boolean> {
  if (!refreshToken) return false
  const response = await fetch(`${API}/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  })
  if (!response.ok) {
    clearTokens()
    return false
  }
  const body = await response.json()
  accessToken = body.access_token
  refreshToken = body.refresh_token
  localStorage.setItem('access_token', body.access_token)
  localStorage.setItem('refresh_token', body.refresh_token)
  return true
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { ...(options.headers as Record<string, string>) }
  if (accessToken) headers['Authorization'] = `Bearer ${accessToken}`
  let response = await fetch(`${API}${path}`, { ...options, headers })
  if (response.status === 401 && refreshToken && !path.startsWith('/auth/')) {
    if (await tryRefresh()) {
      headers['Authorization'] = `Bearer ${accessToken}`
      response = await fetch(`${API}${path}`, { ...options, headers })
    }
  }
  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = await response.json()
      detail = body.detail ?? detail
    } catch {
      /* keep statusText */
    }
    throw new ApiError(response.status, detail)
  }
  return (await response.json()) as T
}

export async function uploadArtifact(
  chatId: number,
  file: File,
  kind: 'image' | 'video' | 'audio',
  replyToId: number | null,
): Promise<MessageOut> {
  const form = new FormData()
  form.append('file', file)
  form.append('kind', kind)
  if (replyToId !== null) form.append('reply_to_id', String(replyToId))
  return api<MessageOut>(`/chats/${chatId}/artifacts`, { method: 'POST', body: form })
}
