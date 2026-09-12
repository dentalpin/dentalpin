/**
 * The cookie header SSR forwards to the backend (ADR 0023).
 *
 * The incoming request's ``cookie`` header is the starting point, but a
 * server-side refresh rotates the session mid-render: the refresh cookie
 * that came in is revoked the moment ``/auth/refresh`` answers. Every
 * later backend call in the *same* render must therefore use the merged
 * jar (incoming + the ``Set-Cookie`` values the refresh produced), or the
 * next call presents the revoked token and reuse detection burns the
 * family. The merged header lives on ``event.context`` so it is
 * per-request and visible to every composable, however early it was
 * created.
 */
import { appendResponseHeader } from 'h3'

const CONTEXT_KEY = 'dpCookieHeader'

/** Overlay ``Set-Cookie`` values onto a cookie header. */
export function mergeCookieHeader(incoming: string | undefined, setCookies: string[]): string {
  const jar = new Map<string, string>()
  for (const part of (incoming || '').split(';')) {
    const [k, ...v] = part.trim().split('=')
    if (k) jar.set(k, v.join('='))
  }
  for (const sc of setCookies) {
    const [pair] = sc.split(';')
    const [k, ...v] = (pair || '').trim().split('=')
    if (k) jar.set(k, v.join('='))
  }
  return Array.from(jar, ([k, v]) => `${k}=${v}`).join('; ')
}

export function useSsrCookies() {
  // Capture the request event and the incoming header once, synchronously,
  // while the Nuxt instance is available. The composable is used after
  // awaits (middleware, retries), where calling useRequestEvent() /
  // useRequestHeaders() again would throw "nuxt instance unavailable";
  // reading event.context is a plain property access and always works.
  const event = import.meta.server ? useRequestEvent() : undefined
  const incoming = import.meta.server ? useRequestHeaders(['cookie']).cookie : undefined

  /** Current cookie header to forward (server only; ``undefined`` on the client). */
  function cookieHeader(): string | undefined {
    if (!import.meta.server) return undefined
    const stored = event?.context[CONTEXT_KEY] as string | undefined
    return stored !== undefined ? stored : incoming
  }

  /** Headers object carrying the forwarded cookie (empty on the client). */
  function cookieHeaders(): Record<string, string> {
    const c = cookieHeader()
    return c ? { cookie: c } : {}
  }

  /** Record rotated cookies for the rest of this render and relay them to the browser. */
  function applySetCookies(setCookies: string[]): void {
    if (!import.meta.server || setCookies.length === 0 || !event) return
    event.context[CONTEXT_KEY] = mergeCookieHeader(cookieHeader(), setCookies)
    for (const c of setCookies) appendResponseHeader(event, 'set-cookie', c)
  }

  return { cookieHeader, cookieHeaders, applySetCookies }
}
