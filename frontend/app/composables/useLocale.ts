import { STORAGE_KEYS } from '~/constants/storage'
import type { CodeLang } from '~/types'

export function useLocale() {
  const { locale, setLocale, locales } = useI18n()

  const availableLocales = computed(() =>
    (locales.value as Array<{ code: CodeLang, name: string }>).map(l => ({
      code: l.code,
      name: l.name
    }))
  )

  async function changeLocale(code: CodeLang): Promise<void> {
    if (import.meta.client) {
      localStorage.setItem(STORAGE_KEYS.LOCALE, code)
    }
    await setLocale(code)
  }

  return {
    locale,
    currentLocale: computed(() => locale.value),
    availableLocales,
    changeLocale
  }
}
