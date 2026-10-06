import assert from 'node:assert/strict'
import test from 'node:test'
import { isRevenueOfficerPreviewRoute } from '../src/app/developmentRoutes.ts'

test('officer preview requires local development and its exact route', () => {
  const hash = '#/dev/revenue-officer'
  for (const host of ['localhost', '127.0.0.1', '[::1]', '::1']) {
    assert.equal(isRevenueOfficerPreviewRoute(hash, true, host), true)
    assert.equal(isRevenueOfficerPreviewRoute(hash, false, host), false)
  }
  assert.equal(isRevenueOfficerPreviewRoute(hash, true, 'app.example.test'), false)
  for (const route of ['#/dashboard', '#/signup', '#/login', '#/verify-email', '#/forgot-password', '#/reset-password', '#/dev/revenue-officer/other']) {
    assert.equal(isRevenueOfficerPreviewRoute(route, true, 'localhost'), false)
  }
})
