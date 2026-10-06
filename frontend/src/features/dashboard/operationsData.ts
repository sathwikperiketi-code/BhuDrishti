import { useCallback } from 'react'
import { ApiRequestError } from '../../api/client'
import { reportUnauthorizedSession } from '../auth/session'
import type { DocumentSummary } from '../live/types'
import { listReviews } from '../review/api'
import type { ReviewCaseSummary } from '../review/types'
import { usePhase4Data } from '../phase4/usePhase4Data'

const base = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/+$/, '')

export interface AnalyticsMetrics {
  documentsTotal: number
  documentsProcessed: number
  processingFailed: number
  recordsTotal: number
  awaitingReview: number
  validationConflicts: number
  approvedRecords: number
  approvalRate: number | null
  reviewRate: number | null
  conflictRate: number | null
  averageQualityScore: number | null
}

export interface AnalyticsSummary {
  source: string
  disclaimer: string
  generatedAt: string
  metrics: AnalyticsMetrics
  processingVolume: { date: string; count: number }[]
  validationDistribution: { status: string; count: number }[]
  processingStatusDistribution: { status: string; count: number }[]
  recentActivity: { id: string; eventType: string; title: string; timestamp: string; href: string }[]
  definitions: { approvalRate: string; reviewRate: string; conflictRate: string; validationConflicts: string }
}

export interface OperationsData {
  summary: AnalyticsSummary
  reviews: ReviewCaseSummary[]
  documents: DocumentSummary[]
}

async function authorizedGet<T>(path: string, token: string, signal: AbortSignal): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${base}${path}`, {
      signal,
      headers: { Accept: 'application/json', Authorization: `Bearer ${token}` },
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiRequestError('Operational data is unavailable. Check the backend connection and retry.')
  }
  if (!response.ok) {
    if (response.status === 401) reportUnauthorizedSession()
    throw new ApiRequestError(`Operational data returned HTTP ${response.status}.`, response.status)
  }
  try { return await response.json() as T }
  catch { throw new ApiRequestError('Operational data returned an unreadable response.', response.status) }
}

export function loadAnalytics(token: string, signal: AbortSignal) {
  return authorizedGet<AnalyticsSummary>('/analytics/summary', token, signal)
}

export function useAnalytics(token: string) {
  const load = useCallback((signal: AbortSignal) => loadAnalytics(token, signal), [token])
  return usePhase4Data(`analytics:${token}`, load)
}

export function useOperationsData(token: string, developmentData?: OperationsData) {
  const previewData = import.meta.env.DEV ? developmentData : undefined
  const load = useCallback(async (signal: AbortSignal): Promise<OperationsData> => {
    if (previewData) return previewData
    const [summary, queue, documentList] = await Promise.all([
      loadAnalytics(token, signal),
      listReviews(token, { filter: 'all', search: '', sort: 'priority', direction: 'desc', limit: 5 }, signal),
      authorizedGet<{ items: DocumentSummary[] }>(`/documents?limit=6`, token, signal),
    ])
    return { summary, reviews: queue.items, documents: documentList.items }
  }, [token, previewData])
  return usePhase4Data(`operations:${token}`, load)
}

export function formatPercent(value: number | null): string {
  return value === null || !Number.isFinite(value) ? '—' : `${Math.round(value * 10) / 10}%`
}

export function formatCount(value: number): string { return Number.isFinite(value) ? value.toLocaleString() : '—' }

export function operationLabel(value: string): string {
  return value.replaceAll('_', ' ').replaceAll('-', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

export function readableDate(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Unknown date' : date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}
