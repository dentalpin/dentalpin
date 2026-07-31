<script setup lang="ts">
/**
 * PlanDetailView - Expanded view of a treatment plan
 *
 * Features:
 * - Odontogram with plan treatments highlighted
 * - Treatment list with hover linking
 * - Actions: activate, generate budget, add treatments
 * - Two-column layout on larger screens
 */

import type { DropdownMenuItem } from '@nuxt/ui'
import type { TreatmentPlanDetail } from '~~/app/types'

import ConfirmPlanModal from './modals/ConfirmPlanModal.vue'
import ReopenPlanModal from './modals/ReopenPlanModal.vue'
import ClosePlanModal from './modals/ClosePlanModal.vue'
import ReactivatePlanModal from './modals/ReactivatePlanModal.vue'
import ContactLogModal from './modals/ContactLogModal.vue'

const props = withDefaults(defineProps<{
  plan: TreatmentPlanDetail
  patientId: string
  readonly?: boolean
  /** Standalone mode: show patient link */
  standalone?: boolean
}>(), {
  standalone: false
})

const emit = defineEmits<{
  'updated': []
  'generate-budget': []
  'schedule': []
  'cancelled': []
}>()

const { t } = useI18n()
const toast = useToast()

const {
  completeItem,
  completeSession,
  cancelSession,
  removeItem,
  reorderItems,
  changeItemDoctor,
  fetchPlan,
  loading,
  confirmPlan,
  reopenPlan,
  closePlan,
  reactivatePlan,
  logContact
} = useTreatmentPlans()

// ============================================================================
// Workflow modals — owned by this view so any parent (standalone page,
// patient ficha clinical tab, sidebar mini-views) gets the same flow
// without re-wiring events.
// ============================================================================

const showConfirmModal = ref(false)
const showReopenModal = ref(false)
const showCloseModal = ref(false)
const showReactivateModal = ref(false)
const showContactLogModal = ref(false)
const transitioning = ref(false)

const planSummary = computed(() => {
  const total = props.plan.items.reduce((acc, item) => {
    const price = item.treatment?.price_snapshot
    return acc + (typeof price === 'number' ? price : Number(price) || 0)
  }, 0)
  return {
    number: props.plan.plan_number,
    count: props.plan.items.length,
    total
  }
})

async function refreshPlan() {
  await fetchPlan(props.plan.id)
  emit('updated')
  await nextTick()
}

async function onConfirmPlan() {
  transitioning.value = true
  try {
    const result = await confirmPlan(props.plan.id)
    if (result) {
      showConfirmModal.value = false
      await refreshPlan()
    }
  } finally {
    transitioning.value = false
  }
}

async function onReopenPlan() {
  transitioning.value = true
  try {
    const result = await reopenPlan(props.plan.id)
    if (result) {
      showReopenModal.value = false
      await refreshPlan()
    }
  } finally {
    transitioning.value = false
  }
}

async function onClosePlanSubmit(payload: { closure_reason: string, closure_note?: string }) {
  transitioning.value = true
  try {
    const result = await closePlan(props.plan.id, payload)
    if (result) {
      showCloseModal.value = false
      await refreshPlan()
      emit('cancelled')
    }
  } finally {
    transitioning.value = false
  }
}

async function onReactivatePlan() {
  transitioning.value = true
  try {
    const result = await reactivatePlan(props.plan.id)
    if (result) {
      showReactivateModal.value = false
      await refreshPlan()
    }
  } finally {
    transitioning.value = false
  }
}

async function onLogContact(payload: { channel: string, note?: string }) {
  transitioning.value = true
  try {
    const ok = await logContact(props.plan.id, payload)
    if (ok) showContactLogModal.value = false
  } finally {
    transitioning.value = false
  }
}

// Cross-module composable provided by the clinical_notes layer. Frontend
// auto-imports resolve to that layer's implementation.
const { createNote: createTreatmentNoteRaw } = useClinicalNotes()

async function createTreatmentNote(treatmentId: string, body: string) {
  await createTreatmentNoteRaw({
    note_type: 'treatment',
    owner_type: 'treatment',
    owner_id: treatmentId,
    body
  })
}

// ============================================================================
// Lock state — a plan with a non-cancelled budget is locked for editing.
// Mutations require explicit transitions: ``Reabrir`` (pending → draft) for
// pre-acceptance edits, or ``Renegociar`` from the budget UI for an
// already-accepted budget. The ``isLocked`` flag drives the read-only banner
// and gates inline mutations.
// ============================================================================

