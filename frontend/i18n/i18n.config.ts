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
  pluralRules: { pl: plPluralRule, ar: arPluralRule },
  // Named date format used by the module detail modal (`d(value, 'short')`).
  // Registered for every shipped locale so no locale falls back with a
  // console warning (L18 parity applies to config-level formats too).
  datetimeFormats: {
    es: { short: { dateStyle: 'short', timeStyle: 'short' } },
    en: { short: { dateStyle: 'short', timeStyle: 'short' } },
    de: { short: { dateStyle: 'short', timeStyle: 'short' } },
    fr: { short: { dateStyle: 'short', timeStyle: 'short' } },
    hu: { short: { dateStyle: 'short', timeStyle: 'short' } },
    it: { short: { dateStyle: 'short', timeStyle: 'short' } },
    pl: { short: { dateStyle: 'short', timeStyle: 'short' } },
    pt: { short: { dateStyle: 'short', timeStyle: 'short' } },
    ta: { short: { dateStyle: 'short', timeStyle: 'short' } },
    ar: { short: { dateStyle: 'short', timeStyle: 'short' } }
  }
}))
