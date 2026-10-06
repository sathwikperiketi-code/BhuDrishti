import assert from 'node:assert/strict'
import test from 'node:test'
import { belongsToDataset, datasetPath } from '../src/features/live/dataset.ts'

test('document read paths explicitly scope operational and sample datasets', () => {
  assert.equal(datasetPath('/documents', 'operational'), '/documents?dataset=operational')
  assert.equal(datasetPath('/documents/id/pages/1/image', 'sample'), '/documents/id/pages/1/image?dataset=sample')
})

test('missing or mismatched dataset classification fails closed', () => {
  assert.equal(belongsToDataset({ datasetScope: 'operational' }, 'operational'), true)
  assert.equal(belongsToDataset({ datasetScope: 'sample' }, 'sample'), true)
  assert.equal(belongsToDataset({ datasetScope: 'sample' }, 'operational'), false)
  assert.equal(belongsToDataset({}, 'sample'), false)
  assert.equal(belongsToDataset({}, 'operational'), false)
})
