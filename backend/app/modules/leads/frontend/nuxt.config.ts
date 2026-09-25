// Nuxt layer for the `leads` module.
//
// Components auto-resolve with no folder prefix (LeadConvertDrawer,
// LeadEditModal, LeadsIntakeSettingsPage); the i18n block merges our
// `leads.*` keys into the host locales. Ten locale files with identical
// key sets — frontend/tests/i18n/locale-parity.test.ts fails otherwise.
export default defineNuxtConfig({
  components: [{ path: './components', pathPrefix: false }],
  i18n: {
    locales: [
      { code: 'en', file: 'en.json' },
      { code: 'es', file: 'es.json' },
      { code: 'fr', file: 'fr.json' },
      { code: 'de', file: 'de.json' },
      { code: 'pt', file: 'pt.json' },
      { code: 'it', file: 'it.json' },
      { code: 'pl', file: 'pl.json' },
      { code: 'hu', file: 'hu.json' },
      { code: 'ta', file: 'ta.json' },
      { code: 'ar', file: 'ar.json' }
    ],
    langDir: 'locales'
  }
})
