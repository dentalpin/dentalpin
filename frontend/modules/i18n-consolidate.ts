/**
 * Build-time locale consolidation for module layers (#322).
 *
 * `@nuxtjs/i18n` registers every layer's `i18n/locales/<code>.json` as its
 * own lazy chunk, so the bundler processes (layers × locales) files: 26
 * layers × up to 10 locales today, and the prod build's peak memory grows
 * with that count, not with the number of keys (measured on #322: moving
 * host keys into layers pushed the build from 3.9 GB to OOM). This local
 * module rewrites the layer configs during its setup; `@nuxtjs/i18n` only
 * reads them in its `modules:done` hook, so install order does not matter.
 * It merges every layer's locale files into one generated file per
 * locale, hands that single file to the host locale entry, and
 * removes the per-layer i18n config so the bundler sees 10 files instead
 * of ~220.
 *
 * Precedence is unchanged. `@nuxtjs/i18n` orders files so that an
 * earlier layer overrides a later one and the host overrides all layers;
 * the merge below walks layers last-to-first (later layers lose) and the
 * consolidated file is placed before the host file (host wins).
 *
 * Opt out with `NUXT_I18N_CONSOLIDATE=0` (used by the memory comparison
 * in the issue and by anyone debugging a single layer's file).
 */
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { defineNuxtModule, useLogger } from '@nuxt/kit'

type Json = Record<string, unknown>

interface LayerLocale { code: string, file?: string, files?: (string | { path: string })[] }
interface LayerI18n { locales?: (string | LayerLocale)[], langDir?: string, restructureDir?: string | false }

function isPlainObject(value: unknown): value is Json {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/** Deep merge where `override` wins; arrays and scalars are replaced. */
function deepMerge(base: Json, override: Json): Json {
  const out: Json = { ...base }
  for (const [key, value] of Object.entries(override)) {
    const current = out[key]
    out[key] = isPlainObject(current) && isPlainObject(value) ? deepMerge(current, value) : value
  }
  return out
}

function localeFiles(locale: LayerLocale): string[] {
  if (locale.files) return locale.files.map(f => (typeof f === 'string' ? f : f.path))
  return locale.file ? [locale.file] : []
}

/**
 * Merge per-layer locale data into one object per locale code. `layers` is
 * in Nuxt `_layers` order (highest precedence first); the walk goes
 * last-to-first so an earlier layer's keys win, matching the order
 * @nuxtjs/i18n loads the separate files in.
 */
export function mergeLayerLocales(layers: { code: string, data: Json }[][]): Map<string, Json> {
  const merged = new Map<string, Json>()
  for (const layer of [...layers].reverse()) {
    for (const { code, data } of layer) {
      merged.set(code, deepMerge(merged.get(code) ?? {}, data))
    }
  }
  return merged
}

export default defineNuxtModule({
  meta: { name: 'dentalpin:i18n-consolidate' },
  setup(_options, nuxt) {
    // Dev keeps the per-layer files so editing one hot-reloads; the chunk
    // count only matters for the production bundle.
    if (nuxt.options.dev || process.env.NUXT_I18N_CONSOLIDATE === '0') return
    const logger = useLogger('i18n-consolidate')

    const layers = nuxt.options._layers.slice(1)
    const perLayer: { code: string, data: Json }[][] = []
    let fileCount = 0
    let layerCount = 0

    for (const layer of layers) {
      const i18n = layer.config.i18n as LayerI18n | undefined
      if (!i18n?.locales) continue
      const langDir = resolve(
        layer.config.rootDir,
        i18n.restructureDir === false ? '' : (i18n.restructureDir ?? 'i18n'),
        i18n.langDir ?? 'locales'
      )
      const entries: { code: string, data: Json }[] = []
      for (const locale of i18n.locales) {
        if (typeof locale === 'string') continue
        for (const file of localeFiles(locale)) {
          const path = resolve(langDir, file)
          if (!existsSync(path)) {
            logger.warn(`Locale file missing, skipped: ${path}`)
            continue
          }
          entries.push({ code: locale.code, data: JSON.parse(readFileSync(path, 'utf8')) as Json })
          fileCount++
        }
      }
      perLayer.push(entries)
      delete layer.config.i18n
      layerCount++
    }
    if (fileCount === 0) return
    const merged = mergeLayerLocales(perLayer)

    const outDir = join(nuxt.options.rootDir, 'node_modules', '.cache', 'dentalpin-i18n')
    mkdirSync(outDir, { recursive: true })
    const generated = new Map<string, string>()
    for (const [code, data] of merged) {
      const path = join(outDir, `${code}.json`)
      writeFileSync(path, JSON.stringify(data))
      generated.set(code, path)
    }

    // Prepend the consolidated file to the host entry for the same locale:
    // @nuxtjs/i18n loads files in array order and later files override, so
    // the host file keeps the last word. Both the resolved options and the
    // project layer's raw config are read by the module; update both.
    const rewrite = (locales: (string | LayerLocale)[] | undefined) => {
      if (!locales) return locales
      return locales.map((locale) => {
        if (typeof locale === 'string') return locale
        const extra = generated.get(locale.code)
        const own = localeFiles(locale)
        const { file: _file, files: _files, ...rest } = locale
        return { ...rest, files: extra ? [extra, ...own] : own }
      })
    }
    const hostI18n = nuxt.options.i18n as LayerI18n | undefined
    if (hostI18n) hostI18n.locales = rewrite(hostI18n.locales)
    const projectI18n = nuxt.options._layers[0]?.config.i18n as LayerI18n | undefined
    if (projectI18n) projectI18n.locales = rewrite(projectI18n.locales)

    logger.info(`Consolidated ${fileCount} layer locale files from ${layerCount} layers into ${generated.size} files`)
  }
})
