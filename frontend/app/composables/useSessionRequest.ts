/**
 * Session-cookie request options (ADR 0023, #353).
 *
 * Auth is an HttpOnly cookie now, so a request only needs
 * ``credentials: 'include'`` plus — on unsafe methods — the double-submit
 * ``X-CSRF-Token`` header echoing the JS-readable ``dp_csrf`` cookie.
 * ``useApi`` applies this itself; module composables that call
 * ``$fetch``/``fetch`` directly (blob downloads, uploads, SSE) spread
 * ``sessionRequest()`` into their init instead of building a bearer
 * header from a token JS can no longer see.
 */
import { customRef, type Ref } from 'vue'

const UNSAFE = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])
const CSRF_RE = /(?:^|;\s*)dp_csrf=([^;]*)/

/**
 * ``dp_csrf`` is owned by the backend (set on login/refresh, cleared on
 * logout); the app only ever reads it, fresh on every access. It is
 * deliberately not a ``useCookie`` ref: on the client ``useCookie`` writes
 * ``dp_csrf=undefined; Max-Age=-1`` whenever it is created while the
 * cookie is absent. A page that read the jar a moment before a login
 * response landed then deleted the cookie that response had just set, and
 * the next SSR saw no session and redirected to /login (#928). Reading on
 * access also sees a cookie set after the composable was created.
 */
export function useSessionRequest() {
  // SSR: the forwarded jar (incoming header, plus any rotation this render
  // did). Captured here, synchronously, while the Nuxt instance exists.
  const { cookieHeader } = useSsrCookies()

  function readCsrf(): string | null {
    const jar = import.meta.server ? cookieHeader() ?? '' : document.cookie
    const match = CSRF_RE.exec(jar)
    if (!match?.[1]) return null
    try {
      return decodeURIComponent(match[1])
    } catch {
      return match[1]
    }
  }

  function csrfHeaders(method?: string): Record<string, string> {
    const csrf = method && UNSAFE.has(method.toUpperCase()) ? readCsrf() : null
    return csrf ? { 'X-CSRF-Token': csrf } : {}
  }

  /** Options to spread into a raw ``fetch``/``$fetch`` init. */
  function sessionRequest(method = 'GET', extraHeaders: Record<string, string> = {}) {
    return {
      credentials: 'include' as const,
      headers: { ...csrfHeaders(method), ...extraHeaders }
    }
  }

  /** ``true`` when a session cookie set is present (the readable half).
   *  Not cached: every ``.value`` reads the jar. */
  const hasSession: Readonly<Ref<boolean>> = customRef(() => ({
    get: () => readCsrf() !== null,
    set: () => {}
  }))

  return { csrfHeaders, sessionRequest, hasSession }
}
