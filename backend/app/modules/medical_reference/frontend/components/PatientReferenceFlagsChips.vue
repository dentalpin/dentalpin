<script setup lang="ts">
/**
 * PatientReferenceFlagsChips — per-patient interaction/contraindication
 * warning chips, registered by medical_reference into the existing
 * ``patient.header.alerts`` slot (the same slot patients_clinical itself
 * registers its alert chips into). The host header never imports this
 * component — the slot name is the only contract, so when this module
 * isn't installed the header simply renders one chip fewer.
 */
import type { PatientFlag } from '../composables/useMedicalReference'

interface Ctx {
  patient: { id: string }
}

const props = defineProps<{ ctx: Ctx }>()

const { t } = useI18n()
const { fetchPatientFlags } = useMedicalReference()

const flags = ref<PatientFlag[]>([])

// Re-fetch whenever the patient changes (the sticky header is reused
// across patient routes) or whenever the patients_clinical data bus
// ticks — i.e. right after a medical-history save (#274). Warning flags
// are clinical safety information: they must reflect the just-saved
// state without a page reload. Failures are swallowed inside the
// composable — flags are additive warnings, never a blocker.
const dataBus = useDataBus()

async function refetchFlags() {
  const patientId = props.ctx.patient.id
  if (!patientId) {
    flags.value = []
    return
  }
  flags.value = await fetchPatientFlags(patientId)
}

watch(
  () => props.ctx.patient.id,
  (patientId) => {
    // Clear only when the header switches patient — never on a bus tick,
    // or the warning would blink out and back in on a slow connection.
    flags.value = []
    if (patientId) refetchFlags()
  },
  { immediate: true }
)
dataBus.on('patients_clinical', refetchFlags)

function flagTitle(flag: PatientFlag): string {
  return t(`medicalReference.flags.${flag.type}`, {
    a: flag.involved[0] ?? '',
    b: flag.involved[1] ?? ''
  })
}
</script>

<template>
  <UTooltip
    v-for="flag in flags"
    :key="`${flag.type}-${flag.involved.join('-')}`"
    :text="flag.risk_note"
  >
    <UBadge
      color="error"
      size="xs"
      variant="subtle"
      class="shrink-0"
    >
      <UIcon
        name="i-lucide-alert-triangle"
        class="w-3 h-3 mr-1 shrink-0"
      />
      {{ flagTitle(flag) }}
    </UBadge>
  </UTooltip>
</template>
