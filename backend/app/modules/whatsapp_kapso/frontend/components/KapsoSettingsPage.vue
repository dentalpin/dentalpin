<script setup lang="ts">
import { useKapso } from '../composables/useKapso'
import { errorDetail } from '~~/app/utils/error'

const { t } = useI18n()
const toast = useToast()
const {
  settings, templates, loading, saving, syncing,
  fetchSettings, saveSettings, syncTemplates, mapTemplate, testConnection
} = useKapso()

// Notification types that can be mapped to an approved WhatsApp template.
const NOTIFICATION_TYPES = [
  'appointment_confirmation',
  'appointment_reminder',
  'appointment_cancelled',
  'budget_sent',
  'budget_accepted',
  'budget_reminder',
  'invoice_sent',
  'recall_reminder',
  'welcome'
]

const notificationTypeItems = computed(() =>
  NOTIFICATION_TYPES.map(key => ({
    value: key,
    label: t(`whatsapp_kapso.types.${key}`)
  }))
)

const form = reactive({
  api_key: '',
  phone_number_id: '',
  business_account_id: '',
  webhook_secret: '',
  display_phone_number: ''
})

const test = reactive({ to_number: '', template_name: '', language: 'es' })
const mapping = reactive({ notification_type: 'appointment_reminder', template_name: '', locale: 'es' })

const webhookUrl = computed(() => `${window.location.origin}/api/v1/whatsapp_kapso/webhook`)
const approvedTemplates = computed(() => templates.value.filter(tpl => tpl.status === 'approved'))

onMounted(async () => {
  await fetchSettings()
  if (settings.value) {
    form.phone_number_id = settings.value.phone_number_id ?? ''
    form.business_account_id = settings.value.business_account_id ?? ''
    form.display_phone_number = settings.value.display_phone_number ?? ''
  }
})

async function onSave() {
  // Only send write-only secrets when the user typed them.
  const payload: Record<string, unknown> = {
    phone_number_id: form.phone_number_id,
    business_account_id: form.business_account_id || null,
    display_phone_number: form.display_phone_number || null
  }
  if (form.api_key) payload.api_key = form.api_key
  if (form.webhook_secret) payload.webhook_secret = form.webhook_secret
  try {
    await saveSettings(payload)
    form.api_key = ''
    form.webhook_secret = ''
    toast.add({ title: t('whatsapp_kapso.saved'), color: 'success' })
  } catch (e) {
    toast.add({ title: t('whatsapp_kapso.saveError'), description: errorDetail(e), color: 'error' })
  }
}

async function onSync() {
  try {
    const list = await syncTemplates()
    toast.add({ title: t('whatsapp_kapso.synced', { n: list.length }), color: 'success' })
  } catch (e) {
    toast.add({ title: t('whatsapp_kapso.syncError'), description: errorDetail(e), color: 'error' })
  }
}

async function onMap() {
  if (!mapping.template_name) return
  try {
    await mapTemplate(mapping.notification_type, mapping.locale, mapping.template_name)
    toast.add({ title: t('whatsapp_kapso.mapped'), color: 'success' })
  } catch (e) {
    toast.add({ title: t('whatsapp_kapso.mapError'), description: errorDetail(e), color: 'error' })
  }
}

async function onTest() {
  if (!test.to_number || !test.template_name) return
  try {
    const res = await testConnection(test.to_number, test.template_name, test.language)
    if (res.success) toast.add({ title: t('whatsapp_kapso.testOk'), color: 'success' })
    else toast.add({ title: t('whatsapp_kapso.testFail'), description: res.error ?? '', color: 'error' })
  } catch (e) {
    toast.add({ title: t('whatsapp_kapso.testFail'), description: errorDetail(e), color: 'error' })
  }
}

function copyWebhook() {
  navigator.clipboard?.writeText(webhookUrl.value)
  toast.add({ title: t('whatsapp_kapso.copied'), color: 'success' })
}
</script>

