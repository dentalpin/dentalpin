<script setup lang="ts">
// Razorpay settings — mode, credentials (write-only), webhook secret +
// health. Follows verifactu's/india_gst's precedent of a fully custom
// settings page (not wrapped in the host's generic
// SettingsLayout/SettingsSection).

import { PERMISSIONS } from '~~/app/config/permissions'
import { errorMessage } from '~~/app/utils/error'

definePageMeta({ layout: 'default' })

const { t } = useI18n()
const toast = useToast()
const { can } = usePermissions()
const { currentClinic } = useClinic()
const { getSettings, updateSettings } = useRazorpay()
const runtimeConfig = useRuntimeConfig()

const canManage = computed(() => can(PERMISSIONS.razorpay.settingsWrite))

const isLoading = ref(true)
const isSaving = ref(false)
const settings = ref<Awaited<ReturnType<typeof getSettings>> | null>(null)

const form = ref({
  mode: 'test' as 'test' | 'live',
  key_id: '',
  key_secret: '',
  webhook_secret: '',
  is_active: false
})

const webhookUrl = computed(() => {
  if (!currentClinic.value) return ''
  const base = String(runtimeConfig.public.apiBaseUrl || '').replace(/\/$/, '')
  return `${base}/api/v1/razorpay/webhook/${currentClinic.value.id}`
})

function formatDate(s: string | null): string {
  if (!s) return t('razorpay.settings.never')
  return new Date(s).toLocaleString()
}

onMounted(async () => {
  try {
    settings.value = await getSettings()
    form.value = {
      mode: settings.value.mode,
      key_id: settings.value.key_id ?? '',
      key_secret: '',
      webhook_secret: '',
      is_active: settings.value.is_active
    }
  } catch {
    toast.add({ title: t('common.error'), description: t('razorpay.settings.loadError'), color: 'error' })
  } finally {
    isLoading.value = false
  }
})

async function save() {
  isSaving.value = true
  try {
    const payload: Record<string, unknown> = {
      mode: form.value.mode,
      key_id: form.value.key_id || null,
      is_active: form.value.is_active
    }
    // Write-only: only send a secret when the admin actually typed a
    // new one — never overwrite a configured secret with blank.
    if (form.value.key_secret) payload.key_secret = form.value.key_secret
    if (form.value.webhook_secret) payload.webhook_secret = form.value.webhook_secret

    settings.value = await updateSettings(payload)
    form.value.key_secret = ''
    form.value.webhook_secret = ''
    toast.add({ title: t('common.success'), description: t('razorpay.settings.saved'), color: 'success' })
  } catch (e) {
    toast.add({ title: t('common.error'), description: errorMessage(e, t('razorpay.settings.saveError')), color: 'error' })
  } finally {
    isSaving.value = false
  }
}

async function copyWebhookUrl() {
  try {
    await navigator.clipboard.writeText(webhookUrl.value)
    toast.add({ title: t('razorpay.settings.webhookCopied'), color: 'success' })
  } catch {
    // Clipboard API can be unavailable (permissions, non-secure
    // context) — the URL is still visible to select/copy by hand.
  }
}
</script>

