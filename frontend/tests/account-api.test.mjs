import assert from 'node:assert/strict'
import test from 'node:test'
import { forgotPassword, resendVerification, resetPassword, signup, verifyEmail } from '../src/features/auth/accountApi.ts'

test('account calls use the agreed API routes and send action tokens only in JSON bodies', async () => {
  const calls = []
  const originalFetch = globalThis.fetch
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options })
    const action = url.split('/').at(-1)
    return new Response(JSON.stringify(action === 'signup'
      ? { message: 'Check your email.', role: 'VERIFIER', requestedRole: 'VERIFIER', roleApprovalStatus: null }
      : { message: 'Request processed.' }), {
      status: action === 'verify-email' || action === 'reset-password' ? 200 : 202,
      headers: { 'Content-Type': 'application/json' },
    })
  }
  try {
    await signup({ fullName: ' Asha Rao ', username: ' ASHA.Rao ', email: ' Asha@Example.Test ', password: 'StrongPassword1!', confirmPassword: 'StrongPassword1!', requestedRole: 'VERIFIER' })
    await verifyEmail('secret-verification-token')
    await resendVerification(' Asha@Example.Test ')
    await forgotPassword(' Asha@Example.Test ')
    await resetPassword('secret-reset-token', 'UpdatedPassword1!', 'UpdatedPassword1!')
  } finally { globalThis.fetch = originalFetch }

  assert.deepEqual(calls.map((call) => call.url), [
    '/api/v1/auth/signup', '/api/v1/auth/verify-email', '/api/v1/auth/resend-verification',
    '/api/v1/auth/forgot-password', '/api/v1/auth/reset-password',
  ])
  const bodies = calls.map((call) => JSON.parse(call.options.body))
  assert.equal(bodies[0].username, 'asha.rao')
  assert.equal(bodies[0].email, 'asha@example.test')
  assert.equal(bodies[0].requestedRole, 'VERIFIER')
  assert.deepEqual(bodies[1], { token: 'secret-verification-token' })
  assert.deepEqual(bodies[4], { token: 'secret-reset-token', password: 'UpdatedPassword1!', confirmPassword: 'UpdatedPassword1!' })
  assert.equal(calls.every((call) => call.options.method === 'POST'), true)
  assert.equal(calls.every((call) => !call.url.includes('token')), true)
})

test('account API keeps SMTP and token failures visible instead of reporting success', async () => {
  const originalFetch = globalThis.fetch
  try {
    globalThis.fetch = async () => new Response(JSON.stringify({ detail: 'Email delivery is not configured.' }), { status: 503, headers: { 'Content-Type': 'application/json' } })
    await assert.rejects(() => signup({ fullName: 'Asha Rao', username: 'asha', email: 'asha@example.test', password: 'StrongPassword1!', confirmPassword: 'StrongPassword1!', requestedRole: 'AUDITOR' }), /Email delivery is not configured/)
    globalThis.fetch = async () => new Response(JSON.stringify({ detail: 'This verification link is invalid or expired.' }), { status: 400, headers: { 'Content-Type': 'application/json' } })
    await assert.rejects(() => verifyEmail('invalid-token'), /invalid or expired/)
    globalThis.fetch = async () => new Response(JSON.stringify({ detail: 'An account with these details already exists.' }), { status: 409, headers: { 'Content-Type': 'application/json' } })
    await assert.rejects(() => signup({ fullName: 'Asha Rao', username: 'asha', email: 'asha@example.test', password: 'StrongPassword1!', confirmPassword: 'StrongPassword1!', requestedRole: 'AUDITOR' }), /already exists/)
  } finally { globalThis.fetch = originalFetch }
})

test('verification reports an unreachable backend and HTML proxy errors clearly', async () => {
  const originalFetch = globalThis.fetch
  try {
    globalThis.fetch = async () => { throw new TypeError('Failed to fetch') }
    await assert.rejects(() => verifyEmail('qa_fixture'), /account service could not be reached/)
    globalThis.fetch = async () => new Response('<html>Proxy unavailable</html>', { status: 502 })
    await assert.rejects(() => verifyEmail('qa_fixture'), /HTTP 502/)
  } finally { globalThis.fetch = originalFetch }
})

test('signup distinguishes unavailable proxy responses from safe backend email and database errors', async () => {
  const originalFetch = globalThis.fetch
  const values = { fullName: 'Asha Rao', username: 'asha', email: 'asha@example.test', password: 'StrongPassword1!', confirmPassword: 'StrongPassword1!', requestedRole: 'AUDITOR' }
  try {
    for (const status of [500, 502, 503, 504]) {
      globalThis.fetch = async () => new Response('<html>internal proxy diagnostics</html>', { status, headers: { 'Content-Type': 'text/html' } })
      await assert.rejects(() => signup(values), (error) => {
        assert.match(error.message, /account service is temporarily unavailable/)
        assert.match(error.message, new RegExp(`HTTP ${status}`))
        assert.doesNotMatch(error.message, /internal proxy diagnostics|Email delivery/)
        return true
      })
    }
    for (const detail of [
      'Email delivery is not configured.',
      'Email service authentication failed. Please contact the administrator.',
      'Email delivery failed. Please try again later.',
      'The account database is temporarily unavailable. Please try again later.',
    ]) {
      globalThis.fetch = async () => new Response(JSON.stringify({ detail }), { status: 503, headers: { 'Content-Type': 'application/json' } })
      await assert.rejects(() => signup(values), (error) => error.message === detail)
    }
  } finally { globalThis.fetch = originalFetch }
})

