// Locale-aware formatters shared by the IA result cards.

export function useCopilotFormat() {
  const { locale } = useI18n()
  // Amounts without an explicit currency are in the clinic's (#1177).
  const { currency: clinicCurrency } = useCurrency()

  function dateTime(iso: string): string {
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return iso
    return new Intl.DateTimeFormat(locale.value, {
      weekday: 'short',
      day: 'numeric',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit'
    }).format(d)
  }

  function timeRange(startIso: string, endIso?: string): string {
    const start = new Date(startIso)
    if (Number.isNaN(start.getTime())) return startIso
    const day = new Intl.DateTimeFormat(locale.value, {
      weekday: 'short',
      day: 'numeric',
      month: 'short'
    }).format(start)
    const t = (d: Date) =>
      new Intl.DateTimeFormat(locale.value, { hour: '2-digit', minute: '2-digit' }).format(d)
    const end = endIso ? new Date(endIso) : null
    const range = end && !Number.isNaN(end.getTime()) ? `${t(start)}–${t(end)}` : t(start)
    return `${day} · ${range}`
  }

  function time(iso: string): string {
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return iso
    return new Intl.DateTimeFormat(locale.value, { hour: '2-digit', minute: '2-digit' }).format(d)
  }

  function money(value: number, currency?: string): string {
    return new Intl.NumberFormat(locale.value, {
      style: 'currency',
      currency: currency || clinicCurrency.value
    }).format(value)
  }

  return { dateTime, timeRange, time, money }
}
