<script setup lang="ts">
import { useSmsGateway } from '../composables/useSmsGateway'

const { t } = useI18n()
const toast = useToast()
const { settings, providers, outbox, loading, saving, fetchProviders, fetchSettings, saveSettings, fetchOutbox } = useSmsGateway()

const form = reactive({
  provider_name: 'placeholder',
  api_key: '',
  sender_id: '',
  base_url: '',
  is_active: false
})

const providerOptions = computed(() => providers.value.map(p => ({ value: p, label: p })))
const isPlaceholder = computed(() => form.provider_name === 'placeholder')

onMounted(async () => {
  await Promise.all([fetchProviders(), fetchSettings(), fetchOutbox()])
  if (settings.value) {
    form.provider_name = settings.value.provider_name
    form.sender_id = settings.value.sender_id ?? ''
    form.base_url = settings.value.base_url ?? ''
    form.is_active = settings.value.is_active
  }
})

async function onSave() {
  const payload: Record<string, unknown> = {
    provider_name: form.provider_name,
    sender_id: form.sender_id || null,
    base_url: form.base_url || null,
    is_active: form.is_active
  }
  // Only send the secret when the user actually typed a new one.
  if (form.api_key) payload.api_key = form.api_key

  await saveSettings(payload)
  form.api_key = ''
  toast.add({ title: t('sms_gateway.settings.saved'), color: 'success' })
  await fetchOutbox()
}
</script>

<template>
  <div class="space-y-6">
    <div>
      <h2 class="text-h3 text-default">
        {{ t('sms_gateway.settings.title') }}
      </h2>
      <p class="text-caption text-subtle">
        {{ t('sms_gateway.settings.description') }}
      </p>
    </div>

    <div v-if="isPlaceholder" class="p-3 rounded-lg border border-default bg-elevated">
      <p class="text-caption">
        {{ t('sms_gateway.settings.placeholderNotice') }}
      </p>
    </div>

    <div class="space-y-4 max-w-md">
      <div>
        <label class="text-caption text-subtle">{{ t('sms_gateway.settings.provider') }}</label>
        <USelect v-model="form.provider_name" :items="providerOptions" class="w-full" />
      </div>

      <UInput
        v-model="form.api_key"
        type="password"
        :placeholder="settings?.has_api_key ? t('sms_gateway.settings.apiKeySet') : t('sms_gateway.settings.apiKey')"
      />
      <UInput v-model="form.sender_id" :placeholder="t('sms_gateway.settings.senderId')" />
      <UInput v-model="form.base_url" :placeholder="t('sms_gateway.settings.baseUrl')" />

      <div class="flex items-center gap-2">
        <USwitch v-model="form.is_active" />
        <span class="text-caption">{{ t('sms_gateway.settings.active') }}</span>
      </div>

      <UButton :loading="saving" :disabled="loading" @click="onSave">
        {{ t('actions.save') }}
      </UButton>
    </div>

    <div>
      <h3 class="text-body font-semibold text-default mb-2">
        {{ t('sms_gateway.settings.recentActivity') }}
      </h3>
      <div class="space-y-1">
        <div v-for="log in outbox" :key="log.id" class="text-caption flex gap-2 flex-wrap">
          <UBadge :color="log.status === 'sent' ? 'success' : log.status === 'skipped' ? 'warning' : 'error'" variant="soft" size="sm">
            {{ log.status }}
          </UBadge>
          <span>{{ log.to_address }}</span>
          <span class="text-subtle">{{ log.error_message || log.body }}</span>
        </div>
        <p v-if="outbox.length === 0" class="text-caption text-subtle">
          {{ t('sms_gateway.settings.noActivity') }}
        </p>
      </div>
    </div>
  </div>
</template>
