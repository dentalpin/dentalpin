import { describe, expect, it } from 'vitest'
// Import directly from the agenda module's frontend layer via the
// #module-layers alias (resolved in vitest.config.ts to ../backend/app/modules).
import { parseCheckinResult } from '#module-layers/agenda/frontend/utils/checkinResult'

describe('parseCheckinResult', () => {
  it('keeps the minutes in too_early:<HH:MM>', () => {
    expect(parseCheckinResult('too_early:09:30')).toEqual({ code: 'too_early', time: '09:30' })
    expect(parseCheckinResult('too_early:14:45')).toEqual({ code: 'too_early', time: '14:45' })
  })
  it('parses window_closed without a time', () => {
    expect(parseCheckinResult('window_closed')).toEqual({ code: 'window_closed', time: '' })
  })
  it('treats anything else as unknown', () => {
    expect(parseCheckinResult('')).toEqual({ code: 'unknown', time: '' })
    expect(parseCheckinResult('garbage')).toEqual({ code: 'unknown', time: '' })
    expect(parseCheckinResult('bogus:12:00')).toEqual({ code: 'unknown', time: '' })
  })
})
