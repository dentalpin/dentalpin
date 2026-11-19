import { test } from 'node:test'
import assert from 'node:assert/strict'
import { safeUrl, validClinicId } from '../src/helpers.js'

test('clinic UUID must be configured and must be valid', () => {
  assert.equal(validClinicId('11111111-1111-4111-8111-111111111111'), true)
  assert.equal(validClinicId('00000000-0000-4000-8000-000000000000'), false)
  assert.equal(validClinicId('../bad'), false)
})
test('links require HTTPS, except for localhost development', () => {
  assert.equal(safeUrl('https://example.com/privacy', 'https://booking.example.com/'), 'https://example.com/privacy')
  assert.equal(safeUrl('/privacy', 'https://booking.example.com/'), 'https://booking.example.com/privacy')
  assert.equal(safeUrl('http://example.com/', 'https://booking.example.com/'), '')
  assert.equal(safeUrl('javascript:alert(1)', 'https://booking.example.com/'), '')
  assert.equal(safeUrl('https://user:pass@example.com/', 'https://booking.example.com/'), '')
  assert.equal(safeUrl('http://127.0.0.1:1234/privacy', 'http://localhost/'), 'http://127.0.0.1:1234/privacy')
})
