import assert from 'node:assert/strict'
import test from 'node:test'
import { registrationRoleLabel, registrationRoles } from '../src/features/auth/registrationRoles.ts'
import { routeAvailableForRole } from '../src/app/navigation.ts'

test('registration offers four distinct requested roles and marks administrator access as a request', () => {
  assert.deepEqual(registrationRoles.map((item) => item.value), ['REVENUE_OFFICER', 'VERIFIER', 'AUDITOR', 'ADMIN'])
  assert.equal(registrationRoleLabel('REVENUE_OFFICER'), 'Revenue Officer')
  assert.equal(registrationRoleLabel(''), '')
  assert.match(registrationRoles.find((item) => item.value === 'ADMIN').action, /^Request /)
})

test('navigation follows the backend role while keeping auditor evidence available', () => {
  assert.equal(routeAvailableForRole('processing', 'REVENUE_OFFICER'), true)
  assert.equal(routeAvailableForRole('processing', 'VERIFIER'), false)
  assert.equal(routeAvailableForRole('validation', 'VERIFIER'), true)
  assert.equal(routeAvailableForRole('validation', 'AUDITOR'), true)
  assert.equal(routeAvailableForRole('processing', 'AUDITOR'), false)
  assert.equal(routeAvailableForRole('audit', 'AUDITOR'), true)
  assert.equal(routeAvailableForRole('processing', 'ADMIN'), true)
  assert.equal(routeAvailableForRole('dashboard', 'UNTRUSTED'), false)
})
