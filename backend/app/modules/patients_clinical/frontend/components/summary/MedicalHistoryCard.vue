<script setup lang="ts">
/**
 * MedicalHistoryCard — patient Resumen smart-card surfacing the
 * clinically critical findings (allergies, systemic diseases, chronic
 * medication, anticoagulant / pregnancy flags) so a clinician sees the
 * risk at a glance instead of having to dig into a sub-tab.
 *
 * Registered into ``patient.summary.cards`` by patients_clinical. Deep
 * links to the patient's Datos tab with the medical-history modal open.
 */
import type { PatientExtended } from '~~/app/types'

interface Ctx {
  patient: PatientExtended
}

const props = defineProps<{ ctx: Ctx }>()

const { t } = useI18n()

const patientId = computed(() => props.ctx.patient.id)
const { medicalHistory, isLoading } = useMedicalHistory(patientId)
const { alerts, isLoading: loadingAlerts } = usePatientAlerts(patientId)

const allergyCount = computed(() => medicalHistory.value.allergies.length)
const diseaseCount = computed(() => medicalHistory.value.systemic_diseases.length)
const medicationCount = computed(() => medicalHistory.value.medications.length)

const topAllergies = computed(() =>
  medicalHistory.value.allergies.slice(0, 2)
)
const topDiseases = computed(() =>
  medicalHistory.value.systemic_diseases.slice(0, 2)
)

const hasCriticalAlerts = computed(() =>
  alerts.value.some(a => a.severity === 'critical')
)
const hasHighAlerts = computed(() =>
  alerts.value.some(a => a.severity === 'high')
)

const severity = computed<'neutral' | 'info' | 'warning' | 'danger'>(() => {
  if (hasCriticalAlerts.value) return 'danger'
  if (hasHighAlerts.value) return 'warning'
  if (allergyCount.value + diseaseCount.value + medicationCount.value > 0) return 'info'
  return 'neutral'
})

const href = computed(
  () => `/patients/${patientId.value}?tab=info&edit=medical`
)

const isEmpty = computed(() =>
  allergyCount.value === 0
  && diseaseCount.value === 0
  && medicationCount.value === 0
  && alerts.value.length === 0
)
</script>

<template>
  <SummaryCard
    :title="t('patientDetail.medicalHistory', 'Historial médico')"
    icon="i-lucide-heart-pulse"
    :severity="severity"
    :loading="isLoading || loadingAlerts"
    :empty="isEmpty"
    :to="href"
  >
    <template #empty>
      {{ t('patientDetail.completeMedicalHistory', 'Sin historial médico. Complétalo para registrar alergias, condiciones y medicación.') }}
    </template>

    <div class="space-y-1.5 text-caption">
      <div
        v-if="allergyCount > 0"
        class="space-y-0.5"
      >
        <div class="flex items-center gap-1.5">
          <UIcon
            name="i-lucide-alert-triangle"
            class="w-3.5 h-3.5 text-[var(--color-danger-accent)]"
          />
          <span class="text-default">
            {{ t('patients.medicalHistory.allergiesCount', { n: allergyCount }, allergyCount) }}
          </span>
        </div>
        <ul class="ps-5 text-muted">
          <li
            v-for="(a, i) in topAllergies"
            :key="`allergy-${i}`"
            class="truncate"
          >
            · {{ a.name }}
            <span
              v-if="a.severity"
              class="text-subtle"
            >({{ a.severity }})</span>
          </li>
        </ul>
      </div>

      <div
        v-if="diseaseCount > 0"
        class="flex items-start gap-1.5"
      >
        <UIcon
          name="i-lucide-activity"
          class="w-3.5 h-3.5 mt-0.5 text-subtle shrink-0"
        />
        <div class="text-muted truncate">
          {{ topDiseases.map(d => d.name).join(', ') }}
          <span
            v-if="diseaseCount > topDiseases.length"
            class="text-subtle"
          >
            (+{{ diseaseCount - topDiseases.length }})
          </span>
        </div>
      </div>

      <div
        v-if="medicalHistory.is_on_anticoagulants"
        class="flex items-center gap-1.5 text-[var(--color-warning-accent)]"
      >
        <UIcon
          name="i-lucide-droplet"
          class="w-3.5 h-3.5"
        />
        {{ t('patients.medicalHistory.onAnticoagulants', 'En tratamiento anticoagulante') }}
      </div>

      <div
        v-if="medicalHistory.is_pregnant"
        class="flex items-center gap-1.5 text-[var(--color-warning-accent)]"
      >
        <UIcon
          name="i-lucide-baby"
          class="w-3.5 h-3.5"
        />
        {{ t('patients.medicalHistory.pregnant', 'Embarazada') }}
      </div>
    </div>

    <template #footer>
      <span>{{ t('patientDetail.editMedicalHistory', 'Editar historial') }}</span>
    </template>
  </SummaryCard>
</template>
