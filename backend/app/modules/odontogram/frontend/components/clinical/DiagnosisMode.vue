<script setup lang="ts">
/**
 * DiagnosisMode - Record current patient conditions
 *
 * Features:
 * - Odontogram in diagnosis mode (only diagnostic categories)
 * - List of recorded conditions with hover linking
 * - Contextual CTA to create/continue treatment plan
 */

const props = defineProps<{
  patientId: string
  readonly?: boolean
}>()

const emit = defineEmits<{
  'create-plan': []
  'continue-plan': [planId: string]
}>()

const { t } = useI18n()

// ============================================================================
// Composables
// ============================================================================

const { treatments, fetchTreatments, loading: odontogramLoading } = useOdontogram()
const { plans, fetchPatientPlans, createPlan, addItem, loading: plansLoading } = useTreatmentPlans()

// ============================================================================
// State
// ============================================================================

// Hover linking between odontogram and conditions list
const hoveredTeeth = ref<number[]>([])
// Last clicked tooth — surfaced via slot ctx so a sidebar (issue #60) can
// pre-bind its diagnosis composer to the tooth without going through the
// odontogram itself.
const selectedTooth = ref<number | null>(null)
// Mobile sidebar slideover state.
const sidebarOpen = ref(false)

// ============================================================================
// Computed
// ============================================================================

// Filter only diagnostic conditions (status = 'existing'). Migrated
// historical treatments are hidden from this panel — bulk-importing a
// patient's entire chart history floods the diagnosis tab and makes
// the active workflow ("what am I diagnosing today?") unusable.
// The artefacts they leave (missing tooth, crown, implant…) are still
// reflected in the odontogram via ``ToothRecord.general_condition``,
// and the full historical record stays accessible from the History
// tab and the treatment plans created by the importer.
const conditions = computed(() =>
  treatments.value.filter(
    t => t.status === 'existing' && t.source_module !== 'migration_import'
  )
)

// Draft plans for contextual CTA
const draftPlans = computed(() =>
  plans.value.filter(p => p.status === 'draft')
)

// Combined loading state
const loading = computed(() => odontogramLoading.value || plansLoading.value)

// Collapsible state for conditions block
const conditionsCollapsed = ref(false)
const recommendation = ref<{ catalogItemId: string, diagnosisName: string, toothNumber: number } | null>(null)
const recommendationPlanId = ref('__new__')
const applyingRecommendation = ref(false)
const draftPlanOptions = computed(() => [
  ...draftPlans.value.map(plan => ({ value: plan.id, label: plan.title || plan.plan_number })),
  { value: '__new__', label: t('clinical.diagnosis.createNewPlanOption', 'Создать новый план') }
])

// ============================================================================
// Lifecycle
// ============================================================================

onMounted(async () => {
  await Promise.all([
    fetchTreatments(props.patientId),
    fetchPatientPlans(props.patientId)
  ])
})

// ============================================================================
// Handlers
// ============================================================================

function handleToothHover(toothNumber: number | null) {
  hoveredTeeth.value = toothNumber ? [toothNumber] : []
  if (toothNumber) selectedTooth.value = toothNumber
}

function handleConditionHover(toothNumber: number | null) {
  hoveredTeeth.value = toothNumber ? [toothNumber] : []
}

const sessionTreatmentIds = computed(() =>
  conditions.value.map(c => c.id).filter((id): id is string => Boolean(id))
)

// Map every treatment of this patient (not only diagnosis-mode conditions)
// to its teeth, so the sidebar can resolve a treatment-owned note to the
// tooth it belongs to without importing odontogram. Treatment-typed notes
// survive plan churn and may belong to any status.
const treatmentsToothById = computed<Record<string, number[]>>(() => {
  const map: Record<string, number[]> = {}
  for (const t of treatments.value) {
    if (!t.id) continue
    const teeth = (t.teeth || [])
      .map(x => x.tooth_number)
      .filter((n): n is number => typeof n === 'number')
    if (teeth.length) map[t.id] = teeth
  }
  return map
})

function handleNoteTeethHover(teeth: number[] | null) {
  hoveredTeeth.value = teeth && teeth.length ? teeth : []
}

const sidebarCtx = computed(() => ({
  patientId: props.patientId,
  selectedTooth: selectedTooth.value,
  sessionTreatmentIds: sessionTreatmentIds.value,
  treatmentsToothById: treatmentsToothById.value,
  onTeethHover: handleNoteTeethHover
}))

