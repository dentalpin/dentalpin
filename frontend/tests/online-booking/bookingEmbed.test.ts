import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { bookingClinicId, bookingFrameAncestors } from '../../server/utils/bookingEmbed'
import { allowedParentOrigin, postBookingHeight, apiLanguage, offsetDay, safeUrl, takeFragmentToken, todayIn, validClinicId } from '#module-layers/online_booking/frontend/utils/publicBooking'

const ID = '0b1c2d3e-4f50-4a6b-8c7d-9e0f1a2b3c4d'
const fetchMock = vi.fn()

function event(path: string, dest?: string) {
  return { path, dest } as never
}

beforeEach(() => {
  fetchMock.mockReset()
  vi.stubGlobal('$fetch', fetchMock)
  vi.stubGlobal('useRuntimeConfig', () => ({ apiBaseUrlServer: 'http://backend:8000' }))
  vi.stubGlobal('getRequestHeader', (e: { dest?: string }) => e.dest)
})
afterEach(() => {
  vi.unstubAllGlobals()
  vi.unstubAllEnvs()
})

describe('booking page frame-ancestors', () => {
  it('only recognises the booking page route', () => {
    expect(bookingClinicId(`/p/booking/${ID}`)).toBe(ID)
    expect(bookingClinicId(`/p/booking/${ID}/?x=1`)).toBe(ID)
    expect(bookingClinicId('/p/booking/not-a-uuid')).toBeNull()
    expect(bookingClinicId(`/p/budget/${ID}`)).toBeNull()
    expect(bookingClinicId(`/p/booking/${ID}/extra`)).toBeNull()
  })

  it.each([['development', true], ['test', false], ['production', false]])('permits loopback framing only in development (%s)', async (environment, permitted) => {
    vi.stubEnv('ENVIRONMENT', environment)
    const id = environment === 'development' ? '11111111-2222-4333-8444-000000000001' : environment === 'test' ? '11111111-2222-4333-8444-000000000002' : '11111111-2222-4333-8444-000000000003'
    fetchMock.mockResolvedValue({ data: { embed_origins: ['http://localhost:3000', 'http://127.0.0.1:3000', 'http://evil.example'] } })
    const value = await bookingFrameAncestors(event(`/p/booking/${id}`, 'iframe'))
    expect(value?.includes('http://localhost:3000')).toBe(permitted)
    expect(value?.includes('http://127.0.0.1:3000')).toBe(permitted)
    expect(value).not.toContain('http://evil.example')
  })

  it('returns null for other routes', async () => {
    expect(await bookingFrameAncestors(event('/login'))).toBeNull()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('allows the clinic origins for framed loads and filters bad values', async () => {
    const id = '11111111-2222-4333-8444-555555555555'
    fetchMock.mockResolvedValue({ data: { embed_origins: ['https://clinic.example.es', 'http://insecure.example', 'https://x.example; script-src *', 7] } })
    expect(await bookingFrameAncestors(event(`/p/booking/${id}`, 'iframe')))
      .toBe('\'self\' https://clinic.example.es')
    expect(fetchMock).toHaveBeenCalledWith(`http://backend:8000/api/v1/online_booking/public/${id}/config`, expect.anything())
    await bookingFrameAncestors(event(`/p/booking/${id}`, 'iframe'))
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('does not look anything up for top-level navigations', async () => {
    expect(await bookingFrameAncestors(event(`/p/booking/${ID}`, 'document'))).toBe('\'self\'')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('fails closed when the backend cannot answer', async () => {
    const id = '22222222-2222-4333-8444-555555555555'
    fetchMock.mockRejectedValue(new Error('down'))
    expect(await bookingFrameAncestors(event(`/p/booking/${id}`))).toBe('\'self\'')
  })
})

describe('public booking helpers', () => {
  it('validates clinic ids and URLs', () => {
    expect(validClinicId(ID)).toBe(true)
    expect(validClinicId('nope')).toBe(false)
    expect(safeUrl('https://clinic.example.es/privacy')).toBe('https://clinic.example.es/privacy')
    expect(safeUrl('javascript:alert(1)')).toBe('')
    expect(safeUrl('https://user:pw@clinic.example.es')).toBe('')
    expect(safeUrl('http://clinic.example.es')).toBe('')
  })

  it('does calendar arithmetic without DST drift', () => {
    expect(offsetDay('2030-03-30', 2)).toBe('2030-04-01')
    expect(todayIn('Europe/Madrid', new Date('2030-01-01T23:30:00Z'))).toBe('2030-01-02')
    expect(apiLanguage('es')).toBe('es')
    expect(apiLanguage('de')).toBe('en')
  })

  it('takes the token from the fragment and clears the address bar', () => {
    window.history.replaceState(null, '', '/p/booking/x#token=abc')
    expect(takeFragmentToken()).toBe('abc')
    expect(window.location.hash).toBe('')
    expect(takeFragmentToken()).toBeNull()
  })
})

describe('iframe parent origin validation', () => {
  it('only accepts exact allowlisted origins', () => {
    expect(allowedParentOrigin('https://host.example/page', ['https://host.example'])).toBe('https://host.example')
    expect(allowedParentOrigin('https://evil.example/page', ['https://host.example'])).toBeNull()
    expect(allowedParentOrigin('https://host.example.evil/page', ['https://host.example'])).toBeNull()
    expect(allowedParentOrigin('', ['https://host.example'])).toBeNull()
    const parent = { postMessage: vi.fn() }
    postBookingHeight(parent, 'https://host.example/page', ['https://host.example'], 120.2)
    expect(parent.postMessage).toHaveBeenCalledWith({ type: 'dentalpin:booking:height', height: 121 }, 'https://host.example')
    postBookingHeight(parent, 'https://evil.example/', ['https://host.example'], 121)
    expect(parent.postMessage).toHaveBeenCalledTimes(1)
  })
})
