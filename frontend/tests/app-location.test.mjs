import assert from 'node:assert/strict'
import test from 'node:test'
import { appLocation } from '../config/appLocation.ts'

test('default frontend URL binds the exact localhost email origin', () => {
  assert.deepEqual(appLocation(), { host: 'localhost', port: 5173, origin: 'http://localhost:5173', base: '/' })
})

test('explicit QA port and deployed path are respected', () => {
  assert.deepEqual(appLocation('http://localhost:5174/'), { host: 'localhost', port: 5174, origin: 'http://localhost:5174', base: '/' })
  assert.deepEqual(appLocation('https://records.example.test/land/'), { host: 'records.example.test', port: 443, origin: 'https://records.example.test', base: '/land/' })
})

test('invalid and token-bearing app URLs fail configuration before startup', () => {
  for (const value of ['', 'localhost:5173', 'file:///tmp/app', 'http://user:password@localhost:5173', 'http://localhost:5173/?token=secret', 'http://localhost:5173/#/verify-email', ' http://localhost:5173']) {
    assert.throws(() => appLocation(value), /VITE_APP_URL/)
  }
})
