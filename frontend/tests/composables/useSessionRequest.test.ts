import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { useSessionRequest } from '~/composables/useSessionRequest'

/**
 * #928: ``dp_csrf`` is owned by the backend (Set-Cookie on login/refresh,
 * cleared on logout). The app only reads it. Nuxt's ``useCookie`` writes on
 * the client as soon as it is created without the cookie present
 * (``dp_csrf=undefined; Max-Age=-1``), so a hydrating page that read the jar
 * a moment before the login response landed deleted the fresh cookie, and
 * the next SSR saw no session hint and redirected to /login.
 */
const proto = Object.getPrototypeOf(document)
let owner: object = proto
while (owner && !Object.getOwnPropertyDescriptor(owner, 'cookie')) {
  owner = Object.getPrototypeOf(owner)
}
const native = Object.getOwnPropertyDescriptor(owner, 'cookie')!

function clearCsrf() {
  native.set!.call(document, 'dp_csrf=; Expires=Thu, 01 Jan 1970 00:00:00 GMT; Path=/')
}

describe('useSessionRequest (#928)', () => {
  let writes: string[]

  beforeEach(() => {
    clearCsrf()
    writes = []
    Object.defineProperty(document, 'cookie', {
      configurable: true,
      get: () => native.get!.call(document),
      set: (value: string) => {
        writes.push(value)
        native.set!.call(document, value)
      }
    })
  })

  afterEach(() => {
    delete (document as unknown as Record<string, unknown>).cookie
    clearCsrf()
  })

  it('never writes dp_csrf when the cookie is absent', () => {
    const { hasSession } = useSessionRequest()
    expect(hasSession.value).toBe(false)
    expect(writes.filter(w => w.startsWith('dp_csrf='))).toEqual([])
  })

  it('never writes dp_csrf when the cookie is present', () => {
    native.set!.call(document, 'dp_csrf=tok-1; Path=/')
    const { hasSession, csrfHeaders } = useSessionRequest()
    expect(hasSession.value).toBe(true)
    expect(csrfHeaders('POST')).toEqual({ 'X-CSRF-Token': 'tok-1' })
    expect(writes.filter(w => w.startsWith('dp_csrf='))).toEqual([])
  })

  it('sees a cookie the backend set after the composable was created', () => {
    const { hasSession, csrfHeaders } = useSessionRequest()
    expect(hasSession.value).toBe(false)
    // The login response (another request, not this composable) sets it.
    native.set!.call(document, 'dp_csrf=tok-2; Path=/')
    expect(hasSession.value).toBe(true)
    expect(csrfHeaders('DELETE')).toEqual({ 'X-CSRF-Token': 'tok-2' })
    expect(csrfHeaders('GET')).toEqual({})
  })
})
