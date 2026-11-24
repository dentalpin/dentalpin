/**
 * Per-clinic `frame-ancestors` for the public booking page.
 *
 * `/p/booking/<clinicId>` may be embedded in an iframe on the clinic's own
 * website. The allowed origins are the clinic's `embed_origins` setting
 * (online_booking settings, validated as https origins by the backend). Every
 * other route keeps `frame-ancestors 'self'` (Caddyfile + csp.ts).
 *
 * The origins are read from the clinic's public config endpoint, cached for a
 * minute. Any failure resolves to `'self'` only (fail closed).
 */
import type { H3Event } from 'h3'

const BOOKING_PATH = /^\/p\/booking\/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\/?$/i
const HTTPS_ORIGIN = /^https:\/\/[a-z0-9.-]+(:\d{1,5})?$/
const TTL_MS = 60_000
const FAILURE_TTL_MS = 10_000
const MAX_ENTRIES = 500

const cache = new Map<string, { origins: string[], expires: number }>()

export function bookingClinicId(path: string): string | null {
  return BOOKING_PATH.exec(path.split('?')[0] ?? '')?.[1]?.toLowerCase() ?? null
}

async function lookup(event: H3Event, clinicId: string): Promise<string[]> {
  const hit = cache.get(clinicId)
  if (hit && hit.expires > Date.now()) return hit.origins
  let origins: string[] = []
  let ttl = FAILURE_TTL_MS
  try {
    const base = String(useRuntimeConfig(event).apiBaseUrlServer || '')
    const response = await $fetch<{ data?: { embed_origins?: unknown } }>(
      `${base}/api/v1/online_booking/public/${clinicId}/config`,
      { timeout: 2000, retry: 0 }
    )
    const listed = response.data?.embed_origins
    if (Array.isArray(listed)) {
      origins = listed.filter((item): item is string => typeof item === 'string' && HTTPS_ORIGIN.test(item))
      ttl = TTL_MS
    }
  } catch {
    origins = []
  }
  if (cache.size >= MAX_ENTRIES) cache.clear()
  cache.set(clinicId, { origins, expires: Date.now() + ttl })
  return origins
}

/**
 * `frame-ancestors` value for the request, or `null` when the route is not
 * the booking page. Only framed loads need the clinic's origins, so a
 * top-level navigation (`Sec-Fetch-Dest: document`) skips the backend lookup.
 */
export async function bookingFrameAncestors(event: H3Event): Promise<string | null> {
  const clinicId = bookingClinicId(event.path || '')
  if (!clinicId) return null
  const dest = getRequestHeader(event, 'sec-fetch-dest')
  if (dest && dest !== 'iframe' && dest !== 'frame') return '\'self\''
  const origins = await lookup(event, clinicId)
  return ['\'self\'', ...origins].join(' ')
}
