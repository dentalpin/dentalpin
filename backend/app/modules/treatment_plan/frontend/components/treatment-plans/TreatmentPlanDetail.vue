<script setup lang="ts">
import type { PlannedTreatmentItem, TreatmentPlanDetail } from '~~/app/types'

const props = defineProps<{
  plan: TreatmentPlanDetail
}>()

const emit = defineEmits<{
  'edit': []
  'status-change': [status: string]
  'generate-budget': []
  'item-add': []
  'item-complete': [itemId: string]
  'item-remove': [itemId: string]
}>()

const { t, d } = useI18n()
const { format: formatMoney } = useCurrency()

// Mirrors backend `_is_plan_locked` + the add_item status guard: items
// are editable in any non-terminal state unless a sent/accepted budget
// has turned the plan into a patient-facing contract. A draft budget
// doesn't lock — edits sync into it.
const canEditItems = computed(() => {
  if (!['draft', 'pending', 'active'].includes(props.plan.status)) return false
  if (!props.plan.budget_id) return true
  const budgetStatus = props.plan.budget?.status
  return budgetStatus === 'cancelled' || budgetStatus === 'draft'
})

// Collapsible state for completed items
const showCompleted = ref(false)

// Confirmation modal state
const showCompleteModal = ref(false)
const itemToComplete = ref<PlannedTreatmentItem | null>(null)

function openCompleteModal(item: PlannedTreatmentItem) {
  itemToComplete.value = item
  showCompleteModal.value = true
}

function confirmComplete() {
  if (itemToComplete.value) {
    emit('item-complete', itemToComplete.value.id)
  }
  showCompleteModal.value = false
  itemToComplete.value = null
}

const pendingItems = computed(() =>
  props.plan.items.filter(i => i.status === 'pending')
)

const completedItems = computed(() =>
  props.plan.items.filter(i => i.status === 'completed')
)

const progress = computed(() => {
  if (props.plan.items.length === 0) return 0
  return Math.round((completedItems.value.length / props.plan.items.length) * 100)
})

// Internal notes collapsible state
const showInternalNotes = ref(false)

function getItemTitle(item: PlannedTreatmentItem): string {
  if (item.catalog_item?.names?.es) {
    return item.catalog_item.names.es
  }
  const treatment = item.treatment
  if (treatment) {
    const teeth = treatment.teeth?.map(t => t.tooth_number) ?? []
    const teethLabel = teeth.length > 0 ? ` - ${t('odontogram.tooth')} ${teeth.join(', ')}` : ''
    return `${treatment.clinical_type}${teethLabel}`
  }
  return t('treatmentPlans.unknownTreatment')
}

function getItemPrice(item: PlannedTreatmentItem): number | null {
  const snap = item.treatment?.price_snapshot
  if (snap) {
    const parsed = Number(snap)
    if (Number.isFinite(parsed)) return parsed
  }
  const def = item.catalog_item?.default_price
  return typeof def === 'number' ? def : null
}

function getBudgetStatusColor(status: string): string {
  const colors: Record<string, string> = {
    accepted: 'success',
    sent: 'info',
    draft: 'neutral',
    rejected: 'error',
    cancelled: 'error'
  }
  return colors[status] || 'neutral'
}
</script>

