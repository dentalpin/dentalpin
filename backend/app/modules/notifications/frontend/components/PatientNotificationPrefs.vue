<script setup lang="ts">
import { errorDetail } from '~~/app/utils/error'

type Channel = 'email_enabled' | 'whatsapp_enabled' | 'sms_enabled'

interface PatientPrefs {
  email_enabled: boolean
  whatsapp_enabled: boolean
  sms_enabled: boolean
  // Per-type opt-outs, keyed by the backend's NotificationType vocabulary.
  // An absent key is consent, so only an explicit false is an opt-out.
  preferences: Record<string, boolean>
}

const props = defineProps<{ ctx: { patient: { id: string } } }>()
const { t } = useI18n()
const toast = useToast()
const api = useApi()
// Same nine-type list the clinic settings page renders; the backend test
// `test_every_enqueued_type_is_in_the_vocabulary` keeps it in step.
const { notificationTypes } = useNotificationSettings()

const patientId = props.ctx?.patient?.id ?? null
const prefs = ref<PatientPrefs | null>(null)
const loading = ref(true)
const saving = ref(false)

onMounted(async () => {
  if (!patientId) {
    loading.value = false
    return
  }
  try {
    const res = await api.get<{ data: PatientPrefs }>(
      `/api/v1/notifications/preferences/patient/${patientId}`
    )
    prefs.value = {
      email_enabled: res.data.email_enabled,
      whatsapp_enabled: res.data.whatsapp_enabled,
      sms_enabled: res.data.sms_enabled,
      preferences: { ...(res.data.preferences ?? {}) }
    }
  } catch {
    prefs.value = null
  } finally {
    loading.value = false
  }
})

function typeEnabled(key: string): boolean {
  return prefs.value?.preferences[key] !== false
}

async function onTypeToggle(key: string, value: boolean | 'indeterminate') {
  if (!patientId || !prefs.value || saving.value) return
  const next = value === true
  const previous = { ...prefs.value.preferences }
  prefs.value.preferences = { ...previous, [key]: next }
  saving.value = true
  try {
    // The PUT merges `preferences`, so sending one key keeps the others.
    await api.put(`/api/v1/notifications/preferences/patient/${patientId}`, {
      preferences: { [key]: next }
    })
    toast.add({ title: t('notifications.prefs.saved'), color: 'success' })
  } catch (e: unknown) {
    if (prefs.value) prefs.value.preferences = previous
    toast.add({
      title: t('errors.updateFailed'),
      description: errorDetail(e),
      color: 'error'
    })
  } finally {
    saving.value = false
  }
}

async function onToggle(channel: Channel, value: boolean | 'indeterminate') {
  if (!patientId || !prefs.value || saving.value) return
  const next = value === true
  const previous = prefs.value[channel]
  prefs.value[channel] = next
  saving.value = true
  try {
    await api.put(`/api/v1/notifications/preferences/patient/${patientId}`, {
      [channel]: next
    })
    toast.add({ title: t('notifications.prefs.saved'), color: 'success' })
  } catch (e: unknown) {
    if (prefs.value) prefs.value[channel] = previous
    toast.add({
      title: t('errors.updateFailed'),
      description: errorDetail(e),
      color: 'error'
    })
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <UCard v-if="patientId">
    <template #header>
      <span class="font-medium">{{ t('notifications.prefs.title') }}</span>
    </template>

    <USkeleton
      v-if="loading"
      class="h-24 w-full"
    />
    <div v-else-if="prefs">
      <p class="text-caption text-subtle mb-3">
        {{ t('notifications.prefs.description') }}
      </p>
      <div class="flex flex-col gap-2">
        <USwitch
          :model-value="prefs.email_enabled"
          :label="t('notifications.channels.email')"
          :disabled="saving"
          @update:model-value="(v) => onToggle('email_enabled', v)"
        />
        <USwitch
          :model-value="prefs.whatsapp_enabled"
          :label="t('notifications.channels.whatsapp')"
          :disabled="saving"
          @update:model-value="(v) => onToggle('whatsapp_enabled', v)"
        />
        <USwitch
          :model-value="prefs.sms_enabled"
          :label="t('notifications.channels.sms')"
          :disabled="saving"
          @update:model-value="(v) => onToggle('sms_enabled', v)"
        />
      </div>

      <p class="text-caption text-subtle mt-4 mb-3">
        {{ t('notifications.prefs.typesDescription') }}
      </p>
      <div class="flex flex-col gap-2">
        <USwitch
          v-for="type in notificationTypes"
          :key="type.key"
          :model-value="typeEnabled(type.key)"
          :label="type.label"
          :disabled="saving"
          @update:model-value="(v) => onTypeToggle(type.key, v)"
        />
      </div>
    </div>
  </UCard>
</template>
