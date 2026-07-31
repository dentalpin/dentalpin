<script setup lang="ts">
import type { TreatmentPlan, TreatmentPlanStatus } from '~~/app/types'

const props = defineProps<{
  plan: TreatmentPlan
  isActive?: boolean
}>()

const emit = defineEmits<{
  'view': [plan: TreatmentPlan]
  'activate': [plan: TreatmentPlan]
  'schedule': [plan: TreatmentPlan]
  'generate-budget': [plan: TreatmentPlan]
}>()

const { t } = useI18n()

// Progress calculations
const totalCount = computed(() => props.plan.item_count || 0)
const completedCount = computed(() => props.plan.completed_count || 0)
const progress = computed(() => {
  if (totalCount.value === 0) return 0
  return Math.round((completedCount.value / totalCount.value) * 100)
})

// Status badge color mapping
const statusColors: Record<TreatmentPlanStatus, 'success' | 'warning' | 'neutral' | 'info' | 'error'> = {
  active: 'success',
  draft: 'warning',
  completed: 'info',
  cancelled: 'error',
  archived: 'neutral'
}

function getStatusColor(status: TreatmentPlanStatus) {
  return statusColors[status] || 'neutral'
}

// Format currency — clinic-wide via useCurrency.
const { format: formatCurrency } = useCurrency()
</script>

<template>
  <div
    class="plan-mini-card"
    :class="{ 'is-active': isActive }"
  >
    <!-- Header: Title + Status -->
    <div class="flex items-start justify-between gap-2 mb-3">
      <div class="flex items-center gap-2 min-w-0">
        <UIcon
          v-if="isActive"
          name="i-lucide-star"
          class="w-4 h-4 text-warning-accent shrink-0"
        />
        <h4 class="font-semibold text-sm text-default truncate">
          {{ plan.title || plan.plan_number }}
        </h4>
      </div>
      <UBadge
        :color="getStatusColor(plan.status)"
        size="xs"
        variant="subtle"
        class="shrink-0"
      >
        {{ t(`treatmentPlans.status.${plan.status}`) }}
      </UBadge>
    </div>

    <!-- Progress bar -->
    <div class="mb-3">
      <div class="flex justify-between items-center mb-1">
        <span class="text-caption text-subtle">
          {{ completedCount }}/{{ totalCount }} {{ t('treatmentPlans.treatments') }}
        </span>
        <span class="text-xs font-medium text-muted">
          {{ progress }}%
        </span>
      </div>
      <div class="w-full bg-surface-sunken rounded-full h-1.5">
        <div
          class="h-1.5 rounded-full transition-all duration-300"
          :class="isActive ? 'bg-[var(--color-primary)]' : 'bg-[var(--color-text-subtle)]'"
          :style="{ width: `${progress}%` }"
        />
      </div>
    </div>

    <!-- Total amount (if available) -->
    <div
      v-if="plan.total !== undefined"
      class="flex items-center gap-1 text-xs text-muted mb-3"
    >
      <UIcon
        name="i-lucide-banknote"
        class="w-3.5 h-3.5"
      />
      <span class="font-medium text-muted">
        {{ formatCurrency(plan.total) }}
      </span>
    </div>

    <!-- Budget link (if exists) -->
    <div
      v-if="plan.budget"
      class="flex items-center gap-2 text-xs mb-3 p-2 bg-surface-muted rounded"
    >
      <UIcon
        name="i-lucide-file-text"
        class="w-3.5 h-3.5 text-subtle"
      />
      <span class="text-muted">
        {{ plan.budget.budget_number }}
      </span>
      <UBadge
        :color="plan.budget.status === 'accepted' ? 'success' : 'warning'"
        size="xs"
        variant="subtle"
      >
        {{ t(`budget.status.${plan.budget.status}`) }}
      </UBadge>
    </div>

    <!-- Actions -->
    <div class="flex items-center gap-2 flex-wrap">
      <UButton
        size="xs"
        variant="soft"
        color="neutral"
        @click="emit('view', plan)"
      >
        {{ t('common.viewDetails') }}
      </UButton>

      <UButton
        v-if="plan.status === 'draft' && totalCount > 0"
        size="xs"
        variant="soft"
        color="primary"
        @click="emit('activate', plan)"
      >
        {{ t('treatmentPlans.activate') }}
      </UButton>

      <UButton
        v-if="['active', 'completed'].includes(plan.status) && (!plan.budget_id || plan.budget?.status === 'cancelled') && totalCount > 0"
        size="xs"
        variant="soft"
        color="neutral"
        icon="i-lucide-file-plus"
        @click="emit('generate-budget', plan)"
      >
        {{ t('treatmentPlans.generateBudget') }}
      </UButton>

      <UButton
        v-if="plan.status === 'active'"
        size="xs"
        variant="soft"
        color="neutral"
        icon="i-lucide-calendar-plus"
        @click="emit('schedule', plan)"
      >
        {{ t('treatmentPlans.scheduleAppointment') }}
      </UButton>
    </div>
  </div>
</template>

<style scoped>
.plan-mini-card {
  padding: var(--density-card-padding-y, 16px) var(--density-card-padding-x, 20px);
  border-radius: 0.5rem;
  border: 1px solid #E5E7EB;
  background-color: white;
  transition: all 0.2s ease;
}

:root.dark .plan-mini-card {
  border-color: #374151;
  background-color: #111827;
}

.plan-mini-card:hover {
  border-color: #D1D5DB;
  box-shadow: 0 1px 2px 0 rgb(0 0 0 / 0.05);
}

:root.dark .plan-mini-card:hover {
  border-color: #4B5563;
}

.plan-mini-card.is-active {
  border-color: #93C5FD;
  background-color: rgba(239, 246, 255, 0.5);
}

:root.dark .plan-mini-card.is-active {
  border-color: #1D4ED8;
  background-color: rgba(30, 58, 138, 0.1);
}
</style>
