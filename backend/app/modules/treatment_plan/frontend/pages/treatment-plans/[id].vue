<script setup lang="ts">
const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const toast = useToast()

const {
  currentPlan,
  loading,
  fetchPlan,
  generateBudget
} = useTreatmentPlans()

const planId = computed(() => route.params.id as string)

onMounted(async () => {
  await fetchPlan(planId.value)
})

watch(planId, async (newId) => {
  if (newId) await fetchPlan(newId)
})

const patientId = computed(() => currentPlan.value?.patient_id || '')

async function handleUpdated() {
  await fetchPlan(planId.value)
  await nextTick()
}

async function handleGenerateBudget() {
  const result = await generateBudget(planId.value)
  if (result?.budget_id) {
    toast.add({
      title: t('common.success'),
      description: t('treatmentPlans.actions.generateBudget'),
      color: 'success'
    })
    router.push(`/budgets/${result.budget_id}`)
  }
}

function handleSchedule() {
  if (patientId.value) {
    router.push(`/appointments?patient_id=${patientId.value}`)
  }
}

function handleCancelled() {
  if (patientId.value) {
    router.push(`/patients/${patientId.value}?tab=clinical&clinicalMode=plans`)
  } else {
    router.push('/treatment-plans')
  }
}
</script>

<template>
  <div class="space-y-6">
    <!-- Loading state -->
    <div
      v-if="loading && !currentPlan"
      class="space-y-4"
    >
      <USkeleton class="h-12 w-1/3" />
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <USkeleton class="h-96" />
        <USkeleton class="h-96" />
      </div>
    </div>

    <!-- Not found -->
    <UCard
      v-else-if="!currentPlan"
      class="text-center py-12"
    >
      <UIcon
        name="i-lucide-file-x"
        class="w-12 h-12 text-subtle mx-auto mb-4"
      />
      <p class="text-subtle">
        {{ t('common.notFound') }}
      </p>
      <UButton
        class="mt-4"
        to="/treatment-plans"
      >
        {{ t('treatmentPlans.title') }}
      </UButton>
    </UCard>

    <!-- Plan detail. PlanDetailView owns the workflow modals (confirm,
         reopen, close, reactivate, contact-log) so the same flow runs
         in the patient ficha (PlansMode) without re-wiring. -->
    <PlanDetailView
      v-else
      :plan="currentPlan"
      :patient-id="patientId"
      standalone
      @updated="handleUpdated"
      @generate-budget="handleGenerateBudget"
      @schedule="handleSchedule"
      @cancelled="handleCancelled"
    />
  </div>
</template>
