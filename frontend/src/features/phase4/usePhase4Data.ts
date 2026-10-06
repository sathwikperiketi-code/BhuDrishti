import { useCallback, useEffect, useState } from 'react'

type Result<T> = { key: string; data?: T; error?: string }
export type RemoteData<T> = { phase: 'loading' } | { phase: 'ready'; data: T } | { phase: 'error'; error: string }

export function usePhase4Data<T>(key: string, load: (signal: AbortSignal) => Promise<T>) {
  const [nonce, setNonce] = useState(0)
  const [result, setResult] = useState<Result<T>>({ key: '' })
  const requestKey = `${key}:${nonce}`
  const retry = useCallback(() => setNonce((value) => value + 1), [])

  useEffect(() => {
    const controller = new AbortController()
    void load(controller.signal).then(
      (data) => { if (!controller.signal.aborted) setResult({ key: requestKey, data }) },
      (error: unknown) => {
        if (!controller.signal.aborted) setResult({ key: requestKey, error: error instanceof Error ? error.message : 'The request failed.' })
      },
    )
    return () => controller.abort()
  }, [load, requestKey])

  const state: RemoteData<T> = result.key !== requestKey
    ? { phase: 'loading' }
    : result.error
      ? { phase: 'error', error: result.error }
      : { phase: 'ready', data: result.data as T }
  return { state, retry }
}
