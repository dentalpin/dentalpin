// @vitest-environment node
import { describe, expect, it } from 'vitest'
import {
  DAY_ORDER,
  canonicalDays,
  dayLabel,
  dayNarrowLabel,
  daysSummary,
  hasAvailability,
  isSlot
} from '#module-layers/leads/frontend/utils/leadAvailability'

/**
 * Availability is structured, and the week strip is rendered from it — so
 * ordering, dedupe and the localized day labels are load-bearing, not
 * cosmetic. Weekday names come from Intl rather than from i18n keys so they
 * are correct in all ten locales without 70 extra translations.
 */
describe('canonicalDays', () => {
  it('orders mon..sun regardless of input order', () => {
    expect(canonicalDays(['fri', 'mon', 'sun'])).toEqual(['mon', 'fri', 'sun'])
  })

  it('drops duplicates and unknown codes', () => {
    expect(canonicalDays(['wed', 'wed', 'monday', 'xyz', 'tue'])).toEqual(['tue', 'wed'])
  })

  it('treats null/undefined/empty as no days', () => {
    expect(canonicalDays(null)).toEqual([])
    expect(canonicalDays(undefined)).toEqual([])
    expect(canonicalDays([])).toEqual([])
  })
})

describe('hasAvailability / isSlot', () => {
  it('is true for days, for a slot, or for both', () => {
    expect(hasAvailability(['mon'], null)).toBe(true)
    expect(hasAvailability([], 'afternoon')).toBe(true)
    expect(hasAvailability(['mon'], 'evening')).toBe(true)
  })

  it('is false when neither is set', () => {
    expect(hasAvailability([], null)).toBe(false)
    expect(hasAvailability(null, '')).toBe(false)
    expect(hasAvailability([], 'whenever')).toBe(false)
  })

  it('only accepts the three real slots', () => {
    expect(isSlot('morning')).toBe(true)
    expect(isSlot('afternoon')).toBe(true)
    expect(isSlot('evening')).toBe(true)
    expect(isSlot('any')).toBe(false)
    expect(isSlot(null)).toBe(false)
  })
})

describe('localized day labels', () => {
  it('renders narrow labels from Intl, not from the English code', () => {
    // Spanish narrow weekdays start on L and use X for miércoles — a naive
    // first letter of the full name would produce "M" twice.
    expect(DAY_ORDER.map(day => dayNarrowLabel(day, 'es'))).toEqual([
      'L',
      'M',
      'X',
      'J',
      'V',
      'S',
      'D'
    ])
    expect(dayNarrowLabel('mon', 'en')).toBe('M')
    expect(dayLabel('wed', 'es')).toBe('miércoles')
    expect(dayLabel('wed', 'fr')).toBe('mercredi')
  })

  it('summarises the selected days as readable prose', () => {
    expect(daysSummary(['mon', 'wed'], 'en')).toBe('Monday and Wednesday')
    expect(daysSummary([], 'en')).toBe('')
  })
})
