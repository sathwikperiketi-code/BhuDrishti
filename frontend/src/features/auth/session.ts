import { useCallback, useEffect, useState } from 'react'

export type SessionRole = 'ADMIN' | 'REVENUE_OFFICER' | 'VERIFIER' | 'AUDITOR'
export interface SessionUser { id: string; name: string; username?: string; email: string; role: SessionRole; requestedRole?: SessionRole | null; roleApprovalStatus?: 'PENDING' | 'APPROVED' | 'REJECTED' | null }
export interface AuthSession { accessToken: string; tokenType: string; user: SessionUser; expiresAt: string }

const apiBase = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/+$/, '')
const storageKey = 'bd.auth.session'
let activeToken = ''
let invalidReported = false

export function getAccessToken() { return activeToken || readStoredSession()?.accessToken || '' }
export function reportUnauthorizedSession() {
  if (invalidReported) return
  invalidReported = true
  window.dispatchEvent(new Event('bd-auth-invalid'))
}

type AuthState =
  | { phase: 'loading' }
  | { phase: 'ready'; session: AuthSession }
  | { phase: 'signedOut' }
  | { phase: 'error'; message: string }

function clearSession() {
  activeToken = ''
  invalidReported = false
  window.sessionStorage.removeItem(storageKey)
}

function readStoredSession(): AuthSession | null {
  const stored = window.sessionStorage.getItem(storageKey)
  if (!stored) return null
  try { return JSON.parse(stored) as AuthSession }
  catch { clearSession(); return null }
}

async function readError(response: Response, fallback: string) {
  const body = await response.json().catch(() => ({})) as { detail?: unknown }
  return typeof body.detail === 'string' ? body.detail : fallback
}

async function createSession(email: string, password: string): Promise<AuthSession> {
  let response: Response
  try {
    response = await fetch(`${apiBase}/auth/login`, {
      method: 'POST',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: email.trim(), password }),
    })
  } catch { throw new Error('The authentication service could not be reached.') }
  if (response.status === 401) throw new Error('Invalid email or password.')
  if (!response.ok) throw new Error(await readError(response, `Sign-in failed (HTTP ${response.status}).`))
  const session = await response.json() as AuthSession
  if (!session.accessToken || !session.user?.id || !session.expiresAt) throw new Error('The authentication response was incomplete.')
  return session
}

async function restoreSession(saved: AuthSession): Promise<AuthSession> {
  if (new Date(saved.expiresAt).getTime() <= Date.now()) throw new Error('Your session expired. Sign in again.')
  let response: Response
  try {
    response = await fetch(`${apiBase}/auth/me`, {
      headers: { Accept: 'application/json', Authorization: `Bearer ${saved.accessToken}` },
    })
  } catch { throw new Error('The authentication service could not be reached. Sign in again when it is available.') }
  if (!response.ok) throw new Error(await readError(response, 'Your session is no longer valid. Sign in again.'))
  const user = await response.json() as SessionUser
  if (!user.id || !user.role) throw new Error('The account response was incomplete.')
  return { ...saved, user }
}

export function useSession() {
  const [state, setState] = useState<AuthState>(() => readStoredSession() ? { phase: 'loading' } : { phase: 'signedOut' })

  const signIn = useCallback(async (email: string, password: string) => {
    setState({ phase: 'loading' })
    try {
      const session = await createSession(email, password)
      activeToken = session.accessToken
      invalidReported = false
      window.sessionStorage.setItem(storageKey, JSON.stringify(session))
      setState({ phase: 'ready', session })
      window.location.hash = '#/dashboard'
    } catch (error) {
      clearSession()
      setState({ phase: 'error', message: error instanceof Error ? error.message : 'Sign-in failed.' })
    }
  }, [])

  useEffect(() => {
    let active = true
    const saved = readStoredSession()
    if (!saved) return () => { active = false }
    void restoreSession(saved).then((session) => {
      if (!active) return
      activeToken = session.accessToken
      invalidReported = false
      window.sessionStorage.setItem(storageKey, JSON.stringify(session))
      setState({ phase: 'ready', session })
    }, (error: unknown) => {
      if (!active) return
      clearSession()
      setState({ phase: 'error', message: error instanceof Error ? error.message : 'Sign in again.' })
    })
    return () => { active = false }
  }, [])

  useEffect(() => {
    const invalidate = () => {
      clearSession()
      setState({ phase: 'error', message: 'Your session expired or was revoked. Sign in again.' })
    }
    window.addEventListener('bd-auth-invalid', invalidate)
    let timer: number | undefined
    if (state.phase === 'ready') {
      const expiresAt = new Date(state.session.expiresAt).getTime()
      const scheduleExpiry = () => {
        const remaining = expiresAt - Date.now()
        if (remaining <= 0 || !Number.isFinite(remaining)) reportUnauthorizedSession()
        else timer = window.setTimeout(scheduleExpiry, Math.min(remaining, 2_147_483_647))
      }
      scheduleExpiry()
    }
    return () => {
      window.removeEventListener('bd-auth-invalid', invalidate)
      if (timer !== undefined) window.clearTimeout(timer)
    }
  }, [state])

  const signOut = useCallback(() => {
    const token = getAccessToken()
    clearSession()
    setState({ phase: 'signedOut' })
    window.location.hash = '#/login'
    if (token) void fetch(`${apiBase}/auth/logout`, { method: 'POST', headers: { Authorization: `Bearer ${token}` } }).catch(() => undefined)
  }, [])

  const clearError = useCallback(() => {
    setState((current) => current.phase === 'error' ? { phase: 'signedOut' } : current)
  }, [])

  return { state, signIn, signOut, clearError }
}
