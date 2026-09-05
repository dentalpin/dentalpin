// Nuxt layer for the `contacts` module.
export default defineNuxtConfig({
  i18n: {
    locales: [
      { code: 'en', file: 'en.json' },
      { code: 'es', file: 'es.json' },
      { code: 'fr', file: 'fr.json' },
      { code: 'de', file: 'de.json' },
      { code: 'pl', file: 'pl.json' },
      { code: 'it', file: 'it.json' },
      { code: 'hu', file: 'hu.json' },
      { code: 'pt', file: 'pt.json' },
      { code: 'ta', file: 'ta.json' }
    ],
    langDir: 'locales'
  }
})
