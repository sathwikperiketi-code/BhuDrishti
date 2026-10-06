import type { DocumentDetail, ProcessingStage, StageEntry, StageStatus } from './types'

export const STAGE_STATUS_LABELS: Record<StageStatus, string> = {
  pending: 'Waiting', running: 'Processing', completed: 'Completed', failed: 'Failed', unavailable: 'History unavailable',
}

export function recordedStageDuration(stage: StageEntry | undefined): number | null {
  if (!stage?.startedAt || !stage.completedAt) return null
  const duration = Date.parse(stage.completedAt) - Date.parse(stage.startedAt)
  return Number.isFinite(duration) && duration >= 0 ? duration : null
}

/** Excludes the time the stored file spent waiting for processing to start. */
export function recordedProcessingDuration(document: Pick<DocumentDetail, 'status' | 'stages' | 'updatedAt'>): number | null {
  const starts = document.stages.filter((stage) => stage.stage !== 'upload' && stage.startedAt).map((stage) => Date.parse(stage.startedAt!)).filter(Number.isFinite)
  const ends = [document.status === 'processing' ? document.updatedAt : null, ...document.stages.filter((stage) => stage.stage !== 'upload').map((stage) => stage.completedAt)]
    .filter((value): value is string => Boolean(value)).map((value) => Date.parse(value)).filter(Number.isFinite)
  if (!starts.length || !ends.length) return null
  const duration = Math.max(...ends) - Math.min(...starts)
  return duration >= 0 ? duration : null
}

export function durationLabel(milliseconds: number): string {
  if (milliseconds < 1000) return `${Math.round(milliseconds)} ms`
  if (milliseconds < 60000) return `${(milliseconds / 1000).toFixed(1)} s`
  return `${Math.floor(milliseconds / 60000)}m ${Math.floor(milliseconds % 60000 / 1000)}s`
}

export interface PipelineStep {
  id: string
  label: string
  short: string
  detail: string
  backendStage: ProcessingStage
  validationLayer?: 'field' | 'record' | 'cross_system'
}

export const PIPELINE_STEPS: PipelineStep[] = [
  { id: 'document_received', label: 'Document received', short: 'Received', detail: 'The source file was stored for processing.', backendStage: 'upload' },
  { id: 'preprocessing', label: 'Preprocessing', short: 'Prepare', detail: 'Pages are rendered for recognition.', backendStage: 'preprocessing' },
  { id: 'ocr', label: 'Text extraction / OCR', short: 'Text', detail: 'Embedded PDF text is extracted, or OCR runs when needed.', backendStage: 'ocr' },
  { id: 'field_extraction', label: 'Field extraction', short: 'Extract', detail: 'Candidates map to land-record fields.', backendStage: 'field_extraction' },
  { id: 'normalization', label: 'Normalization', short: 'Normalize', detail: 'Dates, numbers, and locations take consistent forms.', backendStage: 'normalization' },
  { id: 'field_validation', label: 'Field validation', short: 'Fields', detail: 'Individual field values and confidence are checked.', backendStage: 'validation', validationLayer: 'field' },
  { id: 'record_validation', label: 'Record validation', short: 'Record', detail: 'Required fields and internal consistency are checked.', backendStage: 'validation', validationLayer: 'record' },
  { id: 'cross_system_validation', label: 'Cross-system validation', short: 'Reference', detail: 'Available local reference records are compared.', backendStage: 'validation', validationLayer: 'cross_system' },
  { id: 'quality_score', label: 'Quality score', short: 'Score', detail: 'Weighted checks produce a transparent score.', backendStage: 'quality_score' },
  { id: 'routing', label: 'Final routing', short: 'Route', detail: 'The result is routed for officer review or a decision path.', backendStage: 'final_routing' },
]

export function pipelineStepStatus(document: Pick<DocumentDetail, 'status' | 'stage' | 'stages' | 'validation'>, step: PipelineStep): StageStatus {
  const entry = document.stages.find((stage) => stage.stage === step.backendStage)
  if (entry) return entry.status
  if (document.status === 'uploaded') return step.backendStage === 'upload' ? 'completed' : 'pending'
  if (document.stage === step.backendStage && document.status === 'processing') return 'running'
  if (document.stage === step.backendStage && document.status === 'failed') return 'failed'
  return 'unavailable'
}

export function completedPipelineCount(document: Pick<DocumentDetail, 'status' | 'stage' | 'stages' | 'validation'>) {
  return PIPELINE_STEPS.filter((step) => pipelineStepStatus(document, step) === 'completed').length
}
