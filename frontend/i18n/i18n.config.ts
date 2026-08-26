// Message-level fallback: a key missing from the active locale renders
// its English text instead of the raw dotted key. Module layers add
// their locale files independently of the host (#131, #144), so a
// language can ship core-first and the optional modules' UI degrades
// to English until their translations land — never to `some.dotted.key`
// on a clinician's screen (the drift #126 documents).
export default defineI18nConfig(() => ({
  fallbackLocale: 'en',
  missingWarn: false,
  fallbackWarn: false,
  pluralRules: {
    // Polish needs three plural forms — [one, few, many]: 1 klient,
    // 2-4 klienci (except 12-14), 0/5+ klientów. vue-i18n's default
    // two-way rule cannot express this; pl.json messages carry three
    // pipe-separated forms in that order (#144).
    pl: (choice: number, choicesLength: number) => {
      if (choice === 1) return 0
      const teen = choice % 100 >= 12 && choice % 100 <= 14
      const few = choice % 10 >= 2 && choice % 10 <= 4 && !teen
      if (choicesLength === 2) return 1
      return few ? 1 : 2
    }
  }
}))
