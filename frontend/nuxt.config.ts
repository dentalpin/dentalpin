// https://nuxt.com/docs/api/configuration/nuxt-config
import { readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

/**
 * Load Nuxt Layer paths from `modules.json`.
 *
 * The backend writes this file whenever a module with a declared
 * `manifest.frontend.layer_path` is installed. When absent (fresh
 * checkout, no community modules yet), returns an empty array.
 */
function loadModuleLayers(): string[] {
  const path = resolve(__dirname, 'modules.json')
  try {
    const raw = readFileSync(path, 'utf-8')
    const payload = JSON.parse(raw) as { layers?: string[] }
    return Array.isArray(payload.layers) ? payload.layers : []
  } catch (err: unknown) {
    const code = (err as { code?: string }).code
    if (code !== 'ENOENT') {
      console.warn('[nuxt.config] modules.json is malformed, using empty layers:', err)
    }
    return []
  }
}

const moduleLayers = loadModuleLayers()
const modulesJsonPath = resolve(__dirname, 'modules.json')
writeFileSync('/tmp/debug-layers.json', JSON.stringify({
  layers: moduleLayers,
  modulesJsonPath,
  cwd: process.cwd(),
  dirname: __dirname
}, null, 2))

export default defineNuxtConfig({

  extends: moduleLayers,

  modules: [
    '@nuxt/eslint',
    '@nuxt/ui',
    '@nuxtjs/i18n',
    // TEMPORARY DEBUG MODULE — inline module gets `nuxt` reliably as its
    // 2nd arg (unlike the config-level `hooks` key, which passed undefined
    // for 'modules:done' in this Nuxt version). Remove this whole entry
    // once the payroll layer-resolution issue is diagnosed.
    (_options: unknown, nuxt: any) => {
      nuxt.hook('modules:done', () => {
        try {
          writeFileSync('/tmp/debug-resolved-layers.json', JSON.stringify({
            resolvedLayerCwds: nuxt.options._layers?.map((l: any) => l.cwd) ?? 'NO _layers FOUND',
            resolvedLayerSrcDirs: nuxt.options._layers?.map((l: any) => l.config?.srcDir ?? null) ?? null,
            resolvedLayerPagesDir: nuxt.options._layers?.map((l: any) => l.config?.dir?.pages ?? null) ?? null,
            resolvedLayerConfigNames: nuxt.options._layers?.map((l: any) => l.config?.name ?? null) ?? null,
            totalResolvedLayers: nuxt.options._layers?.length ?? -1
          }, null, 2))
        } catch (hookErr: unknown) {
          writeFileSync('/tmp/debug-resolved-layers-error.json', JSON.stringify({
            error: String(hookErr),
            stack: hookErr instanceof Error ? hookErr.stack : null
          }, null, 2))
        }
      })
    }
  ],

  components: [
    {
      path: '~/components',
      pathPrefix: false
    }
  ],

  devtools: {
    enabled: true
  },
  app: {
    head: {
      title: 'DentalPin',
      link: [
        { rel: 'icon', type: 'image/svg+xml', href: '/favicon.svg' }
      ]
    }
  },

  css: ['~/assets/css/main.css'],

  // Default to light mode; users can opt into dark via the toggle. Both
  // ``preference`` and ``fallback`` are set so SSR + first-paint render
  // light without a flash even before client hydration reads OS prefs.
  colorMode: {
    preference: 'light',
    fallback: 'light'
  },

  runtimeConfig: {
    // Server-side only (for SSR inside Docker)
    apiBaseUrlServer: process.env.API_BASE_URL_SERVER || 'http://backend:8000',
    public: {
      // Client-side (browser)
      apiBaseUrl: process.env.API_BASE_URL || 'http://localhost:8000',
      demoMode: process.env.NUXT_PUBLIC_DEMO_MODE === 'true',
      // Documentation portal origin used by the in-app help drawer
      // (Fase 5 of issue #75). Empty disables the help button.
      docsUrl: process.env.NUXT_PUBLIC_DOCS_URL || 'https://docs.dentalpin.com'
    }
  },
  srcDir: 'app',

  // Restart dev server when the backend rewrites `modules.json` on
  // module install/uninstall. `extends` is evaluated once at config
  // boot, so a layer added after Nuxt started is invisible until
  // restart. Watching the file makes the round-trip automatic.
  watch: [modulesJsonPath],

  compatibilityDate: '2025-01-15',

  vite: {
    optimizeDeps: {
      // Pre-bundle deps that Vite otherwise discovers at runtime. Runtime
      // discovery triggers a full page reload, which in CI races Playwright's
      // `goto` and causes net::ERR_ABORTED on the very first visit to any
      // route that uses these packages.
      include: [
        'nprogress',
        '@vueuse/core',
        '@vue/devtools-core',
        '@vue/devtools-kit'
      ]
    }
  },

  eslint: {
    config: {
      stylistic: {
        commaDangle: 'never',
        braceStyle: '1tbs'
      }
    }
  },

  i18n: {
    locales: [
      { code: 'en', name: 'English', file: 'en.json' },
      { code: 'es', name: 'Español', file: 'es.json' },
      { code: 'fr', name: 'Français', file: 'fr.json' },
      { code: 'pt', name: 'Português', file: 'pt.json' }
    ],
    defaultLocale: 'en',
    lazy: true,
    langDir: 'locales',
    strategy: 'no_prefix',
    detectBrowserLanguage: false
  },

  // Pre-bundle every `i-lucide-*` icon referenced in source into the client
  // bundle. Without this, @nuxt/icon fetches icons lazily per-name on client
  // navigation, which causes the sidebar to briefly render a stale / wrong
  // icon (e.g. the settings cog showing up next to "Pacientes") until the
  // real icon resolves.
  icon: {
    clientBundle: {
      scan: true,
      sizeLimitKb: 512
    }
  }
})