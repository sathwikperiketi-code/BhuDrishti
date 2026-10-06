import { ApiRequestError } from '../../api/client'
import { reportUnauthorizedSession } from '../auth/session'
import type { ReviewAction, ReviewCaseDetail, ReviewCaseSummary, ReviewDecision, ReviewDocument, QueueFilter, QueueSort } from './types'

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/+$/, '')

async function request<T>(path: string, token: string, init: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${apiBaseUrl}${path}`, {
      ...init,
      headers: { Accept: 'application/json', Authorization: `Bearer ${token}`, ...init.headers },
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiRequestError('The review API could not be reached. Check the backend and retry.')
  }
  if (!response.ok) {
    if (response.status === 401) reportUnauthorizedSession()
    let message = `Review request failed with HTTP ${response.status}.`
    try {
      const body: unknown = await response.json()
      if (body && typeof body === 'object' && 'detail' in body) {
        const detail = body.detail
        if (typeof detail === 'string') message = detail
        else if (detail && typeof detail === 'object' && 'message' in detail && typeof detail.message === 'string') message = detail.message
        else if (detail && typeof detail === 'object' && 'reasons' in detail && Array.isArray(detail.reasons)) message = detail.reasons.join(' ')
      }
    } catch { /* The HTTP status is still actionable. */ }
    throw new ApiRequestError(message, response.status)
  }
  try { return await response.json() as T }
  catch { throw new ApiRequestError('The review API returned an unreadable response.', response.status) }
}

export interface QueueQuery {
  filter: QueueFilter
  search: string
  sort: QueueSort
  direction: 'asc' | 'desc'
  offset?: number
  limit?: number
}

export async function listReviews(token: string, query: QueueQuery, signal?: AbortSignal) {
  const params = new URLSearchParams({
    filter: query.filter,
    search: query.search,
    sort: query.sort,
    direction: query.direction,
    offset: String(query.offset ?? 0),
    limit: String(query.limit ?? 50),
  })
  const data = await request<{ items: ReviewCaseSummary[]; total: number }>(`/reviews?${params}`, token, { signal })
  if (!Array.isArray(data.items)) throw new ApiRequestError('The review queue response was invalid.')
  return data
}

export function getReview(token: string, recordId: string, signal?: AbortSignal) {
  return request<ReviewCaseDetail>(`/reviews/${encodeURIComponent(recordId)}`, token, { signal })
}

export function getReviewDocument(token: string, documentId: string, signal?: AbortSignal) {
  return request<ReviewDocument>(`/documents/${encodeURIComponent(documentId)}`, token, { signal })
}

export function reprocessReviewDocument(token: string, documentId: string) {
  return request<unknown>(`/documents/${encodeURIComponent(documentId)}/process`, token, { method: 'POST' })
}

export function startReview(token: string, recordId: string) {
  return request<ReviewCaseDetail>(`/reviews/${encodeURIComponent(recordId)}/start`, token, { method: 'POST' })
}

export function assignReview(token: string, recordId: string, officerId: string) {
  return request<ReviewCaseDetail>(`/reviews/${encodeURIComponent(recordId)}/assign`, token, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ officerId }),
  })
}

export function acceptClearFields(token: string, recordId: string) {
  return request<ReviewCaseDetail>(`/reviews/${encodeURIComponent(recordId)}/accept-clear-fields`, token, { method: 'POST' })
}

export function reviewField(token: string, recordId: string, fieldName: string, action: ReviewAction, reviewedValue?: unknown, reason?: string) {
  return request<ReviewCaseDetail>(`/reviews/${encodeURIComponent(recordId)}/fields/${encodeURIComponent(fieldName)}`, token, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action, ...(action === 'edit' ? { reviewedValue } : {}), ...(reason?.trim() ? { reason: reason.trim() } : {}) }),
  })
}

export function resolveReviewIssue(token: string, recordId: string, issueCode: string, resolution: 'corrected' | 'confirmed' | 'not_applicable', reason: string, fieldName?: string | null) {
  return request<ReviewCaseDetail>(`/reviews/${encodeURIComponent(recordId)}/issues/${encodeURIComponent(issueCode)}/resolve`, token, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ resolution, reason: reason.trim(), ...(fieldName ? { fieldName } : {}) }),
  })
}

export function decideReview(token: string, recordId: string, decision: ReviewDecision, reason?: string) {
  return request<ReviewCaseDetail>(`/reviews/${encodeURIComponent(recordId)}/decision`, token, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ decision, ...(reason?.trim() ? { reason: reason.trim() } : {}) }),
  })
}

export function recommendReview(token: string, recordId: string, recommendation: ReviewDecision, reason: string) {
  return request<ReviewCaseDetail>(`/reviews/${encodeURIComponent(recordId)}/recommendation`, token, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ recommendation, reason: reason.trim() }),
  })
}
