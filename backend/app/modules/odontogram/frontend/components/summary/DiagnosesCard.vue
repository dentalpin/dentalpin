<script setup lang="ts">
/**
 * DiagnosesCard — smart-card for the patient Resumen grid.
 *
 * Registered into ``patient.summary.cards`` by the odontogram module.
 * Shows the count of planned (pending) tooth treatments and a sample
 * of up to three so the clinician can spot what needs treatment at a
 * glance. Deep links into the patient detail clinical → diagnosis mode.
 */
import type { PatientExtended, PaginatedResponse, Treatment } from '~~/app/types'

// The list endpoint returns `TreatmentResponse`: tooth numbers and
// surfaces live on each `teeth[]` member, not on the treatment itself.
// Global (whole-mouth / arch) treatments have no teeth.
type TreatmentSummary = Pick<Treatment, 'id' | 'clinical_type' | 'teeth'>

interface Ctx {
  patient: PatientExtended
}

const props = defineProps<{ ctx: Ctx }>()

const { t } = useI18n()
const api = useApi()

const patientId = computed(() => props.ctx.patient.id)

const { data, status } = await useAsyncData(
  () => `odontogram:summary-card:${patientId.value}`,
  async () => {
    try {
      return await api.get<PaginatedResponse<TreatmentSummary>>(
        `/api/v1/odontogram/patients/${patientId.value}/treatments?status=planned&page_size=50`
      )
    } catch {
      return { data: [], total: 0, page: 1, page_size: 50 }
    }
  },
  { watch: [patientId], server: false }
)

const total = computed(() => data.value?.total ?? 0)
const sample = computed<TreatmentSummary[]>(() => (data.value?.data ?? []).slice(0, 3))

const severity = computed<'neutral' | 'info' | 'warning'>(() => {
  if (total.value === 0) return 'neutral'
  if (total.value >= 5) return 'warning'
  return 'info'
})

const href = computed(
  () => `/patients/${patientId.value}?tab=clinical&clinicalMode=diagnosis`
)

function formatClinicalType(key: string): string {
  // `odontogram.treatments.types` is the real namespace (`treatmentTypes` never
  // existed in the locales, so every label fell back to humanized raw keys).
  return t(`odontogram.treatments.types.${key}`, key.replace(/_/g, ' '))
}
</script>

<template>
  <SummaryCard
    :title="t('patientDetail.diagnoses', 'Diagnósticos')"
    icon="i-lucide-stethoscope"
    :severity="severity"
    :loading="status === 'pending'"
    :empty="total === 0"
    :to="href"
  >
    <template #empty>
      {{ t('patientDetail.noDiagnoses', 'Sin hallazgos pendientes') }}
    </template>

    <div class="space-y-1.5">
      <div class="flex items-baseline gap-1">
        <span class="text-h2 text-default tnum">{{ total }}</span>
        <span class="text-caption text-muted">
          {{ t('patientDetail.pending', 'sin tratar') }}
        </span>
      </div>
      <ul class="space-y-0.5 text-caption text-muted">
        <li
          v-for="item in sample"
          :key="item.id"
          class="truncate"
        >
          · {{ formatClinicalType(item.clinical_type) }}
          <span
            v-for="tooth in item.teeth ?? []"
            :key="tooth.id"
            class="tnum"
          >
            #{{ tooth.tooth_number }}
            <span
              v-if="tooth.surfaces && tooth.surfaces.length > 0"
              class="text-subtle"
            >({{ tooth.surfaces.join(',') }})</span>
          </span>
        </li>
      </ul>
    </div>

    <template #footer>
      <span>{{ t('patientDetail.openOdontogram', 'Abrir odontograma') }}</span>
    </template>
  </SummaryCard>
</template>
