// Nuxt layer for the `payments` module.
//
// Issue #53. Pages live under ./pages, components under ./components
// with no folder-prefix so cross-layer auto-imports resolve. Locales
// are declared so @nuxtjs/i18n merges the `payments.*` keys into the
// host's es/en at build time (same pattern as schedules).
export default defineNuxtConfig({
  components: [
    { path: './components', pathPrefix: false }
  ],
  i18n: {
    locales: [
      { code: 'en', file: 'en.json' },
      { code: 'es', file: 'es.json' },
      { code: 'fr', file: 'fr.json' }
    ],
    langDir: 'locales'
  }
})
