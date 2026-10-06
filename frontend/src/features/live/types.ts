export type LiveView = 'document' | 'processing' | 'validation'
export type DatasetScope = 'operational' | 'sample'

export type ProcessingStage =
  | 'upload'
  | 'preprocessing'
  | 'ocr'
  | 'field_extraction'
  | 'normalization'
  | 'validation'
  | 'quality_score'
  | 'final_routing'

export type DocumentStatus = 'uploaded' | 'processing' | 'completed' | 'failed'
export type ReviewStatus = 'queued' | 'in_progress' | 'approved' | 'rejected' | 'sent_back'
export type StageStatus = 'pending' | 'running' | 'completed' | 'failed' | 'unavailable'

export interface DocumentError { code: string; message: string }

export interface DocumentSummary {
  id: string
  fileName: string
  mimeType: string
  fileSize: number
  pageCount: number
  language: string | null
  uploadedAt: string
  status: DocumentStatus
  reviewStatus?: ReviewStatus | null
  stage: ProcessingStage | null
  provider: string | null
  isSynthetic: boolean
  datasetScope: DatasetScope
  datasetReason: string | null
}

export interface DocumentPage {
  pageNumber: number
  imageUrl: string
  width: number
  height: number
}

export interface FieldEvidence {
  page: number
  bbox: [number, number, number, number] | null
  text?: string | null
}

export interface ExtractedField {
  field: string
  value: unknown
  confidence: number | null
  source: FieldEvidence | null
  extractionMethod?: string | null
  warnings: string[]
}

export interface StageEntry {
  stage: ProcessingStage
  status: StageStatus
  startedAt?: string | null
  completedAt?: string | null
  message?: string | null
}

export interface ValidationIssue {
  level: 'field' | 'record' | 'cross_system'
  code: string
  message: string
  fieldName: string | null
  severity: string
  expected: unknown
  actual: unknown
}

export interface ValidationResult {
  fieldScore: number
  recordScore: number
  crossSystemScore: number
  qualityScore: number
  routing: string
  issues: ValidationIssue[]
  generatedAt: string
}

export interface ScoreBreakdown {
  fieldWeight: number
  recordWeight: number
  crossSystemWeight: number
  fieldContribution: number
  recordContribution: number
  crossSystemContribution: number
  warningPenalty: number
  unroundedTotal: number
  qualityScore: number
  rejectBelow: number
  approveAtOrAbove: number
  routing: string
}

export interface DocumentDetail extends DocumentSummary {
  updatedAt?: string
  processedAt?: string | null
  pages: DocumentPage[]
  ocrPages: { pageNumber: number; text: string; regions: { text: string; bbox: number[]; confidence?: number | null }[] }[]
  extraction: Record<string, unknown> | null
  fields: ExtractedField[]
  validation: ValidationResult | null
  scoreBreakdown: ScoreBreakdown | null
  warnings: string[]
  processingMetadata: Record<string, unknown> | null
  error: DocumentError | null
  stages: StageEntry[]
}

export interface ProcessingStatusResponse {
  id: string
  status: DocumentStatus
  stage: ProcessingStage | null
  attempts: number
  stages: StageEntry[]
  error: DocumentError | null
  updatedAt: string
}
