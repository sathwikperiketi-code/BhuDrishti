export type PublicAuthRoute = 'login' | 'signup' | 'verify-email' | 'forgot-password' | 'reset-password'

export function publicAuthRoute(hash: string): PublicAuthRoute | null {
  const path = hash.replace(/^#\/?/, '').split('?')[0]
  return path === 'login' || path === 'signup' || path === 'verify-email'
    || path === 'forgot-password' || path === 'reset-password' ? path : null
}
