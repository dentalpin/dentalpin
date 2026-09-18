<script setup lang="ts">
// Slot entry into `patient.summary.actions`: deep-link to the
// prescriptions page with this patient preselected.
const props = defineProps<{
  ctx: {
    patient: {
      id: string
      status?: string
    }
  }
}>()

const { t } = useI18n()

const patientId = computed(() => props.ctx?.patient?.id)
const isArchived = computed(() => props.ctx?.patient?.status === 'archived')
</script>

<template>
  <NuxtLink
    v-if="patientId && !isArchived"
    :to="`/prescriptions?patient_id=${patientId}&new=1`"
  >
    <UButton
      icon="i-lucide-pill"
      color="neutral"
      variant="ghost"
    >
      {{ t('prescriptions.newPrescription') }}
    </UButton>
  </NuxtLink>
</template>
