<script setup lang="ts">
definePageMeta({
  layout: 'guest'
})

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const config = useRuntimeConfig()

type State = 'loading' | 'done' | 'invalid'
const state = ref<State>('loading')

onMounted(async () => {
  const token = route.query.t
  if (typeof token !== 'string' || !token) {
    state.value = 'invalid'
    return
  }
  try {
    await $fetch('/api/v1/agenda/public/check-in', {
      baseURL: config.public.apiBaseUrl,
      method: 'POST',
      body: { token }
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