async function handleTreatmentsChanged() {
  await fetchTreatments(props.patientId)
}

function handleTreatmentRecommendation(value: { catalogItemId: string, diagnosisName: string, toothNumber: number }) {
  recommendation.value = value
  recommendationPlanId.value = draftPlans.value[0]?.id ?? '__new__'
}

async function confirmTreatmentRecommendation() {
  if (!recommendation.value || applyingRecommendation.value) return
  applyingRecommendation.value = true
  try {
    let planId = recommendationPlanId.value
    if (planId === '__new__') {
      const plan = await createPlan({
        patient_id: props.patientId,
        title: t('clinical.diagnosis.planFromDiagnosis', { diagnosis: recommendation.value.diagnosisName })
      })
      if (!plan) return
      planId = plan.id
    }
    const item = await addItem(planId, {
      create_treatment: {
        catalog_item_id: recommendation.value.catalogItemId,
        status: 'planned',
        scope: 'tooth',
        tooth_numbers: [recommendation.value.toothNumber]
      }
    })
    if (!item) return
    recommendation.value = null
    await fetchPatientPlans(props.patientId)
    emit('continue-plan', planId)
  } finally {
    applyingRecommendation.value = false
  }
}
</script>

<template>
  <div class="diagnosis-workspace">
    <section
      class="diagnosis-chart-column min-w-0"
      :aria-label="t('clinical.diagnosis.registerConditions')"
    >
      <div
        v-if="loading"
        class="diagnosis-loading flex min-h-64 items-center justify-center rounded-token-lg border border-default bg-surface"
      >
        <UIcon
          name="i-lucide-loader-2"
          class="size-8 animate-spin text-primary-accent"
        />
      </div>

      <UCard
        v-else
        class="diagnosis-chart-card min-w-0"
      >
        <template #header>
          <div class="flex min-w-0 items-center gap-3">
            <span class="diagnosis-section-icon flex size-10 shrink-0 items-center justify-center rounded-token-md">
              <UIcon
                name="i-lucide-stethoscope"
                class="size-5"
              />
            </span>
            <div class="min-w-0">
              <h3 class="text-ui font-semibold text-default">
                {{ t('clinical.diagnosis.registerConditions') }}
              </h3>
              <p class="mt-0.5 text-caption text-muted">
                {{ t('clinical.diagnosis.startDiagnosis') }}
              </p>
            </div>
          </div>
        </template>

        <OdontogramChart
          :patient-id="patientId"
          mode="diagnosis"
          :readonly="readonly"
          :highlighted-teeth-prop="hoveredTeeth"
          @tooth-hover="handleToothHover"
          @treatments-changed="handleTreatmentsChanged"
          @treatment-recommendation="handleTreatmentRecommendation"
        />
      </UCard>
    </section>

    <aside
      class="diagnosis-rail min-w-0"
      :aria-label="t('clinical.diagnosis.registeredConditions')"
    >
      <div
        v-if="loading"
        class="space-y-3"
        aria-hidden="true"
      >
        <USkeleton class="h-48 w-full rounded-token-lg" />
        <USkeleton class="h-36 w-full rounded-token-lg" />
      </div>

      <template v-else>
        <UCard class="diagnosis-conditions-card min-w-0">
          <template #header>
            <button
              type="button"
              class="diagnosis-conditions-trigger flex min-h-11 w-full items-center justify-between gap-3 text-start"
              :aria-expanded="!conditionsCollapsed"
              @click="conditionsCollapsed = !conditionsCollapsed"
            >
              <span class="flex min-w-0 items-center gap-2.5">
                <span class="diagnosis-section-icon flex size-9 shrink-0 items-center justify-center rounded-token-md">
                  <UIcon
                    name="i-lucide-clipboard-list"
                    class="size-4.5"
                  />
                </span>
                <span class="min-w-0">
                  <span class="block text-ui font-semibold text-default">
                    {{ t('clinical.diagnosis.registeredConditions') }}
                  </span>
                  <span class="block text-caption text-muted">
                    {{ t('clinical.diagnosis.generalConditions') }}
                  </span>
                </span>
              </span>
              <span class="flex shrink-0 items-center gap-2">
                <UBadge
                  color="neutral"
                  variant="subtle"
                  class="tnum"
                >
                  {{ conditions.length }}
                </UBadge>
                <UIcon
                  :name="conditionsCollapsed ? 'i-lucide-chevron-right' : 'i-lucide-chevron-down'"
                  class="size-4 text-subtle"
                  aria-hidden="true"
                />
              </span>
            </button>
          </template>

          <ConditionsList
            v-if="!conditionsCollapsed"
            :conditions="conditions"
            :patient-id="patientId"
            :highlighted-teeth="hoveredTeeth"
            @tooth-hover="handleConditionHover"
          />
        </UCard>

        <DiagnosisCTA
          v-if="!readonly && conditions.length > 0"
          class="diagnosis-next-step"
          :draft-plans="draftPlans"
          @create="emit('create-plan')"
          @continue="emit('continue-plan', $event)"
        />

        <div class="diagnosis-notes-slot">
          <ModuleSlot
            name="odontogram.diagnosis.sidebar"
            :ctx="sidebarCtx"
          />
        </div>
      </template>
    </aside>

    <UButton
      class="fixed end-4 bottom-[calc(5.5rem+env(safe-area-inset-bottom))] z-30 shadow-lg lg:bottom-4 xl:hidden"
      icon="i-lucide-notebook-pen"
      color="primary"
      size="lg"
      :aria-label="t('clinical.diagnosis.openNotes')"
      @click="sidebarOpen = true"
    />
    <USlideover
      v-model:open="sidebarOpen"
      side="right"
      class="xl:hidden"
    >
      <template #content>
        <div class="h-full p-2">
          <ModuleSlot
            name="odontogram.diagnosis.sidebar"
            :ctx="sidebarCtx"
          />
        </div>
      </template>
    </USlideover>

    <UModal
      :open="!!recommendation"
      @update:open="(open) => { if (!open) recommendation = null }"
    >
      <template #content>
        <div class="space-y-4 p-5">
          <h2 class="text-h3 font-semibold text-default">
            {{ t('clinical.diagnosis.recommendedTreatmentTitle', 'Добавить процедуру в план?') }}
          </h2>
          <p class="text-caption text-subtle">
            {{ t('clinical.diagnosis.recommendedTreatmentDescription', { diagnosis: recommendation?.diagnosisName, tooth: recommendation?.toothNumber }) }}
          </p>
          <UFormField :label="t('clinical.diagnosis.planForTreatment', 'План лечения')">
            <USelect
              v-model="recommendationPlanId"
              :items="draftPlanOptions"
              value-key="value"
              label-key="label"
            />
          </UFormField>
          <div class="flex justify-end gap-2">
            <UButton
              color="neutral"
              variant="ghost"
              :disabled="applyingRecommendation"
              @click="recommendation = null"
            >
              {{ t('common.cancel') }}
            </UButton>
            <UButton
              color="primary"
              :loading="applyingRecommendation"
              @click="confirmTreatmentRecommendation"
            >
              {{ t('clinical.diagnosis.addToPlan', 'Добавить в план') }}
            </UButton>
          </div>
        </div>
      </template>
    </UModal>
  </div>
</template>

<style scoped>
.diagnosis-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  align-items: start;
  width: 100%;
  min-width: 0;
  gap: 1rem;
}

.diagnosis-chart-column,
.diagnosis-chart-card,
.diagnosis-rail,
.diagnosis-conditions-card {
  min-width: 0;
}

.diagnosis-chart-card {
  overflow: hidden;
}

.diagnosis-section-icon {
  background-color: var(--color-primary-soft);
  color: var(--color-primary-soft-text);
}

.diagnosis-rail {
  display: grid;
  align-content: start;
  gap: 1rem;
}

.diagnosis-conditions-trigger {
  border-radius: var(--radius-sm);
  touch-action: manipulation;
}

.diagnosis-conditions-trigger:focus-visible {
  outline: 3px solid color-mix(in oklab, var(--color-primary-accent) 38%, transparent);
  outline-offset: 2px;
}

.diagnosis-notes-slot {
  min-width: 0;
}

@container diagnosis-mode (min-width: 1000px) {
  .diagnosis-workspace {
    grid-template-columns: minmax(0, 1fr) minmax(20rem, 23rem);
    gap: 1.25rem;
  }

  .diagnosis-rail {
    position: sticky;
    top: 6rem;
  }
}
</style>
