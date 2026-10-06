import assert from 'node:assert/strict'
import test from 'node:test'
import { PIPELINE_STEPS, completedPipelineCount, pipelineStepStatus } from '../src/features/live/pipeline.ts'
import { qualityScoreLabel, confidencePercent, documentWorkflowLabel, reviewRecordId } from '../src/features/live/format.ts'
import { applyTerminalDocument, readProcessingSnapshot } from '../src/features/live/polling.ts'
import { MAX_UPLOAD_BYTES, validateUploadFile } from '../src/features/live/uploadValidation.ts'

test('processing strip reflects persisted stage entries and does not invent missing completions', () => {
  const uploaded = { status: 'uploaded', stage: 'upload', validation: null, stages: [] }
  assert.equal(pipelineStepStatus(uploaded, PIPELINE_STEPS[0]), 'completed')
  assert.equal(pipelineStepStatus(uploaded, PIPELINE_STEPS[2]), 'pending')

  const processing = {
    status: 'processing', stage: 'ocr', validation: null,
    stages: [
      { stage: 'upload', status: 'completed' },
      { stage: 'preprocessing', status: 'completed' },
      { stage: 'ocr', status: 'running' },
    ],
  }
  assert.equal(pipelineStepStatus(processing, PIPELINE_STEPS[1]), 'completed')
  assert.equal(pipelineStepStatus(processing, PIPELINE_STEPS[2]), 'running')
  assert.equal(pipelineStepStatus(processing, PIPELINE_STEPS[3]), 'unavailable')
  assert.equal(completedPipelineCount(processing), 2)

  const completeWithoutHistory = { status: 'completed', stage: 'final_routing', validation: null, stages: [] }
  assert.equal(pipelineStepStatus(completeWithoutHistory, PIPELINE_STEPS[2]), 'unavailable')
  assert.equal(completedPipelineCount(completeWithoutHistory), 0)
})

test('display keeps backend score below threshold and shows unmeasured confidence', () => {
  assert.equal(qualityScoreLabel(59.5), '59.5')
  assert.equal(qualityScoreLabel(59.95), '59.95')
  assert.equal(qualityScoreLabel(60), '60')
  assert.equal(qualityScoreLabel(null), '—')
  assert.equal(confidencePercent(null), null)
})

test('terminal polling waits for persisted detail and updates the document list', async () => {
  let resolveDetail
  const pending = readProcessingSnapshot(
    'record-1',
    async () => ({ id: 'record-1', status: 'completed', stage: 'final_routing', stages: [], error: null }),
    () => new Promise((resolve) => { resolveDetail = resolve }),
  )
  let settled = false
  void pending.then(() => { settled = true })
  await new Promise((resolve) => setImmediate(resolve))
  assert.equal(settled, false, 'terminal state must not publish before full detail is fetched')
  const detail = { id: 'record-1', status: 'completed', stage: 'final_routing', fields: [{ field: 'surveyNumber', value: '142/3A' }] }
  resolveDetail(detail)
  const snapshot = await pending
  assert.equal(snapshot.kind, 'terminal')
  assert.equal(snapshot.document.fields[0].value, '142/3A')
  const list = applyTerminalDocument([{ id: 'record-1', status: 'processing' }, { id: 'record-2', status: 'uploaded' }], snapshot.document)
  assert.equal(list[0].status, 'completed')
  assert.equal(list[1].status, 'uploaded')
})

test('all completed scored routes expose the persisted officer review case', () => {
  for (const routing of ['approved', 'human_review', 'rejected']) {
    assert.equal(reviewRecordId({ status: 'completed', validation: { routing }, extraction: { recordId: 'record-1' } }), 'record-1')
  }
  assert.equal(reviewRecordId({ status: 'processing', validation: null, extraction: { recordId: 'record-1' } }), null)
})

test('upload validation accepts supported sources and rejects unsafe or empty inputs', () => {
  assert.equal(validateUploadFile({ name: 'record.pdf', type: 'application/pdf', size: 1024 }), null)
  assert.equal(validateUploadFile({ name: 'scan.jpeg', type: 'image/jpeg', size: 1024 }), null)
  assert.equal(validateUploadFile({ name: 'source.png', type: 'image/png', size: MAX_UPLOAD_BYTES }), null)
  assert.match(validateUploadFile({ name: 'source.exe', type: 'application/octet-stream', size: 1024 }), /Choose a PDF/)
  assert.match(validateUploadFile({ name: 'source.pdf', type: 'image/png', size: 1024 }), /Choose a PDF/)
  assert.match(validateUploadFile({ name: 'empty.pdf', type: 'application/pdf', size: 0 }), /empty/)
  assert.match(validateUploadFile({ name: 'large.pdf', type: 'application/pdf', size: MAX_UPLOAD_BYTES + 1 }), /20 MB/)
})

test('document labels use persisted review outcomes only after processing completes', () => {
  assert.equal(documentWorkflowLabel({ status: 'uploaded', reviewStatus: null }), 'Ready to process')
  assert.equal(documentWorkflowLabel({ status: 'processing', reviewStatus: 'queued' }), 'Processing')
  assert.equal(documentWorkflowLabel({ status: 'completed', reviewStatus: null }), 'Processed')
  assert.equal(documentWorkflowLabel({ status: 'completed', reviewStatus: 'queued' }), 'Needs review')
  assert.equal(documentWorkflowLabel({ status: 'completed', reviewStatus: 'approved' }), 'Approved')
  assert.equal(documentWorkflowLabel({ status: 'completed', reviewStatus: 'sent_back' }), 'Sent back')
  assert.equal(documentWorkflowLabel({ status: 'failed', reviewStatus: 'approved' }), 'Processing failed')
})
