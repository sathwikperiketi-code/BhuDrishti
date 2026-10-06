import { useCallback, useEffect, useState } from 'react'
import { getHealth } from '../api/health'
import type { HealthResponse } from '../types/health'

export type HealthState =
  | { phase: 'loading' }
  | { phase: 'ready'; data: HealthResponse; checkedAt: Date }
  | { phase: 'error'; message: string }

export function useHealth() {
  const [attempt, setAttempt] = useState(0)
  const [state, setState] = useState<HealthState>({ phase: 'loading' })

  useEffect(() => {
    const controller = new AbortController()
    getHealth(controller.signal)
      .then((data) => setState({ phase: 'ready', data, checkedAt: new Date() }))
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setState({ phase: 'error', message: error instanceof Error ? error.message : 'The API health check failed.' })
        }
      })
    return () => controller.abort()
  }, [attempt])

  const retry = useCallback(() => {
    setState({ phase: 'loading' })
    setAttempt((current) => current + 1)
  }, [])

  return { state, retry }
}
