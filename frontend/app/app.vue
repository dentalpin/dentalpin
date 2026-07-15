<script setup lang="ts">
import { fr, es, en } from '@nuxt/ui/locale'

const { t, locale } = useI18n()

const nuxtUILocales: Record<string, typeof en> = { en, fr, es }
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
