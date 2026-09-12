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
const UNSAFE = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])

export function useSessionRequest() {
  const csrf = useCookie<string | null>('dp_csrf')

  function csrfHeaders(method?: string): Record<string, string> {
    if (method && UNSAFE.has(method.toUpperCase()) && csrf.value) {
      return { 'X-CSRF-Token': csrf.value }
    }
    return {}
  }

  /** Options to spread into a raw ``fetch``/``$fetch`` init. */
  function sessionRequest(method = 'GET', extraHeaders: Record<string, string> = {}) {
    return {
      credentials: 'include' as const,
      headers: { ...csrfHeaders(method), ...extraHeaders }
    }
  }

  /** ``true`` when a session cookie set is present (the readable half). */
  const hasSession = computed(() => !!csrf.value)

  return { csrfHeaders, sessionRequest, hasSession }
}