<template>
  <div class="space-y-4">
    <!-- Header (no card) -->
    <div class="space-y-3">
      <!-- Title row -->
      <div class="flex items-start justify-between">
        <div>
          <div class="flex items-center gap-3">
            <h2 class="text-h1 text-default text-default">
              {{ plan.title || t('treatmentPlans.untitled') }}
            </h2>
            <TreatmentPlanStatusBadge
              :status="plan.status"
              size="md"
            />
          </div>
          <p class="text-sm text-muted mt-1">
            {{ plan.plan_number }} &middot; {{ d(new Date(plan.created_at), 'short') }}
          </p>
          <NuxtLink
            v-if="plan.patient"
            :to="`/patients/${plan.patient_id}`"
            class="inline-flex items-center gap-1.5 mt-1 text-sm text-primary-accent hover:text-primary-700 dark:hover:text-primary-300 hover:underline"
          >
            <UIcon
              name="i-lucide-user"
              class="w-4 h-4"
            />
            {{ plan.patient.first_name }} {{ plan.patient.last_name }}
          </NuxtLink>
        </div>

        <div class="flex gap-2">
          <UButton
            v-if="plan.status === 'draft' && plan.items.length > 0"
            color="primary"
            variant="soft"
            icon="i-lucide-play"
            @click="emit('status-change', 'active')"
          >
            {{ t('treatmentPlans.actions.activate') }}
          </UButton>

          <UButton
            v-if="(!plan.budget_id || plan.budget?.status === 'cancelled') && plan.items.length > 0"
            color="primary"
            variant="soft"
            icon="i-lucide-file-text"
            @click="emit('generate-budget')"
          >
            {{ t('treatmentPlans.actions.generateBudget') }}
          </UButton>

          <UButton
            color="neutral"
            variant="ghost"
            icon="i-lucide-pencil"
            @click="emit('edit')"
          >
            {{ t('actions.edit') }}
          </UButton>
        </div>
      </div>

      <!-- Progress bar inline (no card) -->
      <div
        v-if="plan.items.length > 0"
        class="flex items-center gap-4"
      >
        <div class="flex-1">
          <div class="h-2 bg-surface-sunken rounded-full overflow-hidden">
            <div
              class="h-full bg-[var(--color-primary)] rounded-full transition-none"
              :style="{ width: `${progress}%` }"
            />
          </div>
        </div>
        <span class="text-sm font-medium text-muted whitespace-nowrap">
          {{ completedItems.length }}/{{ plan.items.length }}
          <span class="text-muted">({{ progress }}%)</span>
        </span>
      </div>

      <!-- Budget link inline -->
      <NuxtLink
        v-if="plan.budget"
        :to="`/budgets/${plan.budget.id}`"
        class="inline-flex items-center gap-2 px-3 py-1.5 bg-surface-muted hover:bg-surface-sunken dark:hover:bg-surface-sunken rounded-lg transition-colors"
      >
        <UIcon
          name="i-lucide-file-text"
          class="w-4 h-4 text-muted"
        />
        <span class="text-sm font-medium text-muted">
          {{ plan.budget.budget_number }}
        </span>
        <UBadge
          :color="getBudgetStatusColor(plan.budget.status)"
          size="xs"
        >
          {{ t(`budget.status.${plan.budget.status}`) }}
        </UBadge>
        <span class="text-sm font-semibold text-default">
          {{ formatMoney(plan.budget.total) }}
        </span>
        <UIcon
          name="i-lucide-external-link"
          class="w-3 h-3 text-subtle"
        />
      </NuxtLink>
    </div>

    <!-- Diagnosis notes (always visible) -->
    <div
      v-if="plan.diagnosis_notes"
      class="border border-default rounded-lg"
    >
      <div class="flex items-center gap-2 px-4 py-3 bg-surface-muted rounded-t-lg border-b border-default">
        <UIcon
          name="i-lucide-stethoscope"
          class="w-4 h-4 text-muted"
        />
        <span class="font-medium text-default text-sm">
          {{ t('treatmentPlans.fields.diagnosisNotes') }}
        </span>
      </div>
      <div class="p-4">
        <p class="text-sm text-muted whitespace-pre-wrap">
          {{ plan.diagnosis_notes }}
        </p>
      </div>
    </div>

    <!-- Internal notes (collapsible) -->
    <div
      v-if="plan.internal_notes"
      class="border border-default rounded-lg"
    >
      <button
        class="w-full flex items-center justify-between gap-2 px-4 py-3 bg-surface-muted rounded-lg hover:bg-surface-muted transition-colors"
        :class="{ 'rounded-b-none border-b border-default': showInternalNotes }"
        @click="showInternalNotes = !showInternalNotes"
      >
        <div class="flex items-center gap-2">
          <UIcon
            name="i-lucide-file-text"
            class="w-4 h-4 text-muted"
          />
          <span class="font-medium text-default text-sm">
            {{ t('treatmentPlans.fields.internalNotes') }}
          </span>
        </div>
        <UIcon
          :name="showInternalNotes ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'"
          class="w-4 h-4 text-subtle"
        />
      </button>
      <div
        v-show="showInternalNotes"
        class="p-4"
      >
        <p class="text-sm text-muted whitespace-pre-wrap">
          {{ plan.internal_notes }}
        </p>
      </div>
    </div>

    <!-- Treatments card (consolidated) -->
    <UCard v-if="plan.items.length > 0">
      <!-- Pending items section -->
      <div v-if="pendingItems.length > 0">
        <div class="flex items-center justify-between mb-3">
          <h3 class="font-medium text-default">
            {{ t('treatmentPlans.pendingTreatments') }}
            <span class="text-muted font-normal">({{ pendingItems.length }})</span>
          </h3>
          <UButton
            v-if="canEditItems"
            color="primary"
            variant="soft"
            size="xs"
            icon="i-lucide-plus"
            @click="emit('item-add')"
          >
            {{ t('treatmentPlans.items.add') }}
          </UButton>
        </div>

        <div class="divide-y divide-[var(--color-border-subtle)]">
          <div
            v-for="item in pendingItems"
            :key="item.id"
            class="py-3 first:pt-0 last:pb-0 flex items-center justify-between gap-4"
          >
            <div class="flex items-center gap-3 min-w-0">
              <div class="w-7 h-7 rounded-full bg-surface-muted flex items-center justify-center flex-shrink-0">
                <span class="text-xs font-medium text-muted">
                  {{ item.sequence_order }}
                </span>
              </div>
              <div class="min-w-0">
                <p class="font-medium text-default truncate">
                  {{ getItemTitle(item) }}
                </p>
                <p
                  v-if="item.treatment?.teeth?.[0]"
                  class="text-sm text-muted"
                >
                  {{ t('odontogram.tooth') }} {{ item.treatment?.teeth?.[0].tooth_number }}
                  <span v-if="item.treatment?.teeth?.[0].surfaces?.length">
                    ({{ item.treatment?.teeth?.[0].surfaces.join(', ') }})
                  </span>
                </p>
              </div>
            </div>

            <div class="flex items-center gap-2 flex-shrink-0">
              <span
                v-if="getItemPrice(item)"
                class="text-sm font-medium text-muted"
              >
                {{ formatMoney(getItemPrice(item)) }}
              </span>
              <UButton
                color="success"
                variant="soft"
                size="xs"
                icon="i-lucide-check"
                @click="openCompleteModal(item)"
              />
              <UButton
                color="neutral"
                variant="ghost"
                size="xs"
                icon="i-lucide-trash-2"
                @click="emit('item-remove', item.id)"
              />
            </div>
          </div>
        </div>
      </div>

      <!-- Divider between sections -->
      <div
        v-if="pendingItems.length > 0 && completedItems.length > 0"
        class="border-t border-default my-4"
      />

      <!-- Completed items section (collapsible) -->
      <div v-if="completedItems.length > 0">
        <button
          class="w-full flex items-center justify-between py-2 text-left"
          @click="showCompleted = !showCompleted"
        >
          <h3 class="font-medium text-success">
            {{ t('treatmentPlans.completedTreatments') }}
            <span class="font-normal">({{ completedItems.length }})</span>
          </h3>
          <UIcon
            :name="showCompleted ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'"
            class="w-5 h-5 text-subtle"
          />
        </button>

        <div
          v-show="showCompleted"
          class="divide-y divide-[var(--color-border-subtle)]  mt-2"
        >
          <div
            v-for="item in completedItems"
            :key="item.id"
            class="py-3 first:pt-0 last:pb-0 flex items-center justify-between gap-4 opacity-70"
          >
            <div class="flex items-center gap-3 min-w-0">
              <div class="w-7 h-7 rounded-full bg-[var(--color-success-soft)] flex items-center justify-center flex-shrink-0">
                <UIcon
                  name="i-lucide-check"
                  class="w-4 h-4 text-success-accent"
                />
              </div>
              <div class="min-w-0">
                <p class="font-medium text-muted line-through truncate">
                  {{ getItemTitle(item) }}
                </p>
                <p
                  v-if="item.completed_at"
                  class="text-xs text-muted"
                >
                  {{ d(new Date(item.completed_at), 'short') }}
                </p>
              </div>
            </div>

            <span
              v-if="getItemPrice(item)"
              class="text-sm text-muted flex-shrink-0"
            >
              {{ formatMoney(getItemPrice(item)) }}
            </span>
          </div>
        </div>
      </div>
    </UCard>

    <!-- Empty state -->
    <UCard v-else>
      <div class="text-center py-8">
        <UIcon
          name="i-lucide-list"
          class="w-12 h-12 text-subtle mx-auto"
        />
        <p class="mt-2 text-muted">
          {{ t('treatmentPlans.noItems') }}
        </p>
        <UButton
          v-if="canEditItems"
          class="mt-4"
          color="primary"
          variant="soft"
          icon="i-lucide-plus"
          @click="emit('item-add')"
        >
          {{ t('treatmentPlans.items.add') }}
        </UButton>
      </div>
    </UCard>

    <!-- Complete item confirmation modal -->
    <UModal v-model:open="showCompleteModal">
      <template #content>
        <UCard>
          <template #header>
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 rounded-full bg-success-100 dark:bg-success-900/30 flex items-center justify-center">
                <UIcon
                  name="i-lucide-check"
                  class="w-5 h-5 text-success-600 dark:text-success-400"
                />
              </div>
              <div>
                <h3 class="font-semibold text-default">
                  {{ t('treatmentPlans.confirmations.completeItem') }}
                </h3>
              </div>
            </div>
          </template>

          <div
            v-if="itemToComplete"
            class="space-y-3"
          >
            <div class="p-3 bg-surface-muted rounded-lg">
              <p class="font-medium text-default">
                {{ getItemTitle(itemToComplete) }}
              </p>
              <p
                v-if="itemToComplete.treatment?.teeth?.[0]"
                class="text-sm text-muted mt-1"
              >
                {{ t('odontogram.tooth') }} {{ itemToComplete.treatment?.teeth?.[0].tooth_number }}
                <span v-if="itemToComplete.treatment?.teeth?.[0].surfaces?.length">
                  ({{ itemToComplete.treatment?.teeth?.[0].surfaces.join(', ') }})
                </span>
              </p>
            </div>
            <p class="text-sm text-muted">
              {{ t('treatmentPlans.confirmations.completeItemDescription') }}
            </p>
          </div>

          <template #footer>
            <div class="flex justify-end gap-2">
              <UButton
                color="neutral"
                variant="ghost"
                @click="showCompleteModal = false"
              >
                {{ t('actions.cancel') }}
              </UButton>
              <UButton
                color="success"
                icon="i-lucide-check"
                @click="confirmComplete"
              >
                {{ t('treatmentPlans.actions.complete') }}
              </UButton>
            </div>
          </template>
        </UCard>
      </template>
    </UModal>
  </div>
</template>
