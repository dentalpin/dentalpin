// Nuxt layer for the `schedules` module.
//
// Keeps the same pathPrefix=false convention as the other module layers
// so components auto-import across the host, and declares the i18n
// locale files so @nuxtjs/i18n v9 merges our `schedules.*` translation
// keys into the host's `es` / `en` locales at build time.
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