const isLocked = computed(() => {
  if (!props.plan.budget_id) return false
  const status = props.plan.budget?.status
  return status !== 'cancelled'
})

const effectiveReadonly = computed(() => props.readonly || isLocked.value)

// ============================================================================
// Cancel plan — delegated to the parent's ClosePlanModal. The legacy in-line
// modal kept for status-only cancellation (without closure_reason); the new
// flow surfaces ``request-close`` so the page collects a reason.
// ============================================================================

const canCancelPlan = computed(() =>
  !props.readonly
  && (
    props.plan.status === 'draft'
    || props.plan.status === 'active'
    || props.plan.status === 'pending'
  )
)

function openCancelModal() {
  // Delegates to the unified ClosePlanModal owned by this view.
  showCloseModal.value = true
}

// ============================================================================
// Visual feedback: pulse right-column card when first item lands on a draft plan
// ============================================================================

const listPulse = ref(false)
watch(
  () => props.plan.items.length,
  (next, prev) => {
    // Only celebrate the first treatment on a draft plan to keep feedback focused.
    if (prev === 0 && next > 0 && props.plan.status === 'draft') {
      toast.add({
        title: t('clinical.plans.addedToPlan'),
        color: 'success',
        icon: 'i-lucide-check-circle'
      })
      listPulse.value = true
      setTimeout(() => {
        listPulse.value = false
      }, 900)
    }
  }
)

// ============================================================================
// Hover linking state
// ============================================================================

const hoveredToothNumber = ref<number | null>(null)
const hoveredItemId = ref<string | null>(null)
/** Treatment id currently under hover in the globals strip (chart → list). */
const hoveredGlobalTreatmentId = ref<string | null>(null)

function itemTeeth(item: { treatment?: { teeth?: Array<{ tooth_number: number }> } }): number[] {
  return (item.treatment?.teeth ?? []).map(t => t.tooth_number)
}

function itemGlobalTreatmentId(item: { treatment?: { id: string, scope?: string } | null }): string | null {
  const scope = item.treatment?.scope
  if (scope === 'global_mouth' || scope === 'global_arch') {
    return item.treatment?.id ?? null
  }
  return null
}

// Items of the hovered tooth (any of whose members touches that tooth).
const highlightedItems = computed(() => {
  const fromTooth = hoveredToothNumber.value
    ? props.plan.items
        .filter(item => itemTeeth(item).includes(hoveredToothNumber.value!))
        .map(item => item.id)
    : []
  const fromGlobal = hoveredGlobalTreatmentId.value
    ? props.plan.items
        .filter(item => item.treatment?.id === hoveredGlobalTreatmentId.value)
        .map(item => item.id)
    : []
  return [...fromTooth, ...fromGlobal]
})

// Teeth of the hovered item (from Treatment.teeth[]).
const highlightedTeeth = computed(() => {
  if (!hoveredItemId.value) return []
  const item = props.plan.items.find(i => i.id === hoveredItemId.value)
  return item ? itemTeeth(item) : []
})

// Global treatment ids to highlight in the strip when hovering a list item.
const highlightedGlobalIds = computed(() => {
  if (!hoveredItemId.value) return []
  const item = props.plan.items.find(i => i.id === hoveredItemId.value)
  if (!item) return []
  const globalId = itemGlobalTreatmentId(item)
  return globalId ? [globalId] : []
})

// ============================================================================
// Computed
// ============================================================================

// Pending items count
const pendingCount = computed(() =>
  props.plan.items.filter(i => i.status === 'pending').length
)

// Can create budget: active or completed plan, without active budget
const canGenerateBudget = computed(() => {
  const validStatus = ['active', 'completed'].includes(props.plan.status)
  const noActiveBudget = !props.plan.budget_id || props.plan.budget?.status === 'cancelled'
  return validStatus && noActiveBudget
})

// ============================================================================
// Progress stepper — maps plan status to a 3-step user journey.
// ============================================================================

type StepState = 'current' | 'complete' | 'upcoming'

interface Step {
  key: 'plan' | 'confirm' | 'inProgress'
  label: string
  icon: string
  state: StepState
}

