// Nuxt layer for the `recalls` module.
//
// Components live under ./components with no folder-prefix naming so
// they auto-resolve across layers. The i18n block makes
// @nuxtjs/i18n merge our `recalls.*` keys into the host es/en.
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
