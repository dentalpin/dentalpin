import { STORAGE_KEYS } from '~/constants/storage'
import type { Composer } from 'vue-i18n'
import type { CodeLang } from '~/types'
import { SUPPORTED_LOCALES } from '~/constants/languages'

export default defineNuxtPlugin(async (nuxtApp) => {
  const i18n = nuxtApp.$i18n as Composer

  const savedLocale = localStorage.getItem(STORAGE_KEYS.LOCALE) as CodeLang

  if (savedLocale && SUPPORTED_LOCALES.includes(savedLocale) && savedLocale !== i18n.locale.value) {
    await i18n.setLocale(savedLocale)
  }
})
