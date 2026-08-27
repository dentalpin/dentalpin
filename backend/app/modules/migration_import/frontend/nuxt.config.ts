// Nuxt layer for the `migration_import` module.
//
// Settings page only — registered via the host's settings registry from
// `plugins/settings.client.ts`. No top-level navigation.
export default defineNuxtConfig({
  components: [
    { path: './components', pathPrefix: false }
  ],
  i18n: {
    locales: [
      { code: 'en', file: 'en.json' },
      { code: 'es', file: 'es.json' },
      { code: 'fr', file: 'fr.json' },
      { code: 'pt', file: 'pt.json' },
      { code: 'ta', file: 'ta.json' },
      { code: 'de', file: 'de.json' },
      { code: 'pl', file: 'pl.json' },
      { code: 'it', file: 'it.json' }
    ],
    langDir: 'locales'
  }
})
