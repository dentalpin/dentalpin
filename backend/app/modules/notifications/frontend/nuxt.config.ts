// Nuxt layer for the `notifications` module.
//
// Components live under ./components with no folder-prefix naming
// (matches host convention so <PatientQuickInfo /> and friends resolve
// across layers).
export default defineNuxtConfig({
  components: [
    { path: './components', pathPrefix: false }
  ],
  i18n: {
    locales: [
      { code: 'en', file: 'notifications-en.json' },
      { code: 'es', file: 'notifications-es.json' },
      { code: 'fr', file: 'notifications-fr.json' },
      { code: 'pt', file: 'notifications-pt.json' },
      { code: 'ta', file: 'notifications-ta.json' },
      { code: 'de', file: 'notifications-de.json' },
      { code: 'pl', file: 'notifications-pl.json' },
      { code: 'it', file: 'notifications-it.json' }
    ],
    langDir: 'locales'
  }
})
