export default defineNuxtConfig({
  components: [
    { path: './components', pathPrefix: false }
  ],
  i18n: {
    locales: [
      { code: 'en', file: 'en.json' },
      { code: 'es', file: 'es.json' },
      { code: 'fr', file: 'fr.json' },
      { code: 'de', file: 'de.json' },
      { code: 'pl', file: 'pl.json' },
      { code: 'it', file: 'it.json' },
      { code: 'ar', file: 'ar.json' },
      { code: 'ta', file: 'ta.json' },
      { code: 'hu', file: 'hu.json' },
      { code: 'pt', file: 'pt.json' }
    ],
    langDir: 'locales'
  }
})
