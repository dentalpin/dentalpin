<script setup lang="ts">
/**
 * Slot entry into `appointment.completed.followup` (#207): a "Cobrar"
 * shortcut that opens the shared PaymentCreateModal for the visit's
 * patient — finishing an appointment is exactly when the front desk
 * collects. It does NOT emit `done` on success: the host closes the
 * whole follow-up modal on `done`, and the other actions (recall,
 * mark-performed) should stay usable; the collected state is shown
 * inline instead.
 */
const props = defineProps<{
  appointment: {
    id: string
    patient_id?: string | null
    patient?: { id: string, first_name?: string, last_name?: string } | null
  }
}>()

defineEmits<{ done: [] }>()

const { t } = useI18n()
const showPayment = ref(false)
const collected = ref(false)

const patientId = computed(() => props.appointment.patient_id ?? props.appointment.patient?.id ?? null)
const patientName = computed(() => {
  const p = props.appointment.patient
  if (!p) return undefined
  return [p.first_name, p.last_name].filter(Boolean).join(' ') || undefined
})

function onCreated() {
  showPayment.value = false
  collected.value = true
}
</script>

<template>
  <div
    v-if="patientId"
    class="space-y-2"
  >
    <UButton
      v-if="!collected"
      color="primary"
      variant="soft"
      icon="i-lucide-hand-coins"
      @click="showPayment = true"
    >
      {{ t('payments.followup.collect') }}
    </UButton>
    <p
      v-else
      class="text-sm text-(--color-success-accent)"
    >
      {{ t('payments.followup.collected') }}
    </p>

    <PaymentCreateModal
      v-model:open="showPayment"
      :default-patient-id="patientId"
      :default-patient-name="patientName"
      @created="onCreated"
    />
  </div>
</template>
