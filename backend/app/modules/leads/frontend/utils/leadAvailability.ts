/**
 * Availability helpers.
 *
 * Weekday names are **not** i18n keys: `Intl.DateTimeFormat` already knows
 * them in every locale the app ships, including the narrow forms a week
 * strip needs (es: L M X J V S D — note `X` for miércoles, which a naive
 * first-letter of the full name would get wrong). Only the time slots are
 * ours to translate.
 */

export const DAY_ORDER = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'] as const
export const SLOT_ORDER = ['morning', 'afternoon', 'evening'] as const

export type DayOfWeek = (typeof DAY_ORDER)[number]
export type AvailabilitySlot = (typeof SLOT_ORDER)[number]

// 2024-01-01 was a Monday: a fixed reference week keeps the labels stable
// regardless of today's date.
const REFERENCE_MONDAY = Date.UTC(2024, 0, 1)

/** Deduplicate and order mon..sun; unknown codes are dropped. */
export function canonicalDays(days: string[] | null | undefined): DayOfWeek[] {
  const seen = new Set((days ?? []).filter((day): day is DayOfWeek =>
    (DAY_ORDER as readonly string[]).includes(day)
  ))
  return DAY_ORDER.filter(day => seen.has(day))
}

export function isSlot(value: string | null | undefined): value is AvailabilitySlot {
  return Boolean(value) && (SLOT_ORDER as readonly string[]).includes(value as string)
}

export function hasAvailability(
  days: string[] | null | undefined,
  slot: string | null | undefined
): boolean {
  return canonicalDays(days).length > 0 || isSlot(slot)
}

function referenceDate(day: DayOfWeek): Date {
  return new Date(REFERENCE_MONDAY + DAY_ORDER.indexOf(day) * 86_400_000)
}

export function dayLabel(day: DayOfWeek, locale: string): string {
  return new Intl.DateTimeFormat(locale, { weekday: 'long', timeZone: 'UTC' }).format(
    referenceDate(day)
  )
}

export function dayNarrowLabel(day: DayOfWeek, locale: string): string {
  return new Intl.DateTimeFormat(locale, { weekday: 'narrow', timeZone: 'UTC' }).format(
    referenceDate(day)
  )
}

/**
 * "Mon, Wed and Fri" in the reader's language — used for the accessible
 * label of the strip and for `title` tooltips.
 */
export function daysSummary(days: string[] | null | undefined, locale: string): string {
  const ordered = canonicalDays(days)
  if (!ordered.length) return ''
  if (typeof Intl.ListFormat !== 'undefined') {
    return new Intl.ListFormat(locale, { style: 'long', type: 'conjunction' }).format(
      ordered.map(day => dayLabel(day, locale))
    )
  }
  return ordered.map(day => dayLabel(day, locale)).join(', ')
}
