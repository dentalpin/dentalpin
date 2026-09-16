/**
 * Clinic wall-clock helpers.
 *
 * The API serializes appointment and availability timestamps in the
 * *clinic* timezone (``2026-08-14T12:00:00+02:00``, issue #161). Anything
 * that shows an hour or buckets by day must read that wall-clock, not
 * ``new Date(iso)`` (which re-renders the instant in the browser's zone
 * and shifts hours when the device and the clinic disagree). Instant math
 * — sorting, overlap, "starts in N min", timers — keeps using ``new Date``.
 */

const ISO_WALL_CLOCK_RE = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?/

/**
 * Parse ``iso`` as clinic wall-clock, dropping the offset. Returns a
 * browser-local ``Date`` holding the clinic's Y-M-D h:m:s, so
 * ``getHours()``, ``toLocaleTimeString()`` and day-bucketing agree with
 * the calendar grid on every device. Throws on non-ISO input.
 */
export function parseWallClock(iso: string): Date {
  const m = ISO_WALL_CLOCK_RE.exec(iso)
  if (!m) throw new Error(`Invalid ISO timestamp: ${iso}`)
  return new Date(
    Number(m[1]), Number(m[2]) - 1, Number(m[3]),
    Number(m[4]), Number(m[5]), Number(m[6] ?? 0)
  )
}

/**
 * Current time as clinic wall-clock (same shape as ``parseWallClock``),
 * for comparing against wall-clock values. Falls back to the browser
 * clock when the timezone is unknown or invalid.
 */
export function clinicNow(timeZone: string | null | undefined): Date {
  const now = new Date()
  if (!timeZone) return now
  try {
    const parts = new Intl.DateTimeFormat('en-US', {
      timeZone,
      hourCycle: 'h23',
      year: 'numeric',
      month: 'numeric',
      day: 'numeric',
      hour: 'numeric',
      minute: 'numeric',
      second: 'numeric'
    }).formatToParts(now)
    const get = (type: string) => Number(parts.find(p => p.type === type)?.value)
    return new Date(get('year'), get('month') - 1, get('day'), get('hour'), get('minute'), get('second'))
  } catch {
    return now
  }
}

/**
 * Today's date in the clinic's timezone, as `YYYY-MM-DD` — for
 * `<input type="date">` v-model and API payloads like `payment_date`
 * (#439/#445 review follow-up). `clinicNow(tz).toISOString()` would
 * re-shift the wall-clock Date through the *browser's own* offset and
 * silently roll to the wrong calendar day near local midnight when the
 * device and the clinic disagree — read the Y-M-D fields directly off
 * the wall-clock Date instead. Falls back to the browser's own local
 * date when the timezone is unknown (same fallback as `clinicNow`).
 */
export function clinicToday(timeZone: string | null | undefined): string {
  const d = clinicNow(timeZone)
  const yyyy = d.getFullYear()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd}`
}
