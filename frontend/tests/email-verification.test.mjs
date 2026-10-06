import assert from 'node:assert/strict'
import test from 'node:test'
import { accountLinkParameter, createEmailVerificationRequest } from '../src/features/auth/emailVerification.ts'

function deferred() {
  let resolve, reject
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}

test('verification reads the token from the hash query and decodes encoded values', () => {
  assert.equal(accountLinkParameter('#/verify-email?token=qa_fixture-123&email=user%2Bqa%40example.test', 'token'), 'qa_fixture-123')
  assert.equal(accountLinkParameter('#/verify-email?token=qa_fixture-123&email=user%2Bqa%40example.test', 'email'), 'user+qa@example.test')
  assert.equal(accountLinkParameter('#/verify-email', 'token'), '')
  assert.equal(accountLinkParameter('#/verify-email?email=user%40example.test', 'token'), '')
  assert.equal(accountLinkParameter('#/verify-email?token=%20%20', 'token'), '')
})

test('effect replay shares one verification call and only updates the active subscriber', async () => {
  const pending = deferred()
  const calls = []
  const request = createEmailVerificationRequest((value) => { calls.push(value); return pending.promise })
  const abandoned = [], active = []
  const stop = request('qa_fixture', (result) => abandoned.push(result))
  stop()
  request('qa_fixture', (result) => active.push(result))
  assert.equal(calls.length, 1)
  assert.deepEqual(active, [])
  pending.resolve()
  await pending.promise
  assert.deepEqual(abandoned, [])
  assert.deepEqual(active, [{ verified: true }])
})

test('a newer link cannot be overwritten by an older verification response', async () => {
  const oldRequest = deferred(), newRequest = deferred()
  const request = createEmailVerificationRequest((token) => token === 'old_qa_fixture' ? oldRequest.promise : newRequest.promise)
  const results = []
  const stop = request('old_qa_fixture', (result) => results.push(result))
  stop()
  request('new_qa_fixture', (result) => results.push(result))
  newRequest.resolve()
  await newRequest.promise
  oldRequest.reject(new Error('Expired fixture'))
  await oldRequest.promise.catch(() => {})
  assert.deepEqual(results, [{ verified: true }])
})

test('verification rejection preserves the backend error and never reports success', async () => {
  const failure = new Error('This verification link is invalid, expired, or already used.')
  const pending = deferred()
  const request = createEmailVerificationRequest(() => pending.promise)
  const results = []
  request('rejected_qa_fixture', (result) => results.push(result))
  pending.reject(failure)
  await pending.promise.catch(() => {})
  assert.deepEqual(results, [{ verified: false, error: failure }])
})

test('navigating away suppresses a completed verification update', async () => {
  const pending = deferred()
  const request = createEmailVerificationRequest(() => pending.promise)
  const results = []
  const stop = request('qa_fixture', (result) => results.push(result))
  stop()
  pending.resolve()
  await pending.promise
  assert.deepEqual(results, [])
})

test('reopening a completed link calls the backend again instead of reusing a past success', async () => {
  let calls = 0
  const results = []
  const request = createEmailVerificationRequest(async () => {
    calls += 1
    if (calls > 1) throw new Error('This verification link is already used.')
  })
  request('same_qa_fixture', (result) => results.push(result))
  await new Promise((resolve) => setImmediate(resolve))
  assert.deepEqual(results, [{ verified: true }])
  request('same_qa_fixture', (result) => results.push(result))
  await new Promise((resolve) => setImmediate(resolve))
  assert.equal(calls, 2)
  assert.equal(results[1].verified, false)
  assert.match(results[1].error.message, /already used/)
})
