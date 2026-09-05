// Nuxt layer for the `staff_tasks` module.
export default defineNuxtConfig({
  i18n: {
    locales: [
      { code: 'en', file: 'en.json' },
      { code: 'es', file: 'es.json' },
      { code: 'fr', file: 'fr.json' },
      { code: 'de', file: 'de.json' },
      { code: 'hu', file: 'hu.json' },
      { code: 'pt', file: 'pt.json' },
      { code: 'ta', file: 'ta.json' },
      { code: 'pl', file: 'pl.json' },
      { code: 'it', file: 'it.json' }
    ],
    langDir: 'locales'
  }
})
