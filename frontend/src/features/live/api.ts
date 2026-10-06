import { ApiRequestError } from '../../api/client'
import { getAccessToken, reportUnauthorizedSession } from '../auth/session'
import { belongsToDataset, datasetPath } from './dataset'
import type { DatasetScope, DocumentDetail, DocumentSummary, ProcessingStatusResponse } from './types'

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/+$/, '')

function apiPath(path: string) { return `${apiBaseUrl}${path}` }

async function jsonRequest<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(apiPath(path), { ...init, headers: { Accept: 'application/json', Authorization: `Bearer ${getAccessToken()}`, ...init?.headers } })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiRequestError('The document API could not be reached. Check that the backend is running, then retry.')
  }
  if (!response.ok) {
    if (response.status === 401) reportUnauthorizedSession()
    let message = `The document API returned HTTP ${response.status}.`
    try {
      const body: unknown = await response.json()
      if (body && typeof body === 'object' && 'detail' in body) {
        const detail = body.detail
        if (typeof detail === 'string') message = detail
        else if (detail && typeof detail === 'object' && 'message' in detail && typeof detail.message === 'string') message = detail.message
      }
    } catch { /* The HTTP status is still actionable. */ }
    throw new ApiRequestError(message, response.status)
  }
  try { return await response.json() as T }
  catch { throw new ApiRequestError('The document API returned an unreadable response.', response.status) }
}

export async function listDocuments(signal?: AbortSignal, dataset: DatasetScope = 'operational'): Promise<DocumentSummary[]> {
  const data = await jsonRequest<{ items: DocumentSummary[] }>(datasetPath('/documents', dataset), { signal })
  if (!Array.isArray(data.items)) throw new ApiRequestError('The document list response was invalid.')
  if (!data.items.every((item) => belongsToDataset(item, dataset))) throw new ApiRequestError('The document list contained an item outside the selected dataset.')
  return data.items
}

export async function getDocument(id: string, signal?: AbortSignal, dataset: DatasetScope = 'operational') {
  const detail = await jsonRequest<DocumentDetail>(datasetPath(`/documents/${encodeURIComponent(id)}`, dataset), { signal })
  if (!belongsToDataset(detail, dataset)) throw new ApiRequestError('This document is outside the selected dataset.')
  return detail
}

export function processDocument(id: string) {
  return jsonRequest<ProcessingStatusResponse>(`/documents/${encodeURIComponent(id)}/process`, { method: 'POST' })
}

export function getProcessingStatus(id: string, signal?: AbortSignal, dataset: DatasetScope = 'operational') {
  return jsonRequest<ProcessingStatusResponse>(datasetPath(`/documents/${encodeURIComponent(id)}/processing-status`, dataset), { signal })
}

export async function getPageImage(id: string, page: number, signal?: AbortSignal, dataset: DatasetScope = 'operational'): Promise<Blob> {
  let response: Response
  try {
    response = await fetch(apiPath(datasetPath(`/documents/${encodeURIComponent(id)}/pages/${page}/image`, dataset)), {
      headers: { Authorization: `Bearer ${getAccessToken()}` }, signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiRequestError('The source page could not be reached. Check that the backend is running, then retry.')
  }
  if (response.status === 401) reportUnauthorizedSession()
  if (!response.ok) throw new ApiRequestError(`The source page returned HTTP ${response.status}.`, response.status)
  return response.blob()
}

export function uploadDocument(file: File, onProgress: (percent: number) => void, onXhr?: (xhr: XMLHttpRequest) => void): Promise<DocumentDetail> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    onXhr?.(xhr)
    xhr.open('POST', apiPath('/documents/upload'))
    xhr.responseType = 'json'
    xhr.setRequestHeader('Accept', 'application/json')
    xhr.setRequestHeader('Authorization', `Bearer ${getAccessToken()}`)
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.min(99, Math.round(event.loaded / event.total * 100)))
    }
    xhr.onload = () => {
      if (xhr.status === 401) reportUnauthorizedSession()
      if (xhr.status >= 200 && xhr.status < 300 && xhr.response && typeof xhr.response.id === 'string') {
        onProgress(100)
        resolve(xhr.response as DocumentDetail)
        return
      }
      const detail = xhr.response?.detail
      const message = typeof detail === 'string' ? detail : detail && typeof detail.message === 'string' ? detail.message : `Upload failed with HTTP ${xhr.status}.`
      reject(new ApiRequestError(message, xhr.status))
    }
    xhr.onerror = () => reject(new ApiRequestError('The upload connection failed. Check the backend and retry.'))
    xhr.onabort = () => reject(new DOMException('Upload cancelled', 'AbortError'))
    const body = new FormData()
    body.append('file', file)
    xhr.send(body)
  })
}
