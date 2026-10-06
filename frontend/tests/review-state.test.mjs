import assert from 'node:assert/strict'
import test from 'node:test'
import { acceptedFieldValue, resolutionForIssue, isClearValidation } from '../src/features/review/reviewState.ts'

test('review values never present untouched or rejected AI output as officer accepted', () => {
  const field = { originalValue: 'AI owner', reviewedValue: 'Officer owner' }
  assert.equal(acceptedFieldValue({ ...field, reviewStatus: 'unreviewed' }), null)
  assert.equal(acceptedFieldValue({ ...field, reviewStatus: 'reject' }), null)
  assert.equal(acceptedFieldValue({ ...field, reviewStatus: 'edit' }), 'Officer owner')
  assert.equal(acceptedFieldValue({ ...field, reviewedValue: null, reviewStatus: 'accept' }), 'AI owner')
  assert.equal(acceptedFieldValue({ ...field, reviewedValue: null, reviewStatus: 'edit' }), null)
  assert.equal(acceptedFieldValue({ ...field, reviewedValue: 0, reviewStatus: 'edit' }), 0)
  assert.equal(field.originalValue, 'AI owner')
})

test('a record-level validation issue cannot borrow a field-level resolution', () => {
  const entries = [
    { issueCode: 'conflict', fieldName: 'ownerName', resolution: 'confirmed' },
    { issueCode: 'conflict', fieldName: null, resolution: 'not_applicable' },
  ]
  assert.equal(resolutionForIssue(entries, 'conflict', null)?.resolution, 'not_applicable')
  assert.equal(resolutionForIssue(entries, 'conflict', 'ownerName')?.resolution, 'confirmed')
  assert.equal(resolutionForIssue(entries, 'conflict', 'surveyNumber'), undefined)
  assert.equal(resolutionForIssue(entries, 'missing', null), undefined)
})

test('only an explicit backend validation result is shown as clear', () => {
  for (const status of ['clear', 'valid', 'PASS', 'passed']) assert.equal(isClearValidation(status), true)
  for (const status of ['', null, undefined, 'warning', 'pending', 'unavailable']) assert.equal(isClearValidation(status), false)
})