<template>
  <div class="space-y-6 max-w-2xl">
    <div>
      <h2 class="text-lg font-semibold">
        {{ t('whatsapp_kapso.settings.title') }}
      </h2>
      <p class="text-sm text-gray-500">
        {{ t('whatsapp_kapso.settings.description') }}
      </p>
    </div>

    <USkeleton
      v-if="loading"
      class="h-40 w-full"
    />

    <template v-else>
      <!-- Connection -->
      <UCard>
        <template #header>
          <div class="flex items-center justify-between">
            <span class="font-medium">{{ t('whatsapp_kapso.connection') }}</span>
            <UBadge
              v-if="settings?.is_verified"
              color="success"
              variant="subtle"
            >
              {{ t('whatsapp_kapso.verified') }}
            </UBadge>
            <UBadge
              v-else
              color="neutral"
              variant="subtle"
            >
              {{ t('whatsapp_kapso.notVerified') }}
            </UBadge>
          </div>
        </template>

        <div class="space-y-3">
          <UFormField
            :label="t('whatsapp_kapso.apiKey')"
            :help="settings?.has_api_key ? t('whatsapp_kapso.secretStored') : ''"
          >
            <UInput
              v-model="form.api_key"
              type="password"
              :placeholder="settings?.has_api_key ? '••••••••' : ''"
              autocomplete="off"
            />
          </UFormField>
          <UFormField :label="t('whatsapp_kapso.phoneNumberId')">
            <UInput v-model="form.phone_number_id" />
          </UFormField>
          <UFormField
            :label="t('whatsapp_kapso.businessAccountId')"
            :help="t('whatsapp_kapso.businessAccountHelp')"
          >
            <UInput v-model="form.business_account_id" />
          </UFormField>
          <UFormField :label="t('whatsapp_kapso.displayPhone')">
            <UInput
              v-model="form.display_phone_number"
              placeholder="+34 600 11 22 33"
            />
          </UFormField>
          <UFormField
            :label="t('whatsapp_kapso.webhookSecret')"
            :help="settings?.has_webhook_secret ? t('whatsapp_kapso.secretStored') : ''"
          >
            <UInput
              v-model="form.webhook_secret"
              type="password"
              :placeholder="settings?.has_webhook_secret ? '••••••••' : ''"
              autocomplete="off"
            />
          </UFormField>
          <UButton
            :loading="saving"
            icon="i-lucide-save"
            @click="onSave"
          >
            {{ t('common.save') }}
          </UButton>
        </div>
      </UCard>

      <!-- Webhook URL -->
      <UCard>
        <template #header>
          <span class="font-medium">{{ t('whatsapp_kapso.webhook') }}</span>
        </template>
        <p class="text-sm text-gray-500 mb-2">
          {{ t('whatsapp_kapso.webhookHelp') }}
        </p>
        <div class="flex gap-2 items-center">
          <UInput
            :model-value="webhookUrl"
            readonly
            class="flex-1"
          />
          <UButton
            icon="i-lucide-copy"
            variant="outline"
            @click="copyWebhook"
          >
            {{ t('whatsapp_kapso.copy') }}
          </UButton>
        </div>
      </UCard>

      <!-- Templates -->
      <UCard>
        <template #header>
          <div class="flex items-center justify-between">
            <span class="font-medium">{{ t('whatsapp_kapso.templates') }}</span>
            <UButton
              :loading="syncing"
              icon="i-lucide-refresh-cw"
              size="sm"
              variant="outline"
              @click="onSync"
            >
              {{ t('whatsapp_kapso.sync') }}
            </UButton>
          </div>
        </template>

        <p
          v-if="!approvedTemplates.length"
          class="text-sm text-gray-500"
        >
          {{ t('whatsapp_kapso.noTemplates') }}
        </p>

        <div
          v-else
          class="space-y-3"
        >
          <div class="grid grid-cols-1 sm:grid-cols-3 gap-2">
            <USelect
              v-model="mapping.notification_type"
              :items="notificationTypeItems"
              value-key="value"
              label-key="label"
              :placeholder="t('whatsapp_kapso.notificationType')"
            />
            <USelect
              v-model="mapping.template_name"
              :items="approvedTemplates.map(tpl => ({ label: `${tpl.name} (${tpl.language})`, value: tpl.name }))"
              :placeholder="t('whatsapp_kapso.template')"
            />
            <UButton
              icon="i-lucide-link"
              :disabled="!mapping.template_name"
              @click="onMap"
            >
              {{ t('whatsapp_kapso.map') }}
            </UButton>
          </div>
        </div>
      </UCard>

      <!-- Test -->
      <UCard>
        <template #header>
          <span class="font-medium">{{ t('whatsapp_kapso.test') }}</span>
        </template>
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-2">
          <UInput
            v-model="test.to_number"
            placeholder="+34600112233"
          />
          <USelect
            v-model="test.template_name"
            :items="approvedTemplates.map(tpl => ({ label: tpl.name, value: tpl.name }))"
            :placeholder="t('whatsapp_kapso.template')"
          />
          <UButton
            icon="i-lucide-send"
            :disabled="!test.to_number || !test.template_name"
            @click="onTest"
          >
            {{ t('whatsapp_kapso.sendTest') }}
          </UButton>
        </div>
      </UCard>
    </template>
  </div>
</template>
