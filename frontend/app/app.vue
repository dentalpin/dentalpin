<script setup lang="ts">
import { fr, es, en, pt, de, hu, ar } from '@nuxt/ui/locale'

const { t, locale } = useI18n()

// @nuxt/ui does not ship a Tamil locale yet; fall back to English for
// built-in UI labels while vue-i18n still serves the app's ta messages.
const nuxtUILocales: Record<string, typeof en> = { en, fr, es, pt, de, hu, ar, ta: en }
const nuxtUILocale = computed(() => nuxtUILocales[locale.value] || en)

// Direction comes from the Nuxt UI locale entry (ar has dir: 'rtl').
const htmlDir = computed(() => nuxtUILocale.value.dir ?? 'ltr')

useHead(() => ({
  meta: [
    { name: 'viewport', content: 'width=device-width, initial-scale=1' }
  ],
  link: [
    { rel: 'icon', href: '/favicon.ico' }
  ],
  htmlAttrs: {
    lang: locale.value,
    dir: htmlDir.value
  }
}))

useSeoMeta({
  title: 'DentalPin',
  description: t('app.tagline')
})
</script>

<template>
  <UApp :locale="nuxtUILocale">
    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>
  </UApp>
</template>
