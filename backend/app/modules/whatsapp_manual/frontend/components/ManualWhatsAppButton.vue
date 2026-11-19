<script setup lang="ts">
import { MANUAL_WHATSAPP_PATH, useManualWhatsApp } from '../composables/useManualWhatsApp'

const props = defineProps<{
  ctx: { patient?: { id: string } }
}>()
const { t } = useI18n()
const api = useManualWhatsApp()
const toast = useToast()
const enabled = ref(false)
const open = ref(false)
const text = ref('')
const busy = ref(false)
const requestId = ref('')
const patientId = computed(() => props.ctx.patient?.id)

onMounted(async () => {
  try {
    enabled.value = (await api.settings()).data.enabled
  } catch {
    enabled.value = false
  }
})

watch(text, () => {
  requestId.value = ''
})

async function queue() {
  if (!patientId.value || !text.value.trim() || busy.value) return
  busy.value = true
  requestId.value ||= crypto.randomUUID()
  try {
    await api.queue({
      patient_id: patientId.value,
      text: text.value.trim(),
      request_id: requestId.value
    })
    open.value = false
    text.value = ''
    toast.add({ title: t('whatsapp_manual.queued'), color: 'success' })
    await navigateTo(MANUAL_WHATSAPP_PATH)
  } catch {
    toast.add({ title: t('whatsapp_manual.queueError'), color: 'error' })
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <UModal
    v-if="enabled && patientId"
    v-model:open="open"
    :title="t('whatsapp_manual.compose')"
    :description="t('whatsapp_manual.composeHelp')"
  >
    <UButton
      color="neutral"
      variant="soft"
      icon="i-lucide-message-circle"
      :label="t('whatsapp_manual.compose')"
    />

    <template #body>
      <UFormField :label="t('whatsapp_manual.message')">
        <UTextarea
          v-model="text"
          :rows="4"
          :maxlength="4096"
          :disabled="busy"
          class="w-full"
        />
      </UFormField>
    </template>
    <template #footer>
      <UButton
        color="neutral"
        variant="ghost"
        :label="t('common.cancel')"
        :disabled="busy"
        @click="open = false"
      />
      <UButton
        :label="t('whatsapp_manual.queue')"
        :disabled="!text.trim()"
        :loading="busy"
        @click="queue"
      />
    </template>
  </UModal>
</template>
