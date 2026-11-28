<script setup lang="ts">
/**
 * ClinicalTab - Main clinical tab with four modes
 *
 * Modes (chronological order):
 * - history: View past odontogram states (read-only)
 * - diagnosis: Record current conditions
 * - plans: Create and manage treatment plans
 * - appointments: View and manage patient appointments
 */

import type { ClinicalMode, TreatmentPlan } from '~~/app/types'
import { PERMISSIONS } from '~~/app/config/permissions'

const props = defineProps<{
  patientId: string
  readonly?: boolean
}>()

const emit = defineEmits<{
  'plan-view-change': [view: 'list' | 'detail']
}>()

const { can } = usePermissions()
const router = useRouter()
const route = useRoute()

// ============================================================================
// State
// ============================================================================

// Current mode (default to diagnosis as the most common workflow)
const currentMode = ref<ClinicalMode>('diagnosis')

// Plan to open directly (when transitioning from diagnosis)
const targetPlanId = ref<string | null>(null)

// Create plan modal
const showPlanModal = ref(false)

// ============================================================================
// URL Sync
// ============================================================================

// Sync mode with URL query param
watch(currentMode, (mode) => {
  router.replace({
    query: {
      ...route.query,
      clinicalMode: mode,
      // Clear targetPlanId when switching modes
      planId: mode === 'plans' && targetPlanId.value ? targetPlanId.value : undefined
    }
  })
})

// Initialize from URL on mount
onMounted(() => {
  const modes: readonly ClinicalMode[] = ['history', 'diagnosis', 'plans', 'appointments']
  const queryMode = modes.find(m => m === route.query.clinicalMode)
  if (queryMode) currentMode.value = queryMode

  // Check for planId in URL
  const planId = route.query.planId as string
  if (planId) {
    targetPlanId.value = planId
    currentMode.value = 'plans'
  }

  // Check for action=createPlan (from sidebar widget)
  if (route.query.action === 'createPlan' && can(PERMISSIONS.treatmentPlans.write)) {
    handleCreatePlan()
    router.replace({ query: { ...route.query, action: undefined } })
  }
})

// ============================================================================
// Mode Transitions
// ============================================================================

function handleCreatePlan() {
  showPlanModal.value = true
}

function handleContinuePlan(planId: string) {
  targetPlanId.value = planId
  currentMode.value = 'plans'
}

function handlePlanCreated(plan: TreatmentPlan) {
  showPlanModal.value = false
  targetPlanId.value = plan.id
  currentMode.value = 'plans'
}

function handlePlanActivated(_plan: TreatmentPlan) {
  // Could show a toast or notification
}

function handleBudgetGenerated(planId: string) {
  router.push(`/budgets/${planId}?from=patient&patientId=${props.patientId}`)
}

// Clear target plan and reset view when leaving plans mode
watch(currentMode, (newMode) => {
  if (newMode !== 'plans') {
    targetPlanId.value = null
    emit('plan-view-change', 'list') // Reset sidebar visibility
  }
})
</script>

<template>
  <div class="clinical-tab space-y-4">
    <!-- Mode Toggle -->
    <ClinicalModeToggle v-model="currentMode" />

    <!-- Mode Content -->
    <HistoryMode
      v-if="currentMode === 'history'"
      :patient-id="patientId"
    />

    <DiagnosisModeContainer
      v-else-if="currentMode === 'diagnosis'"
      :patient-id="patientId"
      :readonly="readonly"
      @create-plan="handleCreatePlan"
      @continue-plan="handleContinuePlan"
    />

    <!-- No readonly here: `readonly` is the odontogram gate. The plan
         view gates each action on its own treatment_plan permission (#1270). -->
    <PlansMode
      v-else-if="currentMode === 'plans'"
      :patient-id="patientId"
      :initial-plan-id="targetPlanId"
      @plan-activated="handlePlanActivated"
      @budget-generated="handleBudgetGenerated"
      @view-change="emit('plan-view-change', $event)"
    />

    <AppointmentsMode
      v-else-if="currentMode === 'appointments'"
      :patient-id="patientId"
    />

    <!-- Create Plan Modal (shared across modes) -->
    <TreatmentPlanModal
      v-model="showPlanModal"
      :patient-id="patientId"
      @saved="handlePlanCreated"
    />
  </div>
</template>