const steps = computed<Step[]>(() => {
  const status = props.plan.status
  // Map the 5 backend states to the 3-step stepper:
  //   draft     → step 1 (Planificar) current
  //   pending   → step 2 (Confirmar)  current — awaiting patient acceptance
  //   active    → step 3 (En curso)   current — treatment underway
  //   completed → all complete
  //   closed    → frozen, last reached step stays current visually
  const isDraft = status === 'draft'
  const isPending = status === 'pending'
  const isActive = status === 'active'
  const isCompleted = status === 'completed'

  return [
    {
      key: 'plan',
      label: t('clinical.plans.steps.plan'),
      icon: 'i-lucide-clipboard-list',
      state: isDraft ? 'current' : 'complete'
    },
    {
      key: 'confirm',
      label: t('clinical.plans.steps.confirm'),
      icon: 'i-lucide-check-circle-2',
      state: isDraft
        ? 'upcoming'
        : (isPending ? 'current' : 'complete')
    },
    {
      key: 'inProgress',
      label: t('clinical.plans.steps.inProgress'),
      icon: 'i-lucide-stethoscope',
      state: isActive
        ? 'current'
        : (isCompleted ? 'complete' : 'upcoming')
    }
  ]
})

const isDraft = computed(() => props.plan.status === 'draft')
const canConfirm = computed(() => isDraft.value && pendingCount.value > 0)

// ============================================================================
// Actions
// ============================================================================

const odontogramRef = ref<{ refetchTreatments: () => Promise<void> } | null>(null)
const notesTimelineRef = ref<{ refresh: () => Promise<void> } | null>(null)

async function handleCompleteItem(
  itemId: string,
  payload: { noteBody: string | null }
) {
  // Clinical-note capture moved to the clinical_notes module — orchestrate
  // both calls from the client so neither module imports the other.
  const item = props.plan.items.find(i => i.id === itemId)
  await completeItem(props.plan.id, itemId, {})
  if (payload.noteBody && item?.treatment_id) {
    await createTreatmentNote(item.treatment_id, payload.noteBody)
  }
  await odontogramRef.value?.refetchTreatments()
  await notesTimelineRef.value?.refresh()
  emit('updated')
}

async function handleRemoveItem(itemId: string) {
  await removeItem(props.plan.id, itemId)
  await odontogramRef.value?.refetchTreatments()
  emit('updated')
}

async function handleReorder(itemIds: string[]) {
  await reorderItems(props.plan.id, itemIds)
  emit('updated')
}

async function handleItemDoctorChange(itemId: string, professionalId: string | null) {
  await changeItemDoctor(props.plan.id, itemId, professionalId)
  emit('updated')
}

async function handleSessionComplete(itemId: string, sessionId: string) {
  await completeSession(props.plan.id, itemId, sessionId, {})
  await odontogramRef.value?.refetchTreatments()
  emit('updated')
}

async function handleSessionCancel(itemId: string, sessionId: string) {
  await cancelSession(props.plan.id, itemId, sessionId, {})
  emit('updated')
}

// The legacy "Activate plan" CTA used to fire ``update_status`` with
// ``status='active'`` — an invalid transition under the new state
// machine (must go through ``pending``). Both the in-page CTA and
// this open handler now delegate to the page-level ConfirmPlanModal
// via the ``request-confirm`` event.
function openActivateModal() {
  // Big body CTA + any other "confirm plan" entry point.
  showConfirmModal.value = true
}

function handleGenerateBudget() {
  emit('generate-budget')
}

const moreMenuItems = computed<DropdownMenuItem[]>(() => {
  const items: DropdownMenuItem[] = []
  if (canCancelPlan.value) {
    items.push({
      label: t('clinical.plans.cancelPlan'),
      icon: 'i-lucide-ban',
      color: 'error',
      onSelect: openCancelModal
    })
  }
  return items
})
</script>

