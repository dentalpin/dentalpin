// @vitest-environment node
import { describe, expect, it } from 'vitest'
import { readFileSync, readdirSync } from 'node:fs'
import { resolve } from 'node:path'

/**
 * Consent strings are read by patients who sign on the clinic tablet, so an
 * English leftover in a translated locale is a real defect, not a cosmetic
 * one (#906 follow-up). `locale-parity.test.ts` only checks key sets and
 * placeholders; this guard additionally fails when a `documents.consent.*`
 * value (or the consent document type label) is identical to English.
 *
 * Genuine cognates are listed in ALLOWED_SAME_AS_ENGLISH as `locale:key`
 * with the reason; anything else must be translated.
 */

const LOCALES_DIR = resolve(__dirname, '../../../backend/app/modules/documents/frontend/i18n/locales')

const ALLOWED_SAME_AS_ENGLISH = new Set([
  'de:documents.consent.patient', // "Patient" is the German word
  'fr:documents.consent.patient' // "Patient" is the French word
])

type Tree = Record<string, unknown>

function flatten(obj: Tree, prefix = ''): Map<string, string> {
  const out = new Map<string, string>()
  for (const [k, v] of Object.entries(obj)) {
    const path = prefix ? `${prefix}.${k}` : k
    if (v !== null && typeof v === 'object') {
      for (const [ck, cv] of flatten(v as Tree, path)) out.set(ck, cv)
    } else {
      out.set(path, String(v))
    }
  }
  return out
}

function load(file: string): Map<string, string> {
  return flatten(JSON.parse(readFileSync(resolve(LOCALES_DIR, file), 'utf-8')) as Tree)
}

const isConsentKey = (key: string) =>
  key.startsWith('documents.consent.') || key === 'documents.types.informed_consent'

describe('documents consent translations', () => {
  const en = load('en.json')
  const locales = readdirSync(LOCALES_DIR)
    .filter(f => f.endsWith('.json') && f !== 'en.json' && f !== 'es.json')
    .map(f => f.replace('.json', ''))

  it('covers the non-es/en locales', () => {
    expect(locales.length).toBeGreaterThanOrEqual(10)
  })

  for (const locale of locales) {
    it(`${locale}: no consent string is left in English`, () => {
      const xx = load(`${locale}.json`)
      const leftovers: string[] = []
      for (const [key, enValue] of en) {
        if (!isConsentKey(key)) continue
        if (xx.get(key) === enValue && !ALLOWED_SAME_AS_ENGLISH.has(`${locale}:${key}`)) {
          leftovers.push(key)
        }
      }
      expect(
        leftovers,
        `${locale}.json still holds English for:\n${leftovers.join('\n')}\n(translate, or allowlist a true cognate)`
      ).toEqual([])
    })
  }
})

describe('documents consent template archive translations', () => {
  const en = load('en.json')
  const locales = readdirSync(LOCALES_DIR)
    .filter(f => f.endsWith('.json') && f !== 'en.json' && f !== 'es.json')
    .map(f => f.replace('.json', ''))

  for (const locale of locales) {
    it(`${locale}: no template archive string is left in English`, () => {
      const xx = load(`${locale}.json`)
      const leftovers = [...en.keys()].filter(
        key => key.startsWith('documents.settings.consentTemplateArchive.')
          && xx.get(key) === en.get(key)
          && !ALLOWED_SAME_AS_ENGLISH.has(`${locale}:${key}`)
      )
      expect(leftovers, `${locale}.json still holds English for:\n${leftovers.join('\n')}`).toEqual([])
    })
  }
})
