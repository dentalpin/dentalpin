// Nuxt layer for the `razorpay` module.
//
// Components auto-resolve with no folder prefix; the i18n block merges
// our `razorpay.*` keys into the host's locales.
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
      { code: 'hu', file: 'hu.json' },
      { code: 'pl', file: 'pl.json' },
      { code: 'it', file: 'it.json' }
    ],
    langDir: 'locales'
  }
})
