import assert from 'node:assert/strict'
import test from 'node:test'
import { recordedProcessingDuration, recordedStageDuration } from '../src/features/live/pipeline.ts'
import { readProcessingSnapshot } from '../src/features/live/polling.ts'
import { isNormalizedBox } from '../src/features/live/evidence.ts'

test('new server stage refreshes page and extraction evidence before terminal state', async () => {
  const detail = { id: 'source', status: 'processing', stage: 'ocr', pages: [{ pageNumber: 1 }], fields: [] }
  const snapshot = await readProcessingSnapshot('source', async () => ({ status: 'processing', stage: 'ocr', updatedAt: '2026-09-26T10:00:02Z' }), async () => detail, '2026-09-26T10:00:01Z')
  assert.equal(snapshot.kind, 'progress')
  assert.equal(snapshot.document.pages[0].pageNumber, 1)
})

test('unchanged server state does not reload full document payload', async () => {
  let reads = 0
  const snapshot = await readProcessingSnapshot('source', async () => ({ status: 'processing', stage: 'ocr', updatedAt: '2026-09-26T10:00:02Z' }), async () => { reads++; return {} }, '2026-09-26T10:00:02Z')
  assert.equal(reads, 0)
  assert.equal(snapshot.kind, 'progress')
})

test('a job finishing between status and detail requests publishes terminal evidence', async () => {
  const snapshot = await readProcessingSnapshot('source', async () => ({ status: 'processing', stage: 'validation', updatedAt: 'new' }), async () => ({ status: 'completed', fields: [{ value: 'Source value' }] }), 'old')
  assert.equal(snapshot.kind, 'terminal')
  assert.equal(snapshot.document.fields[0].value, 'Source value')
})

test('processing duration uses server timestamps and excludes intake wait or later edits', () => {
  const stages = [
    { stage: 'upload', startedAt: '2026-09-26T08:00:00Z', completedAt: '2026-09-26T08:00:01Z' },
    { stage: 'preprocessing', startedAt: '2026-09-26T10:00:00Z', completedAt: '2026-09-26T10:00:02Z' },
    { stage: 'ocr', startedAt: '2026-09-26T10:00:02Z', completedAt: '2026-09-26T10:00:10Z' },
  ]
  assert.equal(recordedProcessingDuration({ status: 'completed', updatedAt: '2026-09-26T12:00:00Z', stages }), 10000)
  assert.equal(recordedStageDuration(stages[2]), 8000)
  assert.equal(recordedStageDuration({ startedAt: 'invalid', completedAt: 'invalid' }), null)
  assert.equal(recordedStageDuration({ startedAt: '2026-09-26T10:00:02Z' }), null)
  assert.equal(recordedProcessingDuration({ status: 'uploaded', stages: [] }), null)
})

test('only genuine normalized source boxes may be rendered', () => {
  assert.equal(isNormalizedBox([.1, .2, .5, .1]), true)
  assert.equal(isNormalizedBox([0, 0, 1, 1]), true)
  for (const box of [null, [120, 30, 60, 10], [-.1, 0, .2, .2], [.9, 0, .2, .2], [0, 0, 0, 1], [NaN, 0, 1, 1]]) assert.equal(isNormalizedBox(box), false)
})
