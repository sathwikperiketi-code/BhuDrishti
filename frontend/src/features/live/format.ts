import type { DocumentStatus, DocumentSummary, ExtractedField, ProcessingStage } from './types'

export const STAGES: { key: ProcessingStage; label: string; short: string; detail: string }[] = [
  { key: 'upload', label: 'Upload', short: 'Upload', detail: 'Source file stored securely.' },
  { key: 'preprocessing', label: 'Preprocessing', short: 'Prepare', detail: 'Pages are rendered and cleaned.' },
  { key: 'ocr', label: 'Text recognition', short: 'OCR', detail: 'Text and regions are recognized.' },
  { key: 'field_extraction', label: 'Field extraction', short: 'Extract', detail: 'Candidates map to land record fields.' },
  { key: 'normalization', label: 'Normalization', short: 'Normalize', detail: 'Values use consistent formats.' },
  { key: 'validation', label: 'Validation', short: 'Validate', detail: 'Field, record, and reference checks run.' },
  { key: 'quality_score', label: 'Quality score', short: 'Score', detail: 'Weighted checks produce a score.' },
  { key: 'final_routing', label: 'Routing', short: 'Route', detail: 'The record enters its decision path.' },
]

export const FIELD_LABELS: Record<string, string> = {
  ownerName: 'Owner name', fatherOrGuardianName: 'Father / guardian', surveyNumber: 'Survey number',
  khasraNumber: 'Khasra number', khataNumber: 'Khata number', recordNumber: 'Record number',
  area: 'Area', areaUnit: 'Area unit', village: 'Village', mandalOrTehsil: 'Mandal / tehsil',
  district: 'District', state: 'State', landClassification: 'Land classification',
  ownershipDetails: 'Ownership details', mutationRecords: 'Mutation records', registrationInformation: 'Registration information',
}

export const FIELD_ORDER = Object.keys(FIELD_LABELS)

export function formatBytes(bytes: number) {
  if (!Number.isFinite(bytes) || bytes < 0) return 'Unknown size'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export function formatDate(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Unknown time' : date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

export function statusLabel(status: DocumentStatus) {
  return ({ uploaded: 'Ready to process', processing: 'Processing', completed: 'Processed', failed: 'Processing failed' } as const)[status]
}

export function documentWorkflowLabel(document: Pick<DocumentSummary, 'status' | 'reviewStatus'>) {
  if (document.status !== 'completed') return statusLabel(document.status)
  if (!document.reviewStatus) return 'Processed'
  return ({ queued: 'Needs review', in_progress: 'In officer review', approved: 'Approved', rejected: 'Rejected', sent_back: 'Sent back' } as const)[document.reviewStatus]
}

export function confidencePercent(value: number | null) {
  return value == null || !Number.isFinite(value) ? null : Math.round(Math.max(0, Math.min(1, value)) * 100)
}

export function confidenceTone(value: number | null) {
  const percent = confidencePercent(value)
  return percent == null ? 'neutral' : percent >= 85 ? 'success' : percent >= 60 ? 'warning' : 'danger'
}

export function fieldValue(field: ExtractedField) {
  if (field.value == null || field.value === '') return 'Missing'
  if (typeof field.value === 'number') return field.value.toLocaleString()
  if (typeof field.value === 'string') return field.value
  if (typeof field.value === 'boolean') return field.value ? 'Yes' : 'No'
  if (Array.isArray(field.value)) {
    if (field.value.length === 0) return 'None recorded'
    return field.value.map((entry) => {
      if (typeof entry === 'string' || typeof entry === 'number') return String(entry)
      if (entry && typeof entry === 'object') {
        const values = Object.values(entry as Record<string, unknown>).filter((value) => typeof value === 'string' || typeof value === 'number')
        return values.slice(0, 2).map(String).join(' · ') || 'Structured entry'
      }
      return 'Entry'
    }).join('; ')
  }
  if (typeof field.value === 'object') {
    const record = field.value as Record<string, unknown>
    if (Array.isArray(record.owners) && record.owners.length > 0) return record.owners.map(String).join(', ')
    const parts = Object.entries(record).filter(([, value]) => value !== null && value !== '' && !Array.isArray(value) && typeof value !== 'object')
    return parts.slice(0, 3).map(([key, value]) => `${fieldLabel(key)}: ${String(value)}`).join(' · ') || 'Structured details available'
  }
  return String(field.value)
}

export function fieldLabel(field: string) { return FIELD_LABELS[field] ?? field.replace(/([A-Z])/g, ' $1').replace(/^./, (letter) => letter.toUpperCase()) }

export function routeLabel(route: string | null | undefined) {
  if (!route) return 'Pending validation'
  if (route === 'approved') return 'Checks passed · officer verification pending'
  if (route === 'rejected') return 'Below quality threshold'
  if (route === 'human_review') return 'Human review required'
  return route.replaceAll('_', ' ').replaceAll('-', ' ').toLowerCase().replace(/^./, (letter) => letter.toUpperCase())
}

export function qualityScoreLabel(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '—'
  if (Number.isInteger(value)) return String(value)
  const rounded = Number(value.toFixed(1))
  return Math.floor(rounded) > Math.floor(value) ? String(value) : rounded.toFixed(1)
}

export function reviewRecordId(document: { status: string; validation: unknown; extraction: Record<string, unknown> | null }): string | null {
  const id = document.extraction?.recordId
  return document.status === 'completed' && Boolean(document.validation) && typeof id === 'string' ? id : null
}
