<script setup lang="ts">
/**
 * PlansListView - Display list of treatment plans for a patient
 *
 * Uses TreatmentPlanMiniCard for each plan.
 * Provides actions: view, activate, generate budget.
 */

import type { TreatmentPlan } from '~~/app/types'

const props = defineProps<{
  plans: TreatmentPlan[]
  patientId: string
  loading?: boolean
  page?: number
  totalPages?: number
  total?: number
  pageSize?: number
}>()

const emit = defineEmits<{
  'view-plan': [planId: string]
  'create-plan': []
  'activate-plan': [plan: TreatmentPlan]
  'generate-budget': [plan: TreatmentPlan]
  'schedule': [plan: TreatmentPlan]
  'update:page': [value: number]
}>()

const { t } = useI18n()

// Group plans by status for display order. Covers every status the
// state machine emits (draft → pending → active → completed, plus
// closed); anything else falls into ``otherPlans`` so a future status
// is never silently dropped from the list.
const draftPlans = computed(() => props.plans.filter(p => p.status === 'draft'))
const pendingPlans = computed(() => props.plans.filter(p => p.status === 'pending'))
const activePlans = computed(() => props.plans.filter(p => p.status === 'active'))
const completedPlans = computed(() => props.plans.filter(p => p.status === 'completed'))
const closedPlans = computed(() => props.plans.filter(p => p.status === 'closed'))

const KNOWN_STATUSES = new Set(['draft', 'pending', 'active', 'completed', 'closed'])
const otherPlans = computed(() => props.plans.filter(p => !KNOWN_STATUSES.has(p.status)))

const hasPlans = computed(() => props.plans.length > 0)
</script>

<template>
  <div class="space-y-[var(--density-gap,1rem)]">
    <SectionHeader
      v-if="loading || hasPlans"
      icon="i-lucide-clipboard-list"
      :title="t('clinical.plans.title')"
    >
      <template #action>
        <UButton
          color="primary"
          size="sm"
          icon="i-lucide-plus"
          @click="emit('create-plan')"
        >
          {{ t('clinical.plans.create') }}
        </UButton>
      </template>
    </SectionHeader>

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

    <!-- Empty state -->
    <UCard
      v-else-if="!hasPlans"
      class="mx-auto w-full max-w-xl text-center"
    >
      <div class="space-y-4 py-2">
        <p class="text-h3 text-default">
          {{ t('treatmentPlans.empty') }}
        </p>
        <UButton
          color="primary"
          icon="i-lucide-plus"
          @click="emit('create-plan')"
        >
          {{ t('treatmentPlans.create') }}
        </UButton>
      </div>
    </UCard>

    <!-- Plans list -->
    <template v-else>
      <!-- Active plans -->
      <div
        v-if="activePlans.length > 0"
        class="space-y-[var(--density-gap,0.75rem)]"
      >
        <h4 class="text-caption text-muted uppercase tracking-wide flex items-center gap-2">
          <UIcon
            name="i-lucide-play-circle"
            class="w-4 h-4 text-success-accent"
          />
          {{ t('clinical.plans.active') }}
        </h4>
        <div class="grid gap-[var(--density-gap,0.75rem)]">
          <TreatmentPlanMiniCard
            v-for="plan in activePlans"
            :key="plan.id"
            :plan="plan"
            is-active
            @view="emit('view-plan', plan.id)"
            @activate="emit('activate-plan', plan)"
            @generate-budget="emit('generate-budget', plan)"
            @schedule="emit('schedule', plan)"
          />
        </div>
      </div>

      <!-- Pending plans (confirmed, waiting for budget acceptance) -->
      <div
        v-if="pendingPlans.length > 0"
        class="space-y-[var(--density-gap,0.75rem)]"
      >
        <h4 class="text-caption text-muted uppercase tracking-wide flex items-center gap-2">
          <UIcon
            name="i-lucide-clock"
            class="w-4 h-4 text-info-accent"
          />
          {{ t('clinical.plans.pending') }}
        </h4>
        <div class="grid gap-[var(--density-gap,0.75rem)]">
          <TreatmentPlanMiniCard
            v-for="plan in pendingPlans"
            :key="plan.id"
            :plan="plan"
            @view="emit('view-plan', plan.id)"
            @activate="emit('activate-plan', plan)"
            @generate-budget="emit('generate-budget', plan)"
            @schedule="emit('schedule', plan)"
          />
        </div>
      </div>

      <!-- Draft plans -->
      <div
        v-if="draftPlans.length > 0"
        class="space-y-[var(--density-gap,0.75rem)]"
      >
        <h4 class="text-caption text-muted uppercase tracking-wide flex items-center gap-2">
          <UIcon
            name="i-lucide-pencil"
            class="w-4 h-4 text-warning-accent"
          />
          {{ t('clinical.plans.drafts') }}
        </h4>
        <div class="grid gap-[var(--density-gap,0.75rem)]">
          <TreatmentPlanMiniCard
            v-for="plan in draftPlans"
            :key="plan.id"
            :plan="plan"
            @view="emit('view-plan', plan.id)"
            @activate="emit('activate-plan', plan)"
            @schedule="emit('schedule', plan)"
          />
        </div>
      </div>

      <!-- Other (unknown / future) statuses — never silently drop a plan -->
      <div
        v-if="otherPlans.length > 0"
        class="space-y-[var(--density-gap,0.75rem)]"
      >
        <h4 class="text-caption text-muted uppercase tracking-wide flex items-center gap-2">
          <UIcon
            name="i-lucide-circle-help"
            class="w-4 h-4 text-muted"
          />
          {{ t('clinical.plans.other') }}
        </h4>
        <div class="grid gap-[var(--density-gap,0.75rem)]">
          <TreatmentPlanMiniCard
            v-for="plan in otherPlans"
            :key="plan.id"
            :plan="plan"
            @view="emit('view-plan', plan.id)"
            @schedule="emit('schedule', plan)"
          />
        </div>
      </div>

      <!-- Completed plans (collapsible) -->
      <UAccordion
        v-if="completedPlans.length > 0"
        :items="[{
          label: `${t('clinical.plans.completed')} (${completedPlans.length})`,
          slot: 'completed'
        }]"
        class="mt-4"
      >
        <template #completed>
          <div class="grid gap-[var(--density-gap,0.75rem)] pt-2">
            <TreatmentPlanMiniCard
              v-for="plan in completedPlans"
              :key="plan.id"
              :plan="plan"
              @view="emit('view-plan', plan.id)"
              @generate-budget="emit('generate-budget', plan)"
              @schedule="emit('schedule', plan)"
            />
          </div>
        </template>
      </UAccordion>

      <!-- Closed plans (collapsible) -->
      <UAccordion
        v-if="closedPlans.length > 0"
        :items="[{
          label: `${t('clinical.plans.closed')} (${closedPlans.length})`,
          slot: 'closed'
        }]"
        class="mt-4"
      >
        <template #closed>
          <div class="grid gap-[var(--density-gap,0.75rem)] pt-2">
            <TreatmentPlanMiniCard
              v-for="plan in closedPlans"
              :key="plan.id"
              :plan="plan"
              @view="emit('view-plan', plan.id)"
              @schedule="emit('schedule', plan)"
            />
          </div>
        </template>
      </UAccordion>

      <PaginationBar
        v-if="totalPages && totalPages > 1 && page"
        :page="page"
        :total-pages="totalPages"
        :total="total"
        :page-size="pageSize"
        @update:page="(v) => emit('update:page', v)"
      />
    </template>
  </div>
</template>
