import assert from 'node:assert/strict'
import test from 'node:test'
import { sampleDocumentAfterOperational404 } from '../src/features/live/samplePromotion.ts'

test('only a matching sample document turns an operational 404 into a dataset move', async () => {
  const lookedUp = []
  const readSample = async (id) => {
    lookedUp.push(id)
    return { datasetScope: id === 'promoted-id' ? 'sample' : 'operational' }
  }
  assert.equal(await sampleDocumentAfterOperational404('promoted-id', { status: 404 }, readSample), true)
  assert.deepEqual(lookedUp, ['promoted-id'])
  assert.equal(await sampleDocumentAfterOperational404('other-id', { status: 404 }, readSample), false)
  assert.equal(await sampleDocumentAfterOperational404('promoted-id', { status: 500 }, readSample), false)
  assert.deepEqual(lookedUp, ['promoted-id', 'other-id'], 'non-404 errors must not query the sample dataset')
})

test('an unrelated operational 404 keeps its error when the sample lookup also fails', async () => {
  assert.equal(await sampleDocumentAfterOperational404('missing-id', { status: 404 }, async () => { throw new Error('Not found') }), false)
  assert.equal(await sampleDocumentAfterOperational404('missing-id', new Error('Connection failed'), async () => ({ datasetScope: 'sample' })), false)
})
