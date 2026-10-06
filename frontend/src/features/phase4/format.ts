import type { AuditEvent } from './types'
import { displayRoleName } from '../../lib/roles.ts'

export function displayDate(value: string | null | undefined, options: Intl.DateTimeFormatOptions = { dateStyle: 'medium', timeStyle: 'short' }): string {
  if (!value) return 'Pending'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Unknown date' : date.toLocaleString(undefined, options)
}

export function titleCase(value: string | null | undefined): string {
  if (!value) return 'Pending'
  if (['ADMIN', 'REVENUE_OFFICER', 'VERIFIER', 'AUDITOR', 'SYSTEM'].includes(value)) return displayRoleName(value)
  if (value === 'send_back') return 'Send back'
  if (value === 'sent_back') return 'Sent back'
  return value.replaceAll('_', ' ').replaceAll('-', ' ').toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase())
}

export function fieldLabel(value: string): string {
  return value.replace(/([A-Z])/g, ' $1').replace(/^./, (letter) => letter.toUpperCase())
}

export function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value)
  if (Array.isArray(value)) return value.length ? value.map(displayValue).join(', ') : '—'
  if (typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>)
      .filter(([, item]) => item !== null && item !== '' && !Array.isArray(item) && typeof item !== 'object')
    return entries.slice(0, 3).map(([key, item]) => `${fieldLabel(key)}: ${String(item)}`).join(' · ') || 'Structured details available'
  }
  return '—'
}

export function eventLabel(event: AuditEvent | string): string {
  const code = typeof event === 'string' ? event : event.eventType
  const labels: Record<string, string> = {
    FIELD_EDITED: 'Field correction saved', FIELD_ACCEPTED: 'Extracted value accepted', FIELD_REJECTED: 'Field value rejected',
    ISSUE_RESOLVED: 'Validation finding resolved', REVIEW_RECOMMENDED: 'Recommendation recorded',
    RECORD_APPROVED: 'Final decision · Approve', RECORD_REJECTED: 'Final decision · Reject', RECORD_SENT_BACK: 'Final decision · Send back',
    GEOMETRY_IMPORTED: 'Parcel geometry imported', GEOMETRY_REPLACED: 'Parcel geometry replaced', GIS_INDEXED: 'Sourced geometry indexed',
  }
  if (labels[code]) return labels[code]
  return titleCase(code)
}

export function auditResult(event: AuditEvent): string {
  if (event.eventType === 'REVIEW_RECOMMENDED' && typeof event.metadata?.value === 'string') return `Recommendation: ${titleCase(event.metadata.value)}. This is not a final decision.`
  if (event.eventType === 'ISSUE_RESOLVED' && typeof event.metadata?.resolution === 'string') return `Finding resolution: ${titleCase(event.metadata.resolution)}. Rationale saved with this event.`
  const outcomes: Record<string, string> = {
    DOCUMENT_UPLOADED: 'Source stored for processing.', PROCESSING_STARTED: 'Processing attempt started.',
    PREPROCESSING_COMPLETED: 'Source preprocessing completed.', OCR_COMPLETED: 'Extracted source text stored.',
    EXTRACTION_COMPLETED: 'Structured fields and evidence stored.', VALIDATION_COMPLETED: 'Validation results stored; human review still required.',
    CONFLICT_DETECTED: 'Validation finding recorded for human review.', PROCESSING_FAILED: 'Processing failed; inspect the source and error before retrying.',
    REVIEW_CREATED: 'Human-review case created.', REVIEW_STARTED: 'Review started.',
    FIELD_EDITED: 'Human-reviewed value saved; original extraction retained.', FIELD_ACCEPTED: 'Extracted value accepted as the human-reviewed value.',
    FIELD_REJECTED: 'Field marked rejected; this is not a final record rejection.', ISSUE_RESOLVED: 'Resolution and rationale saved for this validation finding.',
    REVIEW_RECOMMENDED: 'Recommendation recorded; this is not a final decision.', REVIEW_ASSIGNED: 'Final-decision assignment updated.',
    RECORD_APPROVED: 'Final approval recorded; reviewed values published to the record.', RECORD_REJECTED: 'Final rejection recorded; source and history retained.',
    RECORD_SENT_BACK: 'Record sent back; source can be reprocessed.', GEOMETRY_IMPORTED: 'Boundary and identified source provenance stored.',
    GEOMETRY_REPLACED: 'Current boundary replaced; prior provenance recorded in the audit trail.', GIS_INDEXED: 'Approved record linked to sourced geometry.',
  }
  return outcomes[event.eventType] || event.description || 'Event recorded.'
}

export function eventTone(code: string): 'success' | 'warning' | 'danger' | 'info' {
  if (code.includes('REJECTED') || code.includes('FAILED')) return 'danger'
  if (code.includes('CONFLICT') || code.includes('SENT_BACK')) return 'warning'
  if (code.includes('APPROVED') || code.includes('INDEXED') || code.includes('COMPLETED')) return 'success'
  return 'info'
}

export function recordHref(id: string) { return `#/records/${encodeURIComponent(id)}` }
export function auditHref(id: string) { return `#/audit/${encodeURIComponent(id)}` }
export function gisHref(id: string) { return `#/gis?record=${encodeURIComponent(id)}` }
export function recordEvidenceHref(id: string) { return `${recordHref(id)}?section=evidence` }
export function reviewHref(id: string) { return `#/review/${encodeURIComponent(id)}` }
