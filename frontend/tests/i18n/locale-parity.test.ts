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
 * Beyond keys, every translated string must keep the same `{placeholder}`
 * names as the English source, and pluralized keys (` | `-separated) must
 * stay pluralized: a locale may need MORE forms than English (Polish has
 * more, wired up via pluralRules in i18n.config.ts), but a pipe in a
 * non-plural key would render literally, so those must stay single.
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

function loadJson(path: string): Tree {
  return JSON.parse(readFileSync(path, 'utf-8')) as Tree
}

function placeholders(message: string): string[] {
  return [...new Set(message.match(/\{[^}]*\}/g) ?? [])].sort()
}

function pluralVariants(message: string): number {
  return message.split(' | ').length
}

function comparePair(name: string, enPath: string, xxPath: string) {
  const en = flatten(loadJson(enPath))
  const xx = flatten(loadJson(xxPath))
  const problems: string[] = []
  for (const k of en.keys()) {
    if (!xx.has(k)) problems.push(`missing (add to ${name}): ${k}`)
  }
  for (const k of xx.keys()) {
    if (!en.has(k)) problems.push(`orphan (not in en — translate everywhere or delete): ${k}`)
  }
  for (const [key, enValue] of en) {
    const value = xx.get(key)
    if (value === undefined) continue // already reported as missing
    const expected = placeholders(enValue)
    const actual = placeholders(value)
    if (expected.join(',') !== actual.join(',')) {
      problems.push(`${key}: placeholders [${actual}] != en [${expected}]`)
    }
    const enVariants = pluralVariants(enValue)
    const variants = pluralVariants(value)
    if (enVariants === 1 ? variants !== 1 : variants < 2) {
      problems.push(`${key}: ${variants} plural variants vs en ${enVariants}`)
    }
  }
  expect(problems, `${name}:\n${problems.join('\n')}`).toEqual([])
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

  // A locale file that exists on disk but is not declared in the layer's
  // nuxt.config is silently never loaded (#322/#330).
  it('module layers: locale files on disk match the nuxt.config declaration', () => {
    for (const mod of readdirSync(MODULES_ROOT)) {
      const i18nDir = resolve(MODULES_ROOT, mod, 'frontend/i18n/locales')
      const config = resolve(MODULES_ROOT, mod, 'frontend/nuxt.config.ts')
      if (!existsSync(i18nDir) || !existsSync(config)) continue
      const onDisk = readdirSync(i18nDir).filter(f => f.endsWith('.json')).sort()
      const declared = [...readFileSync(config, 'utf-8').matchAll(/file:\s*['"]([^'"]+)['"]/g)]
        .map(m => m[1])
        .sort()
      expect(onDisk, `${mod}: locale files on disk vs i18n.locales in nuxt.config.ts`).toEqual(declared)
    }
  })
})
