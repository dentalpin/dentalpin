<script setup lang="ts">
/**
 * Patient check-in page (agenda). Mounted at `/p/check-in/<token>`
 * and bypasses the global auth middleware (public route, same as
 * `/p/budget/<token>`). The token is the auth: the browser redeems it
 * by path segment so proxies and Referer headers never see it in a
 * query string.
 *
 * ADR 0037: the `source` claim decides the behaviour. A `counter` token
 * was scanned in the clinic (presence proven) and auto-submits on load;
 * a `reminder` link may be pre-fetched by mail scanners, so it renders
 * a confirm button and only POSTs on press. Missing/unrecognised source
 * fails safe to the confirm path, never auto-submit.
 */
import { parseCheckinResult } from '../../../utils/checkinResult'

definePageMeta({
  layout: 'public'
})

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const config = useRuntimeConfig()

type State = 'loading' | 'confirm' | 'done' | 'invalid' | 'tooEarly' | 'tooLate'
const state = ref<State>('loading')
const startsAt = ref('')

function sourceOf(token: string): string {
  try {
    const payload = token.split('.')[1] ?? ''
    const decoded = JSON.parse(atob(payload.replace(/-/g, '+').replace(/_/g, '/')))
    return typeof decoded.source === 'string' ? decoded.source : 'reminder'
  } catch {
    return 'reminder'
  }
}

async function submit(token: string) {
  state.value = 'loading'
  try {
    await $fetch(`/api/v1/agenda/public/check-in/${token}`, {
      baseURL: config.public.apiBaseUrl,
      method: 'POST'
    })
    state.value = 'done'
  } catch (e: unknown) {
    // The global HTTP handler stringifies error details, so the window
    // code travels as `too_early:<HH:MM>` / `window_closed` (ADR 0037).
    // parseCheckinResult splits on the FIRST colon: the time itself
    // contains one, and splitting on every colon drops the minutes.
    const message = (e as { data?: { message?: string } })?.data?.message ?? ''
    const parsed = parseCheckinResult(message)
    if (parsed.code === 'too_early') {
      startsAt.value = parsed.time
      state.value = 'tooEarly'
    } else if (parsed.code === 'window_closed') {
      state.value = 'tooLate'
    } else {
      state.value = 'invalid'
    }
  }
}

onMounted(async () => {
  const token = route.params.token
  if (typeof token !== 'string' || !token) {
    state.value = 'invalid'
    return
  }
  if (sourceOf(token) === 'counter') {
    await submit(token)
  } else {
    state.value = 'confirm'
  }
})

function confirm() {
  const token = route.params.token
  if (typeof token === 'string' && token) {
    void submit(token)
  }
}
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
        <div v-else-if="state === 'confirm'">
          <p>{{ t('appointments.checkin.confirmHint') }}</p>
          <UButton
            class="mt-4"
            @click="confirm"
          >
            {{ t('appointments.checkin.confirm') }}
          </UButton>
        </div>
        <p v-else-if="state === 'done'">
          {{ t('appointments.checkin.success') }}
        </p>
        <p v-else-if="state === 'tooEarly'">
          {{ t('appointments.checkin.tooEarly', { time: startsAt }) }}
        </p>
        <p v-else-if="state === 'tooLate'">
          {{ t('appointments.checkin.tooLate') }}
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
