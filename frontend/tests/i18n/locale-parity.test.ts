// @vitest-environment node
import { describe, expect, it } from 'vitest'
import { readFileSync, readdirSync, existsSync } from 'node:fs'
import { resolve } from 'node:path'

/**
 * Key-parity guard for every locale file in the app (host + module
 * layers). Each non-English locale must expose exactly the same key set
 * as its `en.json` counterpart — no missing keys (English would leak
 * through `fallbackLocale`) and no orphans (dead translations that
 * drift silently, the problem documented in #126).
 *
 * Runs in plain Node on purpose: it reads JSON straight off the
 * repository tree, so no Nuxt context (and no module-layer bootstrap)
 * is required.
 *
 * When a new locale ships, it joins automatically: drop the file next
 * to the others and this test holds it to full parity.
 */

const HOST_LOCALES = resolve(__dirname, '../../i18n/locales')

// In Docker the module layers are mounted at /module_layers; outside
// Docker they live at ../../backend/app/modules relative to this file.
const MODULES_ROOT = existsSync('/module_layers')
  ? '/module_layers'
  : resolve(__dirname, '../../../backend/app/modules')

type Tree = Record<string, unknown>

function flatten(obj: Tree, prefix = ''): string[] {
  const keys: string[] = []
  for (const [k, v] of Object.entries(obj)) {
    const path = prefix ? `${prefix}.${k}` : k
    if (v !== null && typeof v === 'object') keys.push(...flatten(v as Tree, path))
    else keys.push(path)
  }
  return keys
}

function loadJson(path: string): Tree {
  return JSON.parse(readFileSync(path, 'utf-8')) as Tree
}

function comparePair(name: string, enPath: string, xxPath: string) {
  const en = new Set(flatten(loadJson(enPath)))
  const xx = new Set(flatten(loadJson(xxPath)))
  const missing = [...en].filter(k => !xx.has(k))
  const extra = [...xx].filter(k => !en.has(k))
  expect(missing, `${name}: missing keys vs en`).toEqual([])
  expect(extra, `${name}: orphan keys not present in en`).toEqual([])
}

describe('locale key parity', () => {
  const hostEn = resolve(HOST_LOCALES, 'en.json')
  const hostLocales = readdirSync(HOST_LOCALES).filter(f => f.endsWith('.json') && f !== 'en.json')

  it('host app: every locale matches en.json exactly', () => {
    expect(hostLocales.length).toBeGreaterThan(0)
    for (const file of hostLocales) {
      comparePair(`host/${file}`, hostEn, resolve(HOST_LOCALES, file))
    }
  })

  it('module layers: every locale matches its module en.json', () => {
    const modules = readdirSync(MODULES_ROOT)
    let compared = 0
    for (const mod of modules) {
      const i18nDir = resolve(MODULES_ROOT, mod, 'frontend/i18n/locales')
      if (!existsSync(i18nDir)) continue
      const moduleEn = resolve(i18nDir, 'en.json')
      if (!existsSync(moduleEn)) continue
      for (const file of readdirSync(i18nDir)) {
        if (!file.endsWith('.json') || file === 'en.json') continue
        comparePair(`${mod}/${file}`, moduleEn, resolve(i18nDir, file))
        compared++
      }
    }
    // Sanity: the suite must actually be comparing something — if the
    // glob breaks (path change), fail loudly instead of passing vacuously.
    expect(compared).toBeGreaterThan(10)
  })
})
