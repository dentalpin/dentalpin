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
const { plans, fetchPatientPlans, loading: plansLoading } = useTreatmentPlans()

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
</script>

<template>
  <!-- Side-by-side at ``min-[960px]:`` instead of the previous
       ``lg:`` (1024px) — laptops + browsers with DevTools or side
       panels open often report a viewport just below 1024px, which
       collapsed the right-rail notes sidebar below the odontogram
       and made the chart fill the full width (looking "gigante"). -->
  <div class="min-[960px]:flex min-[960px]:gap-4 min-[960px]:items-start">
    <div class="flex-1 min-w-0 space-y-4">
      <!-- Loading state -->
      <div
        v-if="loading"
        class="flex items-center justify-center py-8"
      >
        <UIcon
          name="i-lucide-loader-2"
          class="w-8 h-8 animate-spin text-primary-accent"
        />
      </div>

      <template v-else>
        <!-- Odontogram with diagnosis mode -->
        <UCard>
          <template #header>
            <div class="flex items-center gap-2">
              <UIcon
                name="i-lucide-stethoscope"
                class="w-5 h-5 text-primary-accent"
              />
              <span class="font-medium">{{ t('clinical.diagnosis.registerConditions') }}</span>
            </div>
          </template>

          <OdontogramChart
            :patient-id="patientId"
            mode="diagnosis"
            :highlighted-teeth-prop="hoveredTeeth"
            @tooth-hover="handleToothHover"
            @treatments-changed="handleTreatmentsChanged"
          />
        </UCard>

        <!-- Registered conditions list -->
        <UCard>
          <template #header>
            <button
              type="button"
              class="w-full flex items-center justify-between gap-2 text-left"
              :aria-expanded="!conditionsCollapsed"
              @click="conditionsCollapsed = !conditionsCollapsed"
            >
              <div class="flex items-center gap-2">
                <UIcon
                  :name="conditionsCollapsed ? 'i-lucide-chevron-right' : 'i-lucide-chevron-down'"
                  class="w-4 h-4 text-subtle transition-transform"
                />
                <UIcon
                  name="i-lucide-clipboard-list"
                  class="w-5 h-5"
                />
                <span class="font-medium">{{ t('clinical.diagnosis.registeredConditions') }}</span>
              </div>
              <UBadge
                v-if="conditions.length > 0"
                color="neutral"
                variant="subtle"
              >
                {{ conditions.length }}
              </UBadge>
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

        <!-- Contextual CTA -->
        <DiagnosisCTA
          v-if="!readonly && conditions.length > 0"
          :draft-plans="draftPlans"
          @create="emit('create-plan')"
          @continue="emit('continue-plan', $event)"
        />
      </template>
    </div>

    <!-- Right rail at ≥960px: clinical-notes sidebar provided by
         other modules via the ``odontogram.diagnosis.sidebar`` slot. -->
    <aside class="hidden min-[960px]:block min-[960px]:w-80 xl:w-96 min-[960px]:shrink-0">
      <ModuleSlot
        name="odontogram.diagnosis.sidebar"
        :ctx="sidebarCtx"
      />
    </aside>

    <!-- Floating action button + slideover for narrow viewports. -->
    <UButton
      class="fixed right-4 bottom-4 z-30 min-[960px]:hidden shadow-lg"
      icon="i-lucide-notebook-pen"
      color="primary"
      size="lg"
      :aria-label="t('clinical.diagnosis.openNotes', 'Notas')"
      @click="sidebarOpen = true"
    />
    <USlideover
      v-model:open="sidebarOpen"
      side="right"
      class="min-[960px]:hidden"
    >
      <template #content>
        <div class="p-2 h-full">
          <ModuleSlot
            name="odontogram.diagnosis.sidebar"
            :ctx="sidebarCtx"
          />
        </div>
      </template>
    </USlideover>
  </div>
</template>
