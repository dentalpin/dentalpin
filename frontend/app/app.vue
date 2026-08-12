<script setup lang="ts">
import { fr, es, en, pt } from '@nuxt/ui/locale'

const { t, locale } = useI18n()

// @nuxt/ui does not ship a Tamil locale yet; fall back to English for
// built-in UI labels while vue-i18n still serves the app's ta messages.
const nuxtUILocales: Record<string, typeof en> = { en, fr, es, pt, ta: en }
const nuxtUILocale = computed(() => nuxtUILocales[locale.value] || en)

useHead(() => ({
  meta: [
    { name: 'viewport', content: 'width=device-width, initial-scale=1' }
  ],
  link: [
    { rel: 'icon', href: '/favicon.ico' }
  ],
  htmlAttrs: {
    lang: locale.value
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
