/**
 * Shared vue-i18n plural rules (pure, framework-free so tests can import
 * them without a Nuxt context).
 */

export function plPluralRule(choice: number, choicesLength: number): number {
  if (choice === 1) return 0
  const teen = choice % 100 >= 12 && choice % 100 <= 14
  const few = choice % 10 >= 2 && choice % 10 <= 4 && !teen
  if (choicesLength === 2) return 1
  return few ? 1 : 2
}

// Arabic pluralization (vue-i18n `choice`): CLDR gives Arabic six
// categories. The rule maps a count to the index vue-i18n uses to pick
// the pipe segment: 0 → zero, 1 → one, 2 → two, 3-10 → few,
// 11-99 → many, everything else → other (index 5).
// NOTE (#389): every ar.json message today carries exactly two segments,
// so only the `choicesLength === 2` shortcut runs. The six-way tail stays
// deliberately — it is clamped to `choicesLength - 1`, so a future
// three-plus-form message resolves correctly instead of silently picking
// the wrong segment. Pinned by tests/i18n/plural-rules.test.ts.
export function arPluralRule(choice: number, choicesLength: number): number {
  const max = choicesLength - 1
  if (choicesLength === 2) return choice === 1 ? 0 : Math.min(1, max)
  const mod100 = Math.abs(choice) % 100
  if (choice === 0) return Math.min(0, max)
  if (choice === 1) return Math.min(1, max)
  if (choice === 2) return Math.min(2, max)
  if (mod100 >= 3 && mod100 <= 10) return Math.min(3, max)
  if (mod100 >= 11 && mod100 <= 99) return Math.min(4, max)
  return Math.min(5, max)
}
