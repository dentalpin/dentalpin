// https://nuxt.com/docs/api/configuration/nuxt-config
import { readFileSync } from 'node:fs'
import { isAbsolute, join, resolve } from 'node:path'

/**
 * Load Nuxt Layer paths from `modules.json`.
 *
 * The backend writes this file whenever a module with a declared
 * `manifest.frontend.layer_path` is installed. When absent (fresh
 * checkout, no community modules yet), returns an empty array.
 */
function loadModuleLayers(): {
  layers: string[]
  names: string[]
  routes: Record<string, string>
} {
  const path = resolve(__dirname, 'modules.json')
  try {
    const raw = readFileSync(path, 'utf-8')
    const payload = JSON.parse(raw) as {
      layers?: string[]
      modules?: { name: string, routes?: string[] }[]
    }
    const modules = Array.isArray(payload.modules) ? payload.modules : []
    // Route pattern → owning module (issue #326): the module-gate route
    // middleware 404s pages of baked-but-uninstalled modules.
    const routes: Record<string, string> = {}
    for (const m of modules) {
      for (const r of m.routes ?? []) routes[r] = m.name
    }
    return {
      layers: Array.isArray(payload.layers) ? payload.layers : [],
      names: modules.map(m => m.name),
      routes
    }
  } catch (err: unknown) {
    const code = (err as { code?: string }).code
    if (code !== 'ENOENT') {
      console.warn('[nuxt.config] modules.json is malformed, using empty layers:', err)
    }
    return { layers: [], names: [], routes: {} }
  }
}

const { layers: moduleLayers, names: moduleLayerNames, routes: moduleRoutes } = loadModuleLayers()
const modulesJsonPath = resolve(__dirname, 'modules.json')
// Layers referenced by a path inside this directory (`./module_layers/...`,
// the symlink CI and ESLint use). Nuxt only auto-includes layers that live
// outside rootDir or under `layers/*/app` in the generated tsconfig, so
// without an explicit include `nuxt typecheck` silently skips every layer
// page. Absolute paths (the Docker mount) are outside rootDir and already
// included by Nuxt itself.
const localLayers = moduleLayers.filter(layer => !isAbsolute(layer))

export default defineNuxtConfig({

  extends: moduleLayers,

  modules: [
    '@nuxt/eslint',
    '@nuxt/ui',
    '@nuxtjs/i18n'
  ],

  components: [
    {
      path: '~/components',
      pathPrefix: false
    }
  ],

  devtools: {
    // Vite devtools full-page reloads (optimizeDeps discovery and the
    // devtools client itself) abort Playwright `goto` mid-navigation
    // (#260). Pre-bundling @vue/devtools-* below is not enough on its
    // own, so e2e contexts disable devtools with NUXT_DEVTOOLS=false
    // (CI does; locally: NUXT_DEVTOOLS=false docker compose up -d
    // frontend). Daily DX stays on by default.
    enabled: process.env.NUXT_DEVTOOLS !== 'false'
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
      docsUrl: process.env.NUXT_PUBLIC_DOCS_URL || 'https://docs.dentalpin.com',
      // Module layers baked into this build. `usePermissions().can()`
      // hides their permissions while the backend reports the module as
      // not installed (prod bakes every layer — see Dockerfile.prod).
      moduleLayers: moduleLayerNames,
      moduleRoutes
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

  typescript: {
    tsConfig: {
      include: localLayers.map(layer => join('..', layer, '**/*')),
      // Layer nuxt.config files belong to the node tsconfig, not the app one.
      exclude: localLayers.map(layer => join('..', layer, 'nuxt.config.*'))
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
      { code: 'pt', name: 'Português', file: 'pt.json' },
      { code: 'ta', name: 'தமிழ்', file: 'ta.json' },
      { code: 'de', name: 'Deutsch', file: 'de.json' },
      { code: 'hu', name: 'Magyar', file: 'hu.json' },
      { code: 'pl', name: 'Polski', file: 'pl.json' },
      { code: 'it', name: 'Italiano', file: 'it.json' },
      { code: 'ar', name: 'العربية', file: 'ar.json', dir: 'rtl' }
    ],
    defaultLocale: 'en',
    lazy: true,
    langDir: 'locales',
    strategy: 'no_prefix',
    // Persist the chosen locale in a cookie the server can read, so SSR
    // renders in the user's language. Locale-dependent DOM *attributes*
    // (placeholder, title, aria-label) are not patched during hydration,
    // so an English server render used to survive until the next
    // client-side navigation (#235, #202). First visit without the
    // cookie falls back to Accept-Language, then to `en`.
    detectBrowserLanguage: {
      useCookie: true,
      cookieKey: 'dentalpin_locale',
      fallbackLocale: 'en'
    }
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
