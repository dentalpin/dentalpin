import { describe, expect, it } from 'vitest'
import { errorMessage } from '~/utils/error'

describe('errorMessage', () => {
  it('surfaces the backend message from an ErrorResponse body', () => {
    // What the API actually returns for a 400 (app/main.py http_exception_handler).
    const e = { statusCode: 400, data: { data: null, message: 'Cannot send empty budget', errors: ['Cannot send empty budget'] } }
    expect(errorMessage(e, 'fallback')).toBe('Cannot send empty budget')
  })

  it('prefers a string detail (FastAPI default handler)', () => {
    expect(errorMessage({ data: { detail: 'Patient has no email address' } }, 'fallback'))
      .toBe('Patient has no email address')
  })

  it('falls back when detail is a 422 validation list, not a string', () => {
    const e = { statusCode: 422, data: { detail: [{ loc: ['body', 'signature'], msg: 'field required' }] } }
    expect(errorMessage(e, 'fallback')).toBe('fallback')
  })

  it('falls back for network errors and non-objects', () => {
    expect(errorMessage(new TypeError('Failed to fetch'), 'fallback')).toBe('Failed to fetch')
    expect(errorMessage(undefined, 'fallback')).toBe('fallback')
  })
})
