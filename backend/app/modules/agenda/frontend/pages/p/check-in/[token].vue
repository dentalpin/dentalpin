<script setup lang="ts">
/**
 * Patient QR check-in page (agenda). Mounted at `/p/check-in/<token>`
 * and bypasses the global auth middleware (public route, same as
 * `/p/budget/<token>`). The token (15 min, single appointment) is the
 * auth: the browser redeems it by path segment so proxies and Referer
 * headers never see it in a query string.
 */
definePageMeta({
  layout: 'public'
})

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const config = useRuntimeConfig()

type State = 'loading' | 'done' | 'invalid'
const state = ref<State>('loading')

onMounted(async () => {
  const token = route.params.token
  if (typeof token !== 'string' || !token) {
    state.value = 'invalid'
    return
  }
  try {
    await $fetch(`/api/v1/agenda/public/check-in/${token}`, {
      baseURL: config.public.apiBaseUrl,
      method: 'POST'
    })
    state.value = 'done'
  } catch {
    state.value = 'invalid'
  }
})
</script>

<template>
  <div class="min-h-screen flex items-center justify-center p-4">
    <UCard class="w-full max-w-sm text-center">
      <template #header>
        <h1 class="text-h2">
          {{ t('appointments.checkin.openTitle') }}
        </h1>
      </template>
      <div class="py-6">
        <p v-if="state === 'loading'">
          {{ t('common.loading') }}
        </p>
        <p v-else-if="state === 'done'">
          {{ t('appointments.checkin.success') }}
        </p>
        <div v-else>
          <p>{{ t('appointments.checkin.invalid') }}</p>
          <UButton
            class="mt-4"
            color="neutral"
            variant="ghost"
            @click="router.go(0)"
          >
            {{ t('common.retry') }}
          </UButton>
        </div>
      </div>
    </UCard>
  </div>
</template>
