/**
 * Core locale files must not drift (#126).
 *
 * Every locale under `i18n/locales/` must expose exactly the same key
 * set as `en.json` (the reference), and every translated string must
 * keep the same `{placeholder}` names and the same number of plural
 * variants (` | `-separated) as the English source. A missing key only
 * ever surfaced as a raw `some.dotted.key` in the UI at runtime —
 * this makes it a test failure with an actionable list instead.
 *
 * Module-layer locales (`backend/app/modules/<name>/frontend/i18n/`)
 * are a separate set, deliberately out of scope here.
 */
import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

const LOCALES_DIR = join(__dirname, '../../i18n/locales')
const REFERENCE = 'en'

function flatten(obj: Record<string, unknown>, prefix = ''): Map<string, string> {
  const out = new Map<string, string>()
  for (const [key, value] of Object.entries(obj)) {
    const path = prefix ? `${prefix}.${key}` : key
    if (value !== null && typeof value === 'object') {
      for (const [k, v] of flatten(value as Record<string, unknown>, path)) out.set(k, v)
    } else {
      out.set(path, String(value))
    }
  }
  return out
}

function placeholders(message: string): string[] {
  return [...new Set(message.match(/\{[^}]*\}/g) ?? [])].sort()
}

function pluralVariants(message: string): number {
  return message.split(' | ').length
}

const files = readdirSync(LOCALES_DIR).filter(f => f.endsWith('.json')).sort()
const messages = new Map(files.map(f => [
  f.replace(/\.json$/, ''),
  flatten(JSON.parse(readFileSync(join(LOCALES_DIR, f), 'utf-8')))
]))
const reference = messages.get(REFERENCE)!
const others = [...messages.keys()].filter(l => l !== REFERENCE)

describe('core locale parity', () => {
  it(`found the ${REFERENCE} reference and at least one other locale`, () => {
    expect(reference).toBeDefined()
    expect(others.length).toBeGreaterThan(0)
  })

  it.each(others)('%s has exactly the same keys as en', (locale) => {
    const keys = messages.get(locale)!
    const missing = [...reference.keys()].filter(k => !keys.has(k))
    const extra = [...keys.keys()].filter(k => !reference.has(k))
    const problems = [
      ...missing.map(k => `missing (add to ${locale}.json): ${k}`),
      ...extra.map(k => `extra (translate the key into the other locales, or delete it): ${k}`)
    ]
    expect(problems, problems.join('\n')).toEqual([])
  })

  it.each(others)('%s keeps every {placeholder} and plural-variant count from en', (locale) => {
    const keys = messages.get(locale)!
    const problems: string[] = []
    for (const [key, enValue] of reference) {
      const value = keys.get(key)
      if (value === undefined) continue // reported by the parity test above
      const expected = placeholders(enValue)
      const actual = placeholders(value)
      if (expected.join(',') !== actual.join(',')) {
        problems.push(`${key}: placeholders [${actual}] != en [${expected}]`)
      }
      // A pluralized key must stay pluralized everywhere, but a locale
      // may need MORE forms than English (Polish has 3, wired up via
      // pluralRules in i18n.config.ts). A pipe in a non-plural key
      // would render literally, so those must stay single.
      const enVariants = pluralVariants(enValue)
      const variants = pluralVariants(value)
      if (enVariants === 1 ? variants !== 1 : variants < 2) {
        problems.push(`${key}: ${variants} plural variants vs en ${enVariants}`)
      }
    }
    expect(problems, problems.join('\n')).toEqual([])
  })
})
