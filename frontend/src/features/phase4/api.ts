import { ApiRequestError } from '../../api/client'
import { reportUnauthorizedSession } from '../auth/session'
import type { AuditListResponse, GisListResponse, NotificationsResponse, RecordDetailResponse, RecordsListResponse } from './types'

const base = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/+$/, '')

async function get<T>(path: string, token: string, signal?: AbortSignal): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${base}${path}`, {
      headers: { Accept: 'application/json', Authorization: `Bearer ${token}` },
      signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiRequestError('The service could not be reached. Check the backend and retry.')
  }
  if (!response.ok) {
    if (response.status === 401) reportUnauthorizedSession()
    let message = `The service returned HTTP ${response.status}.`
    try {
      const body = await response.json() as { detail?: string | { message?: string } }
      if (typeof body.detail === 'string') message = body.detail
      else if (body.detail?.message) message = body.detail.message
    } catch { /* retain HTTP status */ }
    throw new ApiRequestError(message, response.status)
  }
  try { return await response.json() as T }
  catch { throw new ApiRequestError('The service returned an unreadable response.', response.status) }
}

function query(params: Record<string, string | number | null | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) if (value !== null && value !== undefined && value !== '') search.set(key, String(value))
  return search.size ? `?${search.toString()}` : ''
}

export const phase4Api = {
  audit: (token: string, params: { recordId?: string; eventType?: string; limit?: number; offset?: number } = {}, signal?: AbortSignal) =>
    get<AuditListResponse>(`/audit/events${query(params)}`, token, signal),
  record: (token: string, id: string, signal?: AbortSignal) =>
    get<RecordDetailResponse>(`/records/${encodeURIComponent(id)}`, token, signal),
  records: (token: string, params: { limit?: number; offset?: number; q?: string } = {}, signal?: AbortSignal) =>
    get<RecordsListResponse>(`/records${query(params)}`, token, signal),
  parcels: (token: string, params: { state?: string; district?: string; village?: string; validationStatus?: string; recordStatus?: string; q?: string } = {}, signal?: AbortSignal) =>
    get<GisListResponse>(`/gis/parcels${query(params)}`, token, signal),
  importParcelGeometry: async (token: string, recordId: string, file: File, sourceReference: string): Promise<void> => {
    const form = new FormData()
    form.append('file', file)
    form.append('sourceReference', sourceReference.trim())
    let response: Response
    try {
      response = await fetch(`${base}/gis/parcels/${encodeURIComponent(recordId)}/geometry`, {
        method: 'POST',
        headers: { Accept: 'application/json', Authorization: `Bearer ${token}` },
        body: form,
      })
    } catch {
      throw new ApiRequestError('The geometry upload could not reach the service. Check the connection and retry.')
    }
    if (response.status === 401) reportUnauthorizedSession()
    if (!response.ok) {
      let message = `Geometry import failed with HTTP ${response.status}.`
      try {
        const body: unknown = await response.json()
        if (body && typeof body === 'object' && 'detail' in body) {
          const detail = body.detail
          if (typeof detail === 'string') message = detail
          else if (detail && typeof detail === 'object' && 'message' in detail && typeof detail.message === 'string') message = detail.message
        }
      } catch { /* retain the HTTP status */ }
      throw new ApiRequestError(message, response.status)
    }
  },
  notifications: (token: string, signal?: AbortSignal) =>
    get<NotificationsResponse>('/notifications', token, signal),
  markNotificationRead: async (token: string, eventId: string) => {
    let response: Response
    try {
      response = await fetch(`${base}/notifications/${encodeURIComponent(eventId)}/read`, {
        method: 'POST',
        headers: { Accept: 'application/json', Authorization: `Bearer ${token}` },
      })
    } catch { throw new ApiRequestError('The notification could not be marked as read. Check the connection and retry.') }
    if (response.status === 401) reportUnauthorizedSession()
    if (!response.ok) throw new ApiRequestError(`Mark as read failed with HTTP ${response.status}.`, response.status)
    return response.json() as Promise<{ eventId: string; read: true }>
  },
}
