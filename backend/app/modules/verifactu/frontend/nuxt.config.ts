// Nuxt layer for the `verifactu` module (Spain AEAT compliance).
//
// Components auto-import with no folder prefix to match other layers.
// i18n keys are namespaced under `verifactu.*` so they don't collide
// with host or other modules.
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
