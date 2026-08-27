export default defineNuxtConfig({
  components: [
    { path: './components', pathPrefix: false }
  ],
  i18n: {
    locales: [
      { code: 'en', file: 'en.json' },
      { code: 'es', file: 'es.json' },
      { code: 'de', file: 'de.json' },
      { code: 'hu', file: 'hu.json' }
    ],
    langDir: 'locales'
  }
})