test('signup does not treat an HTML frontend fallback as a successful API signup', async () => {
  const originalFetch = globalThis.fetch
  try {
    globalThis.fetch = async () => new Response('<html>BhuDrishti</html>', { status: 200, headers: { 'Content-Type': 'text/html' } })
    await assert.rejects(() => signup({ fullName: 'Asha Rao', username: 'asha', email: 'asha@example.test', password: 'StrongPassword1!', confirmPassword: 'StrongPassword1!', requestedRole: 'VERIFIER' }), /account service returned an unexpected response/)
  } finally { globalThis.fetch = originalFetch }
})

test('invalid signup data retains the backend validation message', async () => {
  const originalFetch = globalThis.fetch
  try {
    globalThis.fetch = async () => new Response(JSON.stringify({ detail: [{ msg: 'Value error, Passwords do not match.' }] }), { status: 422, headers: { 'Content-Type': 'application/json' } })
    await assert.rejects(() => signup({ fullName: 'Asha Rao', username: 'asha', email: 'asha@example.test', password: 'StrongPassword1!', confirmPassword: 'MismatchPassword1!', requestedRole: 'VERIFIER' }), (error) => error.message === 'Passwords do not match.')
  } finally { globalThis.fetch = originalFetch }
})

test('account actions require the correct HTTP status and a confirmed JSON message', async () => {
  const originalFetch = globalThis.fetch
  try {
    const invalidResponses = [
      () => new Response(null, { status: 202 }),
      () => new Response(JSON.stringify({ success: true }), { status: 202, headers: { 'Content-Type': 'application/json' } }),
      () => new Response(JSON.stringify({ message: '' }), { status: 202, headers: { 'Content-Type': 'application/json' } }),
      () => new Response('not json', { status: 202, headers: { 'Content-Type': 'application/json' } }),
      () => new Response(JSON.stringify({ message: 'Unexpected backend action.' }), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    ]
    for (const makeResponse of invalidResponses) {
      globalThis.fetch = async () => makeResponse()
      await assert.rejects(() => forgotPassword('asha@example.test'), /unexpected response/)
    }
    globalThis.fetch = async () => new Response(JSON.stringify({ message: 'Request accepted.' }), { status: 202, headers: { 'Content-Type': 'application/json' } })
    await assert.rejects(() => verifyEmail('qa-fixture-token'), /unexpected response/)
    await assert.rejects(() => resetPassword('qa-fixture-token', 'UpdatedPassword1!', 'UpdatedPassword1!'), /unexpected response/)
  } finally { globalThis.fetch = originalFetch }
})

test('signup requires its requested role to be confirmed by the existing response contract', async () => {
  const originalFetch = globalThis.fetch
  const values = { fullName: 'Asha Rao', username: 'asha', email: 'asha@example.test', password: 'StrongPassword1!', confirmPassword: 'StrongPassword1!', requestedRole: 'ADMIN' }
  try {
    for (const payload of [
      { message: 'Created.' },
      { message: 'Created.', role: 'UNKNOWN', requestedRole: 'ADMIN', roleApprovalStatus: 'PENDING' },
      { message: 'Created.', role: 'AUDITOR', requestedRole: 'AUDITOR', roleApprovalStatus: 'PENDING' },
      { message: 'Created.', role: 'AUDITOR', requestedRole: 'ADMIN', roleApprovalStatus: 'UNKNOWN' },
    ]) {
      globalThis.fetch = async () => new Response(JSON.stringify(payload), { status: 202, headers: { 'Content-Type': 'application/json' } })
      await assert.rejects(() => signup(values), /unexpected response/)
    }
    globalThis.fetch = async () => new Response(JSON.stringify({ message: 'Check your email.', role: 'AUDITOR', requestedRole: 'ADMIN', roleApprovalStatus: 'PENDING' }), { status: 202, headers: { 'Content-Type': 'application/json; charset=utf-8' } })
    await signup(values)
  } finally { globalThis.fetch = originalFetch }
})

test('recovery and resend never report success after a backend email failure', async () => {
  const originalFetch = globalThis.fetch
  try {
    globalThis.fetch = async () => new Response(JSON.stringify({ detail: 'The email service is temporarily unreachable. Please try again later.' }), { status: 503, headers: { 'Content-Type': 'application/json' } })
    await assert.rejects(() => forgotPassword('asha@example.test'), /temporarily unreachable/)
    await assert.rejects(() => resendVerification('asha@example.test'), /temporarily unreachable/)
    globalThis.fetch = async () => new Response(JSON.stringify({ detail: 'This reset link is invalid, expired, or already used.' }), { status: 400, headers: { 'Content-Type': 'application/json' } })
    await assert.rejects(() => resetPassword('qa-fixture-token', 'UpdatedPassword1!', 'UpdatedPassword1!'), /invalid, expired, or already used/)
  } finally { globalThis.fetch = originalFetch }
})