<template>
  <div class="space-y-4">
    <!-- Header: title + stepper + actions -->
    <div class="plan-header">
      <div class="plan-header-title">
        <h2 class="text-h1 text-default">
          {{ plan.title || plan.plan_number }}
        </h2>
        <NuxtLink
          v-if="standalone && plan.patient"
          :to="`/patients/${patientId}`"
          class="inline-flex items-center gap-1 text-caption text-primary-accent hover:underline mt-0.5"
        >
          <UIcon
            name="i-lucide-user"
            class="w-3.5 h-3.5"
          />
          {{ plan.patient.first_name }} {{ plan.patient.last_name }}
        </NuxtLink>
      </div>

      <!-- Progress stepper -->
      <ol class="plan-stepper">
        <li
          v-for="(step, idx) in steps"
          :key="step.key"
          class="plan-step"
          :class="`plan-step-${step.state}`"
        >
          <span class="plan-step-marker">
            <UIcon
              v-if="step.state === 'complete'"
              name="i-lucide-check"
              class="w-3.5 h-3.5"
            />
            <span v-else>{{ idx + 1 }}</span>
          </span>
          <span class="plan-step-label">{{ step.label }}</span>
          <span
            v-if="idx < steps.length - 1"
            class="plan-step-connector"
          />
        </li>
      </ol>

      <!-- Action buttons: ghost/disabled for draft, live for active/completed. -->
      <div
        v-if="!readonly"
        class="plan-header-actions"
      >
        <UButton
          v-if="canGenerateBudget"
          variant="soft"
          size="sm"
          icon="i-lucide-file-plus"
          :loading="loading"
          @click="handleGenerateBudget"
        >
          {{ t('clinical.plans.generateBudget') }}
        </UButton>
        <UButton
          v-else-if="isDraft"
          variant="soft"
          size="sm"
          icon="i-lucide-file-plus"
          color="neutral"
          disabled
          :title="t('clinical.plans.ghostHint')"
        >
          {{ t('clinical.plans.generateBudget') }}
        </UButton>

        <UButton
          v-if="plan.status === 'active'"
          variant="soft"
          size="sm"
          icon="i-lucide-calendar-plus"
          @click="emit('schedule')"
        >
          {{ t('treatmentPlans.scheduleAppointment') }}
        </UButton>
        <UButton
          v-else-if="isDraft"
          variant="soft"
          size="sm"
          icon="i-lucide-calendar-plus"
          color="neutral"
          disabled
          :title="t('clinical.plans.ghostHint')"
        >
          {{ t('treatmentPlans.scheduleAppointment') }}
        </UButton>

        <!-- Workflow transitions for plans past draft. The big CTA in
             the body owns the draft → pending action so it's not
             duplicated up here. -->
        <UButton
          v-if="plan.status === 'pending'"
          variant="soft"
          color="warning"
          size="sm"
          icon="i-lucide-undo-2"
          @click="showReopenModal = true"
        >
          {{ t('treatmentPlans.actions.reopen') }}
        </UButton>
        <UButton
          v-if="plan.status === 'closed'"
          variant="solid"
          color="primary"
          size="sm"
          icon="i-lucide-rotate-ccw"
          @click="showReactivateModal = true"
        >
          {{ t('treatmentPlans.actions.reactivate') }}
        </UButton>

        <UDropdownMenu
          v-if="moreMenuItems.length > 0"
          :items="moreMenuItems"
        >
          <UButton
            variant="ghost"
            color="neutral"
            icon="i-lucide-more-horizontal"
            size="sm"
            :aria-label="t('common.actions')"
          />
        </UDropdownMenu>
      </div>
    </div>

    <!-- Locked banner — shown whenever plan has a live budget attached. -->
    <div
      v-if="isLocked"
      class="plan-locked-banner"
    >
      <UIcon
        name="i-lucide-lock"
        class="w-4 h-4 shrink-0 mt-0.5"
      />
      <div class="plan-locked-text">
        <div class="plan-locked-title">
          {{ t('clinical.plans.locked.title') }}
        </div>
        <div class="plan-locked-subtitle">
          {{ t('clinical.plans.locked.subtitle', { number: plan.budget?.budget_number || '' }) }}
        </div>
      </div>
      <UButton
        v-if="plan.budget_id"
        :to="`/budgets/${plan.budget_id}`"
        size="xs"
        color="warning"
        variant="soft"
        icon="i-lucide-external-link"
        trailing
        class="plan-locked-action shrink-0"
      >
        {{ t('clinical.plans.locked.viewBudget') }}
      </UButton>
    </div>

    <!-- Two-column layout.
         Tailwind's ``lg:`` (1024px) used to drive this layout but
         many laptops + browsers with DevTools or side panels open
         report a viewport below 1024px, collapsing the grid to a
         single column — odontogram filled full width and the
         treatment list + clinical notes slid below it. The custom
         ``min-[960px]:`` breakpoint covers most desktops/laptops
         (13″ MacBook = 1280px, even with the dock taking 64px the
         viewport is ≥1216px; a 1280px window with a 320px DevTools
         pane still has 960px left) while keeping the stacked
         layout for genuine tablet widths. -->
    <div class="grid grid-cols-1 min-[960px]:grid-cols-5 gap-4">
      <!-- Left column: Odontogram (wider) -->
      <UCard class="min-[960px]:col-span-3 self-start">
        <template #header>
          <div class="flex items-center gap-2">
            <UIcon
              name="i-lucide-scan"
              class="w-5 h-5 text-primary-accent"
            />
            <span class="text-ui text-default">{{ t('clinical.plans.odontogram') }}</span>
          </div>
        </template>

        <OdontogramChart
          ref="odontogramRef"
          :patient-id="patientId"
          :mode="effectiveReadonly ? 'view-only' : 'planning'"
          :plan-id="plan.id"
          :plan-title="plan.title || plan.plan_number"
          :highlighted-teeth-prop="highlightedTeeth"
          :highlighted-global-ids="highlightedGlobalIds"
          @tooth-hover="hoveredToothNumber = $event"
          @global-hover="hoveredGlobalTreatmentId = $event"
          @treatments-changed="emit('updated')"
        />
      </UCard>

      <!-- Right column: Treatment list + clinical notes, stacked and auto-height. -->
      <div class="min-[960px]:col-span-2 flex flex-col gap-4 self-start">
        <UCard
          class="plan-list-card"
          :class="{ 'plan-list-pulse': listPulse }"
        >
          <template #header>
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <UIcon
                  name="i-lucide-list-checks"
                  class="w-5 h-5"
                />
                <span class="font-medium">{{ t('clinical.plans.treatments') }}</span>
              </div>
              <UBadge
                v-if="pendingCount > 0"
                color="primary"
                variant="subtle"
              >
                {{ pendingCount }} {{ t('clinical.plans.pending') }}
              </UBadge>
            </div>
          </template>

          <PlanTreatmentList
            :items="plan.items"
            :highlighted-items="highlightedItems"
            :readonly="effectiveReadonly"
            :allow-complete="isLocked && !readonly"
            :plan-status="plan.status"
            :plan-professional-id="plan.assigned_professional_id ?? null"
            @item-hover="hoveredItemId = $event"
            @item-complete="handleCompleteItem"
            @item-remove="handleRemoveItem"
            @session-complete="handleSessionComplete"
            @session-cancel="handleSessionCancel"
            @reorder="handleReorder"
            @item-doctor-change="handleItemDoctorChange"
          />

          <!-- Sticky confirm-plan CTA: only in draft, adapts to whether items exist. -->
          <template
            v-if="!readonly && isDraft"
            #footer
          >
            <div class="confirm-cta">
              <div
                v-if="!canConfirm"
                class="confirm-cta-empty"
              >
                <UIcon
                  name="i-lucide-info"
                  class="w-4 h-4"
                />
                <span>{{ t('clinical.plans.confirmCta.empty') }}</span>
              </div>
              <template v-else>
                <div class="confirm-cta-text">
                  <div class="confirm-cta-title">
                    {{ t('clinical.plans.confirmCta.titleWithItems') }}
                  </div>
                  <div class="confirm-cta-subtitle">
                    {{ t('clinical.plans.confirmCta.subtitleWithItems') }}
                  </div>
                </div>
                <UButton
                  color="primary"
                  size="lg"
                  block
                  icon="i-lucide-check-circle-2"
                  :loading="loading"
                  @click="openActivateModal"
                >
                  {{ t('treatmentPlans.actions.confirm') }}
                </UButton>
              </template>
            </div>
          </template>
        </UCard>

        <UCard>
          <template #header>
            <div class="flex items-center gap-2">
              <UIcon
                name="i-lucide-notebook-pen"
                class="w-5 h-5"
              />
              <span class="font-medium">{{ t('treatmentPlans.notes.title') }}</span>
            </div>
          </template>
          <PlanNotesTimeline
            ref="notesTimelineRef"
            :plan-id="plan.id"
            :patient-id="plan.patient_id"
            :items="plan.items"
            :readonly="readonly"
            @item-hover="hoveredItemId = $event"
          />
        </UCard>
      </div>
    </div>

    <!-- Workflow modals (PR1/PR2) — owned by this view so any parent
         (standalone page, patient ficha) gets the same flow. -->
    <ConfirmPlanModal
      :open="showConfirmModal"
      :plan-number="planSummary.number"
      :item-count="planSummary.count"
      :total-estimated="planSummary.total"
      :loading="transitioning"
      @update:open="(v) => (showConfirmModal = v)"
      @confirm="onConfirmPlan"
      @cancel="showConfirmModal = false"
    />
    <ReopenPlanModal
      :open="showReopenModal"
      :loading="transitioning"
      @update:open="(v) => (showReopenModal = v)"
      @confirm="onReopenPlan"
      @cancel="showReopenModal = false"
    />
    <ClosePlanModal
      :open="showCloseModal"
      :loading="transitioning"
      @update:open="(v) => (showCloseModal = v)"
      @confirm="onClosePlanSubmit"
      @cancel="showCloseModal = false"
    />
    <ReactivatePlanModal
      :open="showReactivateModal"
      :loading="transitioning"
      :closed-at="plan.closed_at ?? null"
      :previous-reason="plan.closure_reason ?? null"
      @update:open="(v) => (showReactivateModal = v)"
      @confirm="onReactivatePlan"
      @cancel="showReactivateModal = false"
    />
    <ContactLogModal
      :open="showContactLogModal"
      :loading="transitioning"
      @update:open="(v) => (showContactLogModal = v)"
      @confirm="onLogContact"
      @cancel="showContactLogModal = false"
    />
  </div>
