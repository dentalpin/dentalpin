// @vitest-environment node
import { afterEach, describe, expect, it, vi } from 'vitest'
import { computeAge, formatPatientDate } from '#module-layers/patients/frontend/utils/medicalSnapshot'

/**
 * #1176: a date of birth is a date-only `YYYY-MM-DD`. `new Date(s)` reads
 * it as UTC midnight, so west of UTC the Info card showed the previous day
 * and the age flipped a day early. Mexico City is UTC-6 all year.
 */
const TZ = process.env.TZ

afterEach(() => {
  process.env.TZ = TZ
  vi.useRealTimers()
})

/** Run `fn` with the process in `tz` (node honours a runtime TZ change). */
function inZone<T>(tz: string, fn: () => T): T {
  process.env.TZ = tz
  return fn()
}

const ZONES = ['America/Mexico_City', 'America/Los_Angeles', 'UTC', 'Europe/Madrid', 'Asia/Kolkata']

describe('formatPatientDate', () => {
  it('shows the stored calendar day in every zone', () => {
    for (const tz of ZONES) {
      expect(inZone(tz, () => formatPatientDate('1985-03-15', 'es-ES')), tz).toBe('15/03/1985')
    }
  })

  it('still formats a full timestamp', () => {
    expect(inZone('UTC', () => formatPatientDate('2026-03-15T10:00:00Z', 'es-ES'))).toBe('15/03/2026')
  })
})

describe('computeAge', () => {
  it('turns a year older on the birthday, not the day before', () => {
    for (const tz of ZONES) {
      inZone(tz, () => {
        vi.useFakeTimers()
        // Evening before the birthday, local time.
        vi.setSystemTime(new Date(2026, 2, 14, 20, 0))
        expect(computeAge('1985-03-15'), `${tz} day before`).toBe(40)
        // Just after local midnight on the birthday.
        vi.setSystemTime(new Date(2026, 2, 15, 0, 30))
        expect(computeAge('1985-03-15'), `${tz} birthday`).toBe(41)
        vi.useRealTimers()
      })
    }
  })
})
