import { FIELD_LABELS } from '../live/format'
import type { ReviewPriority, ReviewStatus } from './types'

export function reviewFieldLabel(field: string) {
  return FIELD_LABELS[field] || field.replace(/([a-z])([A-Z])/g, '$1 $2').replace(/_/g, ' ').replace(/^./, (letter) => letter.toUpperCase())
}

export function reviewValue(value: unknown): string {
  if (value == null || value === '') return 'Not detected'
  if (typeof value === 'string') return value
  if (typeof value === 'number') return String(value)
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (Array.isArray(value)) return value.length ? value.map(reviewValue).join(', ') : 'None recorded'
  return JSON.stringify(value)
}

export function reviewDate(value: string | null | undefined) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

export function priorityLabel(value: ReviewPriority) {
  return value === 'high' ? 'High' : value === 'medium' ? 'Medium' : value === 'low' ? 'Low' : value
}

export function reviewStatusLabel(value: ReviewStatus) {
  return ({ queued: 'Awaiting review', in_progress: 'In review', approved: 'Approved', rejected: 'Rejected', sent_back: 'Sent back' } as Record<string, string>)[value] || value.replace(/_/g, ' ')
}

export function reviewSourcePage(source: { sourcePage?: number; page?: number } | null | undefined) { return source?.sourcePage || source?.page || null }
export function reviewSourceText(source: { extractedText?: string | null; text?: string | null } | null | undefined) { return source?.extractedText || source?.text || null }
export function reviewSourceMethod(source: { extractionMethod?: string | null } | null | undefined) { return source?.extractionMethod || null }

export function confidenceLabel(value: number | null | undefined) {
  return value == null || !Number.isFinite(value) ? 'Unmeasured' : `${Math.round(Math.max(0, Math.min(1, value)) * 100)}%`
}
