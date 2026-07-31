<script setup lang="ts">
/**
 * ClosePlanModal — terminal closure with reason + optional note.
 */

const props = defineProps<{
  open: boolean
  loading?: boolean
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'confirm': [payload: { closure_reason: string, closure_note?: string }]
  'cancel': []
}>()

const { t } = useI18n()

const REASONS = [
  'rejected_by_patient',
  'expired',
  'cancelled_by_clinic',
  'patient_abandoned',
  'other'
] as const

const reason = ref<string>('cancelled_by_clinic')
const note = ref('')

const reasonOptions = computed(() =>
  REASONS.map(r => ({
    value: r,
    label: t(`treatmentPlans.closureReason.${r}`)
  }))
)

function submit() {
  emit('confirm', {
    closure_reason: reason.value,
    closure_note: note.value.trim() || undefined
  })
}

function reset() {
  reason.value = 'cancelled_by_clinic'
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
            {{ t('treatmentPlans.modals.close.title') }}
          </h2>
        </template>

        <div class="space-y-4 text-sm">
          <p>{{ t('treatmentPlans.modals.close.description') }}</p>
          <UFormField
            :label="t('treatmentPlans.modals.close.reasonLabel')"
            required
          >
            <USelect
              v-model="reason"
              :items="reasonOptions"
              class="w-full"
            />
          </UFormField>
          <UFormField :label="t('treatmentPlans.modals.close.noteLabel')">
            <UTextarea
              v-model="note"
              :rows="3"
              :maxlength="2000"
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
              color="error"
              :loading="loading"
              @click="submit"
            >
              {{ t('treatmentPlans.modals.close.submit') }}
            </UButton>
          </div>
        </template>
      </UCard>
    </template>
  </UModal>
</template>
