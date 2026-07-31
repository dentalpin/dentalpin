<script setup lang="ts">
/**
 * ContactLogModal — record a reception touchpoint with the patient
 * without changing the plan status.
 */

const props = defineProps<{
  open: boolean
  loading?: boolean
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'confirm': [payload: { channel: string, note?: string }]
  'cancel': []
}>()

const { t } = useI18n()

const CHANNELS = ['call', 'whatsapp', 'email', 'in_person', 'other'] as const

const channel = ref<string>('call')
const note = ref('')

const channelLabels: Record<string, string> = {
  call: 'Llamada',
  whatsapp: 'WhatsApp',
  email: 'Email',
  in_person: 'En clínica',
  other: 'Otro'
}

const channelOptions = computed(() =>
  CHANNELS.map(c => ({ value: c, label: channelLabels[c] || c }))
)

function submit() {
  emit('confirm', { channel: channel.value, note: note.value.trim() || undefined })
}

function reset() {
  channel.value = 'call'
  note.value = ''
}

watch(
  () => props.open,
  (opened) => {
    if (!opened) reset()
  }
)
</script>

<template>
  <UModal
    :open="open"
    @update:open="(v) => emit('update:open', v)"
  >
    <template #content>
      <UCard>
        <template #header>
          <h2 class="text-lg font-semibold">
            {{ t('treatmentPlans.modals.contactLog.title') }}
          </h2>
        </template>

        <div class="space-y-4 text-sm">
          <p>{{ t('treatmentPlans.modals.contactLog.description') }}</p>
          <UFormField :label="t('treatmentPlans.modals.contactLog.channelLabel')">
            <USelect
              v-model="channel"
              :items="channelOptions"
              class="w-full"
            />
          </UFormField>
          <UFormField :label="t('treatmentPlans.modals.contactLog.noteLabel')">
            <UTextarea
              v-model="note"
              :rows="3"
              :maxlength="1000"
            />
          </UFormField>
        </div>

        <template #footer>
          <div class="flex justify-end gap-2">
            <UButton
              color="neutral"
              variant="ghost"
              :disabled="loading"
              @click="emit('cancel')"
            >
              {{ t('common.cancel') }}
            </UButton>
            <UButton
              color="primary"
              :loading="loading"
              @click="submit"
            >
              {{ t('treatmentPlans.modals.contactLog.submit') }}
            </UButton>
          </div>
        </template>
      </UCard>
    </template>
  </UModal>
</template>