<template>
  <div class="space-y-6 max-w-3xl">
    <h1 class="text-display text-default">
      {{ t('razorpay.settings.title') }}
    </h1>
    <p class="text-subtle">
      {{ t('razorpay.settings.description') }}
    </p>

    <USkeleton
      v-if="isLoading"
      class="h-96 w-full"
    />

    <template v-else>
      <UCard>
        <template #header>
          <h3 class="font-semibold text-default">
            {{ t('razorpay.settings.credentials') }}
          </h3>
        </template>
        <div class="space-y-4">
          <UFormField
            :label="t('razorpay.settings.mode')"
            :hint="t('razorpay.settings.modeHint')"
          >
            <USelectMenu
              v-model="form.mode"
              :items="[
                { label: t('razorpay.settings.modeTest'), value: 'test' },
                { label: t('razorpay.settings.modeLive'), value: 'live' }
              ]"
              value-key="value"
              :disabled="!canManage"
            />
          </UFormField>
          <UFormField
            :label="t('razorpay.settings.keyId')"
            :hint="t('razorpay.settings.keyIdHint')"
          >
            <UInput
              v-model="form.key_id"
              placeholder="rzp_test_xxxxxxxxxxxx"
              :disabled="!canManage"
            />
          </UFormField>
          <UFormField
            :label="t('razorpay.settings.keySecret')"
            :hint="settings?.has_key_secret ? t('razorpay.settings.keySecretConfiguredHint') : t('razorpay.settings.keySecretHint')"
          >
            <UInput
              v-model="form.key_secret"
              type="password"
              :placeholder="settings?.has_key_secret ? '••••••••••••' : t('razorpay.settings.keySecretPlaceholder')"
              :disabled="!canManage"
            />
          </UFormField>
          <div class="flex items-center justify-between">
            <span class="text-sm">{{ t('razorpay.settings.isActive') }}</span>
            <USwitch
              v-model="form.is_active"
              :disabled="!canManage"
            />
          </div>
          <p class="text-caption text-subtle">
            {{ t('razorpay.settings.isActiveHint') }}
          </p>
        </div>
      </UCard>

      <UCard>
        <template #header>
          <h3 class="font-semibold text-default">
            {{ t('razorpay.settings.webhook') }}
          </h3>
        </template>
        <div class="space-y-4">
          <UFormField
            :label="t('razorpay.settings.webhookUrl')"
            :hint="t('razorpay.settings.webhookUrlHint')"
          >
            <div class="flex items-center gap-2">
              <UInput
                :model-value="webhookUrl"
                readonly
                class="flex-1 font-mono text-xs"
              />
              <UButton
                variant="soft"
                icon="i-lucide-copy"
                size="xs"
                @click="copyWebhookUrl"
              >
                {{ t('common.copy') }}
              </UButton>
            </div>
          </UFormField>
          <UFormField
            :label="t('razorpay.settings.webhookSecret')"
            :hint="settings?.has_webhook_secret ? t('razorpay.settings.webhookSecretConfiguredHint') : t('razorpay.settings.webhookSecretHint')"
          >
            <UInput
              v-model="form.webhook_secret"
              type="password"
              :placeholder="settings?.has_webhook_secret ? '••••••••••••' : t('razorpay.settings.webhookSecretPlaceholder')"
              :disabled="!canManage"
            />
          </UFormField>

          <div class="rounded-token-md bg-surface-muted p-3 space-y-1.5">
            <div class="flex items-center justify-between text-caption">
              <span class="text-subtle">{{ t('razorpay.settings.lastWebhookReceived') }}</span>
              <span class="tabular-nums">{{ formatDate(settings?.last_webhook_received_at ?? null) }}</span>
            </div>
            <div class="flex items-center justify-between text-caption">
              <span class="text-subtle">{{ t('razorpay.settings.lastWebhookProcessed') }}</span>
              <span class="tabular-nums">{{ formatDate(settings?.last_webhook_processed_at ?? null) }}</span>
            </div>
            <div
              v-if="settings?.last_webhook_event_type"
              class="flex items-center justify-between text-caption"
            >
              <span class="text-subtle">{{ t('razorpay.settings.lastWebhookEventType') }}</span>
              <span class="font-mono">{{ settings.last_webhook_event_type }}</span>
            </div>
            <div
              v-if="settings?.last_webhook_error"
              class="mt-2 rounded-token-md bg-warning/10 p-2 text-caption text-warning"
            >
              <div class="font-medium">
                {{ t('razorpay.settings.lastWebhookError') }} · {{ formatDate(settings.last_webhook_error_at) }}
              </div>
              <div class="mt-0.5">
                {{ settings.last_webhook_error }}
              </div>
            </div>
          </div>
        </div>
      </UCard>

      <UAlert
        color="neutral"
        variant="subtle"
        icon="i-lucide-info"
        :description="t('razorpay.settings.professionalNotice')"
      />

      <UButton
        v-if="canManage"
        block
        color="primary"
        :loading="isSaving"
        @click="save"
      >
        {{ t('common.save') }}
      </UButton>
    </template>
  </div>
</template>
