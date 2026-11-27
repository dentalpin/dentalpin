// @vitest-environment node
import { describe, expect, it } from 'vitest'
import { readFileSync, readdirSync } from 'node:fs'
import { resolve } from 'node:path'

/**
 * The public check-in page (`/p/check-in/<token>`) is read on the patient's
 * phone, so an English leftover in a translated locale is a real defect
 * (#1217). `locale-parity.test.ts` only checks key sets and placeholders;
 * this guard fails when an `appointments.checkin.*` value is identical to
 * English.
 */

const LOCALES_DIR = resolve(__dirname, '../../i18n/locales')

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

describe('appointments check-in translations', () => {
  const en = load('en.json')
  const locales = readdirSync(LOCALES_DIR)
    .filter(f => f.endsWith('.json') && f !== 'en.json')
    .map(f => f.replace('.json', ''))

  for (const locale of locales) {
    it(`${locale}: no check-in string is left in English`, () => {
      const xx = load(`${locale}.json`)
      const leftovers = [...en.keys()].filter(
        key => key.startsWith('appointments.checkin.') && xx.get(key) === en.get(key)
      )
      expect(leftovers, `${locale}.json still holds English for:\n${leftovers.join('\n')}`).toEqual([])
    })
  }
})
