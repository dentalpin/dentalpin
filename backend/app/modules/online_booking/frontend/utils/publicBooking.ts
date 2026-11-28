/**
 * Pure helpers for the public booking page (`/p/booking/<clinicId>`).
 * Day strings are `YYYY-MM-DD` calendar days in the clinic timezone; they
 * are shifted at noon UTC so daylight-saving changes never move them.
 */

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

export function validClinicId(value: unknown): value is string {
  return typeof value === 'string' && UUID_RE.test(value)
}

/** Only absolute https URLs without credentials (plus http on localhost for development). */
export function safeUrl(value: string | null | undefined, base?: string): string {
  if (!value) return ''
  try {
    const url = new URL(value, base)
    const localHttp = url.protocol === 'http:' && ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)
    return (url.protocol === 'https:' || localHttp) && !url.username && !url.password ? url.href : ''
  } catch {
    return ''
  }
}

export function offsetDay(day: string, offset: number): string {
  const date = new Date(`${day}T12:00:00Z`)
  date.setUTCDate(date.getUTCDate() + offset)
  // Read the UTC fields: the string is a calendar day, not an instant.
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())}`
}

export function dayDistance(a: string, b: string): number {
  return Math.round((Date.parse(`${b}T12:00:00Z`) - Date.parse(`${a}T12:00:00Z`)) / 86400000)
}

/** Today's calendar day in the given IANA timezone. */
export function todayIn(timezone: string, now: Date = new Date()): string {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: timezone, year: 'numeric', month: '2-digit', day: '2-digit'
  }).formatToParts(now)
  const part = (name: string) => parts.find(item => item.type === name)?.value
  return `${part('year')}-${part('month')}-${part('day')}`
}

/** Hour (0-23) of an instant in the given timezone. */
export function hourIn(timezone: string, iso: string): number {
  return Number(new Intl.DateTimeFormat('en-GB', {
    timeZone: timezone, hour: '2-digit', hourCycle: 'h23'
  }).format(new Date(iso)))
}

export function splitDayParts(starts: string[], timezone: string) {
  return {
    morning: starts.filter(value => hourIn(timezone, value) < 12),
    afternoon: starts.filter(value => hourIn(timezone, value) >= 12)
  }
}

/** The booking and confirmation API only know Spanish and English copy. */
export function apiLanguage(locale: string): 'es' | 'en' {
  return locale === 'es' ? 'es' : 'en'
}

/** Read `token` from the URL fragment and strip the fragment from the address bar. */
export function takeFragmentToken(): string | null {
  if (typeof window === 'undefined' || !window.location.hash) return null
  const token = new URLSearchParams(window.location.hash.slice(1)).get('token')
  window.history.replaceState(null, '', window.location.pathname + window.location.search)
  return token
}

/** Resolve a framed parent's origin only when it is explicitly allowlisted. */
export function allowedParentOrigin(referrer: string, origins: string[]): string | null {
  try {
    const origin = new URL(referrer).origin
    return origins.includes(origin) ? origin : null
  } catch {
    return null
  }
}

export function postBookingHeight(parent: Pick<Window, 'postMessage'>, referrer: string, origins: string[], height: number): void {
  const origin = allowedParentOrigin(referrer, origins)
  if (origin && Number.isFinite(height) && height > 0) {
    parent.postMessage({ type: 'dentalpin:booking:height', height: Math.ceil(height) }, origin)
  }
}