</template>

<style scoped>
.plan-header {
  display: grid;
  grid-template-columns: 1fr auto auto;
  align-items: center;
  gap: 16px;
}

@media (max-width: 900px) {
  .plan-header {
    grid-template-columns: 1fr;
  }
}

.plan-header-title {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.plan-header-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

/* Stepper */
.plan-stepper {
  display: flex;
  align-items: center;
  gap: 8px;
  list-style: none;
  padding: 0;
  margin: 0;
}

.plan-step {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #9CA3AF;
  position: relative;
}

.plan-step-marker {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  border: 1.5px solid currentColor;
  background: transparent;
  flex-shrink: 0;
}

.plan-step-label {
  font-weight: 500;
  white-space: nowrap;
}

.plan-step-connector {
  width: 20px;
  height: 1.5px;
  background: currentColor;
  opacity: 0.4;
}

.plan-step-current {
  color: #2563EB;
}

.plan-step-current .plan-step-marker {
  background: #2563EB;
  color: white;
  border-color: #2563EB;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.2);
}

.plan-step-complete {
  color: #16A34A;
}

.plan-step-complete .plan-step-marker {
  background: #16A34A;
  color: white;
  border-color: #16A34A;
}

.plan-step-upcoming {
  color: #9CA3AF;
}

:root.dark .plan-step-current {
  color: #60A5FA;
}

:root.dark .plan-step-current .plan-step-marker {
  background: #2563EB;
  border-color: #3B82F6;
}

:root.dark .plan-step-complete {
  color: #4ADE80;
}

/* Confirm CTA footer */
.confirm-cta {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.confirm-cta-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.confirm-cta-title {
  font-weight: 600;
  font-size: 14px;
  color: #1E40AF;
}

:root.dark .confirm-cta-title {
  color: #BFDBFE;
}

.confirm-cta-subtitle {
  font-size: 12px;
  color: #475569;
  line-height: 1.35;
}

:root.dark .confirm-cta-subtitle {
  color: #94A3B8;
}

.confirm-cta-empty {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  font-size: 13px;
  color: #64748B;
  background: #F1F5F9;
  border-radius: 8px;
}

:root.dark .confirm-cta-empty {
  background: rgba(100, 116, 139, 0.15);
  color: #CBD5E1;
}

/* First-item pulse on list card */
.plan-list-card {
  transition: box-shadow 0.3s ease;
}

.plan-list-pulse {
  animation: plan-list-pulse 0.9s ease-out;
}

@keyframes plan-list-pulse {
  0%   { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.55); }
  50%  { box-shadow: 0 0 0 8px rgba(34, 197, 94, 0.18); }
  100% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }
}

/* Locked banner */
.plan-locked-banner {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 10px 14px;
  background: #FEF3C7;
  border: 1px solid #FCD34D;
  border-radius: 8px;
  color: #92400E;
  font-size: 13px;
  line-height: 1.4;
}

.plan-locked-text {
  flex: 1;
  min-width: 0;
}

.plan-locked-action {
  align-self: center;
}

:root.dark .plan-locked-banner {
  background: rgba(251, 191, 36, 0.12);
  border-color: rgba(251, 191, 36, 0.35);
  color: #FCD34D;
}

.plan-locked-title {
  font-weight: 600;
}

.plan-locked-subtitle {
  font-size: 12px;
  opacity: 0.85;
}
</style>
