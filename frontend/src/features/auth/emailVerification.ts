export function accountLinkParameter(hash: string, name: 'token' | 'email'): string {
  const queryStart = hash.indexOf('?')
  if (queryStart < 0) return ''
  return new URLSearchParams(hash.slice(queryStart + 1)).get(name)?.trim() ?? ''
}

type VerificationResult = { verified: true } | { verified: false; error: unknown }

// Share an attempt across effect replays, while ignoring results after navigation.
// Tokens stay in this page's memory and are sent only by the existing account API.
export function createEmailVerificationRequest(verify: (token: string) => Promise<void>) {
  let current: { token: string; request: Promise<void> } | null = null
  return (token: string, onResult: (result: VerificationResult) => void) => {
    let active = true
    if (current?.token !== token) {
      const attempt = { token, request: verify(token) }
      current = attempt
      const clear = () => { if (current === attempt) current = null }
      void attempt.request.then(clear, clear)
    }
    void current.request.then(
      () => { if (active) onResult({ verified: true }) },
      (error: unknown) => { if (active) onResult({ verified: false, error }) },
    )
    return () => { active = false }
  }
}
