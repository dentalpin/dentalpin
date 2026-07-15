// Single source of truth for rendering money in the frontend.
// - Currency comes from `currentClinic.currency` (one clinic = one currency).
// - Locale follows the user's UI language (Intl handles separators/symbols).
//
// Components that render money should call `format()` (or use the `<Money>`
// component, which delegates here). No callsite should hardcode 'EUR' or
// inline `Intl.NumberFormat`.

export function useCurrency() {
  const { currentClinic } = useClinic()
  const { currentLocale } = useLocale()

  function format(amount: number | string | null | undefined): string {
    if (amount == null || amount === '') return '—'
    const value = typeof amount === 'string' ? Number(amount) : amount
    if (Number.isNaN(value)) return '—'
    const currency = currentClinic.value?.currency ?? 'EUR'
    return new Intl.NumberFormat(currentLocale.value, {
      style: 'currency',
      currency
    }).format(value)
  }

  function symbol(): string {
    const currency = currentClinic.value?.currency ?? 'EUR'
    const parts = new Intl.NumberFormat(currentLocale.value, {
      style: 'currency',
      currency,
      currencyDisplay: 'narrowSymbol'
    }).formatToParts(0)
    return parts.find(p => p.type === 'currency')?.value ?? currency
  }

  return {
    format,
    symbol,
    currency: computed(() => currentClinic.value?.currency ?? 'EUR')
  }
}
