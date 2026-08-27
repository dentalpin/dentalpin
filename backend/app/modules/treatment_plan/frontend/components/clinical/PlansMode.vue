<script setup lang="ts">
/**
 * PlansMode - Manage treatment plans for a patient
 *
 * Features:
 * - List view of all plans (grouped by status)
 * - Detail view of single plan with odontogram
 * - Create new plan modal
 * - Transitions from diagnosis mode (initialPlanId)
 */

import type { TreatmentPlan, TreatmentPlanDetail } from '~~/app/types'

const props = defineProps<{
  patientId: string
  initialPlanId?: string | null
  readonly?: boolean
}>()

const emit = defineEmits<{
  'plan-activated': [plan: TreatmentPlan]
  'budget-generated': [planId: string]
  'view-change': [view: 'list' | 'detail']
}>()

const router = useRouter()

// ============================================================================
// Composables
// ============================================================================

const {
  plans,
  total,
  loading,
  fetchPlans,
  fetchPlan,
  updatePlanStatus,
  generateBudget
} = useTreatmentPlans()

// ============================================================================
// State
// ============================================================================

// Current view: 'list' or 'detail'
const view = ref<'list' | 'detail'>('list')
const selectedPlan = ref<TreatmentPlanDetail | null>(null)
const showCreateModal = ref(false)

// Pagination
const currentPage = ref(1)
const pageSize = 20
const totalPages = computed(() => Math.ceil(total.value / pageSize))

async function loadPatientPlans() {
  await fetchPlans({
    patient_id: props.patientId,
    page: currentPage.value,
    page_size: pageSize
  })
}

watch(currentPage, loadPatientPlans)

// Emit view changes to parent
watch(view, (newView) => {
  emit('view-change', newView)
}, { immediate: true })

// ============================================================================
// Methods
// ============================================================================

async function openPlanDetail(planId: string) {
  const plan = await fetchPlan(planId)
  if (plan) {
    selectedPlan.value = plan
    view.value = 'detail'
  }
}

async function handleActivatePlan(plan: TreatmentPlan) {
  const updated = await updatePlanStatus(plan.id, { status: 'active' })
  if (updated) {
    emit('plan-activated', updated)
    loadPatientPlans()
  }
}

async function handleGenerateBudget(plan: TreatmentPlan) {
  const result = await generateBudget(plan.id)
  if (result) {
    emit('budget-generated', plan.id)
    // Navigate to budget
    router.push(`/budgets/${result.budget_id}`)
  }
}

async function handleDetailGenerateBudget() {
  if (!selectedPlan.value) return
  const result = await generateBudget(selectedPlan.value.id)
  if (result) {
    emit('budget-generated', selectedPlan.value.id)
    router.push(`/budgets/${result.budget_id}`)
  }
}

function handleSchedule(plan: TreatmentPlan) {
  router.push(`/appointments?patient_id=${plan.patient_id}&new=1&plan_id=${plan.id}`)
}

function handlePlanCreated(plan: TreatmentPlan) {
  showCreateModal.value = false
  // Open the newly created plan
  openPlanDetail(plan.id)
}

async function handlePlanUpdated() {
  // Refresh the detail view with updated data
  if (selectedPlan.value) {
    const updated = await fetchPlan(selectedPlan.value.id)
    if (updated) {
      selectedPlan.value = updated
    }
  }
}

async function handlePlanCancelled() {
  // Cancelling a plan ends its lifecycle — back to the list so the user sees
  // the updated status and can pick another plan.
  selectedPlan.value = null
  view.value = 'list'
  await loadPatientPlans()
}

watch(() => props.patientId, () => {
  currentPage.value = 1
  loadPatientPlans()
})

// ============================================================================
// Lifecycle
// ============================================================================

onMounted(async () => {
  await loadPatientPlans()

  // If initialPlanId provided, open that plan directly
  if (props.initialPlanId) {
    openPlanDetail(props.initialPlanId)
  }
})

// Watch for initialPlanId changes (e.g., from diagnosis mode)
watch(() => props.initialPlanId, (newId) => {
  if (newId) {
    openPlanDetail(newId)
  }
})
</script>

<template>
  <div>
    <!-- List View -->
    <PlansListView
      v-if="view === 'list'"
      v-model:page="currentPage"
      :plans="plans"
      :patient-id="patientId"
      :loading="loading"
      :total="total"
      :total-pages="totalPages"
      :page-size="pageSize"
      @view-plan="openPlanDetail"
      @create-plan="showCreateModal = true"
      @activate-plan="handleActivatePlan"
      @generate-budget="handleGenerateBudget"
      @schedule="handleSchedule"
    />

    <!-- Detail View -->
    <PlanDetailView
      v-else-if="selectedPlan"
      :plan="selectedPlan"
      :patient-id="patientId"
      :readonly="readonly"
      @updated="handlePlanUpdated"
      @activate="loadPatientPlans()"
      @generate-budget="handleDetailGenerateBudget"
      @schedule="router.push(`/appointments?patient_id=${patientId}&new=1&plan_id=${selectedPlan?.id ?? ''}`)"
      @cancelled="handlePlanCancelled"
    />

    <!-- Create Plan Modal -->
    <TreatmentPlanModal
      v-model="showCreateModal"
      :patient-id="patientId"
      @saved="handlePlanCreated"
    />
  </div>
</template>
