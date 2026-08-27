// Nuxt layer for the `medication_catalog` module.
export default defineNuxtConfig({
  i18n: {
    locales: [
      { code: 'en', file: 'en.json' },
      { code: 'es', file: 'es.json' },
      { code: 'de', file: 'de.json' },
      { code: 'fr', file: 'fr.json' },
      { code: 'pt', file: 'pt.json' },
      { code: 'hu', file: 'hu.json' },
      { code: 'pl', file: 'pl.json' },
      { code: 'it', file: 'it.json' },
      { code: 'ta', file: 'ta.json' }
    ],
    langDir: 'locales'
  }
})
