// Nuxt layer for the `treatment_consumables` module.
export default defineNuxtConfig({
  i18n: {
    locales: [
      { code: 'en', file: 'en.json' },
      { code: 'es', file: 'es.json' },
      { code: 'fr', file: 'fr.json' },
      { code: 'pt', file: 'pt.json' },
      { code: 'ta', file: 'ta.json' },
      { code: 'de', file: 'de.json' },
      { code: 'hu', file: 'hu.json' }
    ],
    langDir: 'locales'
  }
})
