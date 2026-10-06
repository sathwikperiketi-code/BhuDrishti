import { registrationRoles } from './registrationRoles.ts'

const apiBase = (import.meta.env?.VITE_API_BASE_URL || '/api/v1').replace(/\/+$/, '')

type AccountRequest = Record<string, string>

async function postAccount(path: string, body: AccountRequest): Promise<void> {
  let response: Response
  try {
    response = await fetch(`${apiBase}/auth/${path}`, {
      method: 'POST',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  } catch {
    throw new Error('The account service could not be reached. Please try again.')
  }

  // Only the existing backend's expected JSON contract confirms this action.
  if (response.ok) {
    const expectedStatus = path === 'verify-email' || path === 'reset-password' ? 200 : 202
    const contentType = response.headers.get('Content-Type')?.split(';')[0].trim().toLowerCase()
    const payload = contentType === 'application/json' ? await response.json().catch(() => null) : null
    const validMessage = payload !== null && typeof payload === 'object'
      && typeof payload.message === 'string' && Boolean(payload.message.trim())
    const validSignup = path !== 'signup' || (validMessage
      && registrationRoles.some((role) => role.value === payload.role)
      && payload.requestedRole === body.requestedRole
      && (payload.roleApprovalStatus === null || payload.roleApprovalStatus === 'PENDING'
        || payload.roleApprovalStatus === 'APPROVED' || payload.roleApprovalStatus === 'REJECTED'))
    if (response.status !== expectedStatus || !validMessage || !validSignup) {
      throw new Error('The account service returned an unexpected response. Please try again later.')
    }
    return
  }
  const payload = await response.json().catch(() => null) as { detail?: unknown } | null
  const detail = payload?.detail
  if (typeof detail === 'string' && detail.trim()) throw new Error(detail)
  if (Array.isArray(detail)) {
    const first = detail.find((item): item is { msg: string } =>
      typeof item === 'object' && item !== null && typeof item.msg === 'string')
    if (first) throw new Error(first.msg.replace(/^Value error,\s*/i, ''))
  }
  if ([500, 502, 503, 504].includes(response.status)) {
    throw new Error(`The account service is temporarily unavailable (HTTP ${response.status}). Please try again later.`)
  }
  throw new Error(`The request could not be completed (HTTP ${response.status}).`)
}

export interface SignupValues {
  fullName: string
  username: string
  email: string
  password: string
  confirmPassword: string
  requestedRole: import('./registrationRoles').RequestedRole
}

export function signup(values: SignupValues) {
  return postAccount('signup', {
    ...values,
    fullName: values.fullName.trim(),
    username: values.username.trim().toLowerCase(),
    email: values.email.trim().toLowerCase(),
  })
}

export function verifyEmail(token: string) {
  return postAccount('verify-email', { token })
}

export function resendVerification(email: string) {
  return postAccount('resend-verification', { email: email.trim().toLowerCase() })
}

export function forgotPassword(email: string) {
  return postAccount('forgot-password', { email: email.trim().toLowerCase() })
}

export function resetPassword(token: string, password: string, confirmPassword: string) {
  return postAccount('reset-password', { token, password, confirmPassword })
}
