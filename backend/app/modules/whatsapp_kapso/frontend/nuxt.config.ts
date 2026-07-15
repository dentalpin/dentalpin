// Nuxt layer for the `whatsapp_kapso` module.
//
// Components auto-resolve with no folder prefix; the i18n block merges our
// `whatsapp_kapso.*` keys into the host es/en.
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
