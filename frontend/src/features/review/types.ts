import type { DocumentDetail, ValidationResult } from '../live/types'

export type ReviewRole = 'ADMIN' | 'REVENUE_OFFICER' | 'VERIFIER' | 'AUDITOR' | string
export type ReviewAction = 'accept' | 'edit' | 'reject'
export type ReviewDecision = 'approve' | 'reject' | 'send_back'
export type ReviewStatus = 'queued' | 'in_progress' | 'approved' | 'rejected' | 'sent_back' | string
export type ReviewPriority = 'high' | 'medium' | 'low' | string

export interface ReviewUser {
  id: string
  name: string
  role: ReviewRole
}

export interface ReviewCaseSummary {
  recordId: string
  recordNumber: string | null
  documentId: string
  documentName: string
  ownerName: string | null
  surveyNumber: string | null
  qualityScore: number
  validationStatus: string
  primaryConflict: string | null
  submittedAt: string
  priority: ReviewPriority
  priorityReasons: string[]
  assignedOfficer: ReviewUser | null
  status: ReviewStatus
}

export interface ReviewFieldSource {
  sourcePage?: number
  boundingBox?: [number, number, number, number] | null
  extractedText?: string | null
  extractionMethod?: string | null
  page?: number
  bbox?: [number, number, number, number] | null
  text?: string | null
}

export interface ReviewField {
  field: string
  originalValue: unknown
  reviewedValue: unknown
  confidence: number | null
  source: ReviewFieldSource | null
  reviewStatus: 'unreviewed' | 'accept' | 'edit' | 'reject' | string
  referenceValue?: unknown
  validationStatus: string
  reason?: string | null
  reviewer?: ReviewUser | null
  reviewedAt?: string | null
}

export interface ReviewSummary {
  fieldsReviewed: number
  fieldsTotal: number
  warningsResolved: number
  warningsTotal: number
  criticalConflicts: number
  canApprove: boolean
  blockingReasons: string[]
}

export interface IssueResolution {
  issueCode: string
  fieldName: string | null
  resolution: 'corrected' | 'confirmed' | 'not_applicable'
  reason: string
  actorId: string
  timestamp: string
}

export interface ReviewCaseDetail extends ReviewCaseSummary {
  originalRecord: Record<string, unknown>
  reviewedRecord: Record<string, unknown>
  fields: ReviewField[]
  validation: ValidationResult | null
  summary: ReviewSummary
  issueResolutions: IssueResolution[]
  recommendation: Record<string, unknown> | null
  gisIndexed: boolean
  gisParcelId: string | null
  startedAt: string | null
  decidedAt: string | null
  decidedBy: ReviewUser | null
  decisionReason: string | null
}

export type ReviewDocument = DocumentDetail

export const QUEUE_FILTERS = [
  { value: 'all', label: 'All' },
  { value: 'high_priority', label: 'High priority' },
  { value: 'low_confidence', label: 'Low confidence' },
  { value: 'conflicts', label: 'Conflicts' },
  { value: 'missing_fields', label: 'Missing fields' },
  { value: 'assigned_to_me', label: 'Assigned to me' },
  { value: 'unassigned', label: 'Unassigned' },
] as const

export type QueueFilter = (typeof QUEUE_FILTERS)[number]['value']
export type QueueSort = 'submitted_at' | 'quality_score' | 'priority'
