import assert from 'node:assert/strict'
import test from 'node:test'
import { passwordError, validateReset, validateSignup, validEmail } from '../src/features/auth/accountValidation.ts'
import { publicAuthRoute } from '../src/features/auth/publicRoutes.ts'

const validSignup = {
  fullName: 'Asha Rao', username: 'Asha.Rao_1', email: 'asha@example.test',
  password: 'StrongPassword1!', confirmPassword: 'StrongPassword1!', requestedRole: 'REVENUE_OFFICER',
}

test('account route parser recognizes public hash routes with token queries', () => {
  assert.equal(publicAuthRoute('#/verify-email?token=secret'), 'verify-email')
  assert.equal(publicAuthRoute('#/reset-password?token=secret'), 'reset-password')
  assert.equal(publicAuthRoute('#/forgot-password'), 'forgot-password')
  assert.equal(publicAuthRoute('#/signup'), 'signup')
  assert.equal(publicAuthRoute('#/login'), 'login')
  assert.equal(publicAuthRoute('#/documents'), null)
})

test('registration requires distinct passwords and backend-aligned username characters', () => {
  assert.deepEqual(validateSignup(validSignup), { password: undefined })
  assert.ok(validateSignup({ ...validSignup, username: '...' }).username)
  assert.ok(validateSignup({ ...validSignup, username: 'not valid' }).username)
  assert.ok(validateSignup({ ...validSignup, confirmPassword: 'StrongPassword2!' }).confirmPassword)
  assert.ok(validateSignup({ ...validSignup, fullName: 'A' }).fullName)
  assert.ok(validateSignup({ ...validSignup, email: 'invalid' }).email)
  assert.ok(validateSignup({ ...validSignup, requestedRole: '' }).requestedRole)
})

test('password recovery enforces the same password rule as signup', () => {
  assert.equal(passwordError(validSignup.password), undefined)
  assert.ok(passwordError('short'))
  assert.ok(passwordError('lowercaseonlypassword1!'))
  assert.ok(passwordError('UPPERCASEONLYPASSWORD1!'))
  assert.ok(passwordError('PasswordWithoutNumber!'))
  assert.ok(passwordError('PasswordWithoutSymbol1'))
  assert.equal(validateReset(validSignup.password, validSignup.password).confirmPassword, undefined)
  assert.ok(validateReset(validSignup.password, 'different').confirmPassword)
})

test('email validation rejects malformed and whitespace addresses', () => {
  assert.equal(validEmail(' asha@example.test '), true)
  assert.equal(validEmail('ashaexample.test'), false)
  assert.equal(validEmail('asha@ example.test'), false)
})

test('account email validation accepts bare aliases and rejects SMTP display or comment syntax', () => {
  for (const email of ['asha+qa@example.test', "o'connor@example.test", 'Asha.Rao@sub.example.test', 'asha@xn--bcher-kva.example']) {
    assert.equal(validEmail(email), true, email)
  }
  for (const email of [
    'foo<bar@example.test>', '(alias)bar@example.test', 'bar@example.test,',
    'bar@example.test;other@example.test', '"bar"@example.test',
    'bar@example.test\r\nBcc:other@example.test', 'bar@example..test',
    '.bar@example.test', 'bar..alias@example.test', 'bar.@example.test',
    'bar@-example.test', 'bar@example-.test', 'bar@example_test', 'bár@example.test',
    `${'a'.repeat(65)}@example.test`, `bar@${'a'.repeat(64)}.test`,
  ]) {
    assert.equal(validEmail(email), false, email)
    assert.ok(validateSignup({ ...validSignup, email }).email)
  }
})
