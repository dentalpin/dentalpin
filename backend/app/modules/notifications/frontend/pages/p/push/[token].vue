<script setup lang="ts">
/**
 * Patient push-subscribe page (notifications T6). Mounted at
 * `/p/push/<token>` and bypasses the global auth middleware (public
 * route, same as `/p/budget/<token>`). The token (24 h, single use)
 * is the auth: the browser redeems it with its subscription.
 */
import type { ApiResponse } from '~~/app/types'

definePageMeta({ layout: 'public' })

const { t } = useI18n()
const route = useRoute()
const config = useRuntimeConfig()

const token = computed(() => route.params.token as string)
const clinicName = ref('')
const state = ref<'loading' | 'ready' | 'done' | 'invalid' | 'unsupported' | 'denied' | 'error'>('loading')

interface TokenInfo {
  valid: boolean
  clinic_name: string
  expires_at: string
  public_key: string
}

async function apiBase(): Promise<string> {
  return import.meta.server ? config.apiBaseUrlServer : config.public.apiBaseUrl
}

function urlsafeToUint8(base64url: string): Uint8Array {
  const padded = base64url.replace(/-/g, '+').replace(/_/g, '/')
  const raw = atob(padded + '='.repeat((4 - (padded.length % 4)) % 4))
  return Uint8Array.from([...raw].map(c => c.charCodeAt(0)))
}

onMounted(async () => {
  if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
    state.value = 'unsupported'
    return
  }
  try {
    const base = await apiBase()
    const res = await $fetch<ApiResponse<TokenInfo>>(
      `${base}/api/v1/notifications/public/push/subscribe/${token.value}`
    )
    if (!res.data.valid) {
      state.value = 'invalid'
      return
    }
    clinicName.value = res.data.clinic_name
    state.value = 'ready'
  } catch {
    state.value = 'invalid'
  }
})

async function enable() {
  try {
    const permission = await Notification.requestPermission()
    if (permission !== 'granted') {
      state.value = 'denied'
      return
    }
    const base = await apiBase()
    const info = await $fetch<ApiResponse<TokenInfo>>(
      `${base}/api/v1/notifications/public/push/subscribe/${token.value}`
    )
    const registration = await navigator.serviceWorker.register('/push-sw.js')
    const subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlsafeToUint8(info.data.public_key)
    })
    const raw = subscription.toJSON()
    await $fetch(`${base}/api/v1/notifications/public/push/subscribe/${token.value}`, {
      method: 'POST',
      body: {
        endpoint: raw.endpoint,
        keys: raw.keys,
        user_agent: navigator.userAgent
      }
    })
    state.value = 'done'
  } catch {
    state.value = 'error'
  }
}
</script>

<template>
  <div class="mx-auto max-w-md p-6 text-center">
    <h1 class="text-xl font-semibold">
      {{ t('notifications.pushSubscribe.title') }}
    </h1>
    <p
      v-if="state === 'ready'"
      class="mt-2 text-sm text-gray-600"
    >
      {{ t('notifications.pushSubscribe.clinicLine', { clinic: clinicName }) }}
    </p>
    <UButton
      v-if="state === 'ready'"
      class="mt-4"
      @click="enable"
    >
      {{ t('notifications.pushSubscribe.enable') }}
    </UButton>
    <p
      v-if="state === 'done'"
      class="mt-4 text-sm"
    >
      {{ t('notifications.pushSubscribe.enabled') }}
    </p>
    <p
      v-if="state === 'invalid'"
      class="mt-4 text-sm"
    >
      {{ t('notifications.pushSubscribe.invalid') }}
    </p>
    <p
      v-if="state === 'unsupported'"
      class="mt-4 text-sm"
    >
      {{ t('notifications.pushSubscribe.unsupported') }}
    </p>
    <p
      v-if="state === 'denied'"
      class="mt-4 text-sm"
    >
      {{ t('notifications.pushSubscribe.denied') }}
    </p>
    <p
      v-if="state === 'error'"
      class="mt-4 text-sm"
    >
      {{ t('notifications.pushSubscribe.error') }}
    </p>
  </div>
</template>
