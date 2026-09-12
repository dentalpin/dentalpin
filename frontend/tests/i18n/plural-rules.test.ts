// @vitest-environment node
import { describe, expect, it } from 'vitest'
import { arPluralRule, plPluralRule } from '../../i18n/pluralRules'

/**
 * Pins the Arabic plural rule (#389 tail). Every `ar.json` message today
 * carries exactly two pipe segments, so only the two-way shortcut runs —
 * these tests lock that mapping and the six-way clamp that protects a
 * future three-plus-form message from silently resolving wrong.
 *
 * Pure functions, plain Node: no Nuxt context required.
 */
describe('arPluralRule', () => {
  it('maps two-segment messages one/other', () => {
    expect(arPluralRule(1, 2)).toBe(0)
    for (const n of [0, 2, 3, 11, 100]) expect(arPluralRule(n, 2)).toBe(1)
  })

  it('maps six-segment messages onto CLDR categories', () => {
    expect(arPluralRule(0, 6)).toBe(0)
    expect(arPluralRule(1, 6)).toBe(1)
    expect(arPluralRule(2, 6)).toBe(2)
    for (const n of [3, 5, 10]) expect(arPluralRule(n, 6)).toBe(3)
    for (const n of [11, 50, 99]) expect(arPluralRule(n, 6)).toBe(4)
    for (const n of [100, 1000]) expect(arPluralRule(n, 6)).toBe(5)
  })

  it('clamps short variant lists instead of overrunning', () => {
    // Three segments (zero | one | other): the six-way tail collapses
    // onto the last available index instead of running past the list.
    const threeWay: Array<[number, number]> = [[0, 0], [1, 1], [2, 2], [5, 2], [50, 2], [100, 2]]
    for (const [n, idx] of threeWay) expect(arPluralRule(n, 3)).toBe(idx)
    expect(arPluralRule(2, 2)).toBe(1)
  })
})

describe('plPluralRule', () => {
  it('maps counts onto one / few / many', () => {
    expect(plPluralRule(1, 3)).toBe(0)
    for (const n of [2, 3, 4, 22]) expect(plPluralRule(n, 3)).toBe(1)
    for (const n of [5, 12, 13, 14, 25]) expect(plPluralRule(n, 3)).toBe(2)
  })

  it('collapses two-segment messages onto one / other', () => {
    expect(plPluralRule(1, 2)).toBe(0)
    for (const n of [2, 5, 22]) expect(plPluralRule(n, 2)).toBe(1)
  })
})
