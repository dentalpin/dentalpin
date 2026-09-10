import { arPluralRule, plPluralRule } from './pluralRules'

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
  pluralRules: { pl: plPluralRule, ar: arPluralRule }
}))
