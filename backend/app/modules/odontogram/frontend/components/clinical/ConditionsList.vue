<script setup lang="ts">
/**
 * ConditionsList - Display diagnosed conditions (status='existing')
 *
 * Shows treatments with existing status grouped by tooth.
 * Supports hover linking with odontogram.
 */

import type { ToothTreatmentView, Treatment } from '~~/app/types'
import { getTreatmentDisplayName, viewForTooth } from '~~/app/utils/treatmentView'

const props = defineProps<{
  conditions: Treatment[]
  highlightedTeeth?: number[]
  /** Forwarded into the per-treatment action slot ctx for downstream
   *  attachments / clinical-notes composer. */
  patientId?: string | null
}>()

const emit = defineEmits<{
  'tooth-hover': [toothNumber: number | null]
}>()

const { t, locale } = useI18n()

// Flatten Treatment[] into per-tooth views and group by tooth number.
const groupedByTooth = computed(() => {
  const groups = new Map<number, ToothTreatmentView[]>()
  for (const treatment of props.conditions) {
    for (const tooth of treatment.teeth) {
      const v = viewForTooth(treatment, tooth.tooth_number)
      if (!v) continue
      const existing = groups.get(v.tooth_number) || []
      existing.push(v)
      groups.set(v.tooth_number, existing)
    }
  }
  return Array.from(groups.entries())
    .sort(([a], [b]) => a - b)
    .map(([toothNumber, treatments]) => ({ toothNumber, treatments }))
})

const generalConditions = computed<ToothTreatmentView[]>(() => [])

function getTreatmentLabel(treatment: ToothTreatmentView): string {
  return getTreatmentDisplayName(treatment, locale.value, t)
}

function formatSurfaces(surfaces: string[] | undefined): string {
  if (!surfaces || surfaces.length === 0) return ''
  return `(${surfaces.join(', ')})`
}

function isHighlighted(toothNumber: number): boolean {
  return props.highlightedTeeth?.includes(toothNumber) ?? false
}
</script>

<template>
  <div>
    <!-- No conditions -->
    <div
      v-if="conditions.length === 0"
      class="text-center py-6 text-muted"
    >
      <UIcon
        name="i-lucide-clipboard-check"
        class="w-10 h-10 mx-auto mb-2 opacity-50"
      />
      <p class="font-medium">
        {{ t('clinical.diagnosis.noConditions') }}
      </p>
      <p class="text-sm">
        {{ t('clinical.diagnosis.startDiagnosis') }}
      </p>
    </div>

    <!-- Conditions by tooth: one compact row per tooth -->
    <ul
      v-else
      class="divide-y divide-[var(--color-border-subtle)]"
    >
      <li
        v-for="group in groupedByTooth"
        :key="group.toothNumber"
        class="flex items-center gap-[var(--density-gap,0.75rem)] px-2 rounded-token-md transition-colors cursor-default min-h-[var(--density-row-height,44px)]"
        :class="{
          'alert-surface-warning': isHighlighted(group.toothNumber),
          'hover:bg-surface-muted/60': !isHighlighted(group.toothNumber)
        }"
        @mouseenter="emit('tooth-hover', group.toothNumber)"
        @mouseleave="emit('tooth-hover', null)"
      >
        <span
          class="inline-flex items-center justify-center min-w-[2.25rem] h-7 px-2 rounded-token-sm text-caption font-semibold tnum bg-surface-muted text-default"
        >
          {{ group.toothNumber }}
        </span>
        <div class="flex flex-wrap items-center gap-x-2 gap-y-1 text-body flex-1 min-w-0">
          <template
            v-for="(condition, idx) in group.treatments"
            :key="condition.id"
          >
            <span class="flex items-baseline gap-1">
              <span>{{ getTreatmentLabel(condition) }}</span>
              <span
                v-if="condition.surfaces?.length"
                class="text-caption text-muted tnum"
              >
                {{ formatSurfaces(condition.surfaces) }}
              </span>
              <!-- Per-treatment action slot (e.g. clinical_notes' note button). -->
              <ModuleSlot
                v-if="condition.treatment_id"
                name="odontogram.condition.actions"
                :ctx="{
                  treatmentId: condition.treatment_id,
                  toothNumber: group.toothNumber,
                  status: condition.status,
                  patientId: patientId
                }"
              />
            </span>
            <span
              v-if="idx < group.treatments.length - 1"
              class="text-subtle"
            >·</span>
          </template>
        </div>
      </li>
    </ul>

    <!-- General conditions (no tooth) -->
    <div
      v-if="generalConditions.length > 0"
      class="mt-3 alert-surface-info rounded-token-lg p-3"
    >
      <div class="flex items-center gap-2 mb-2">
        <UIcon
          name="i-lucide-user"
          class="w-4 h-4 text-info-accent"
        />
        <span class="font-medium">{{ t('clinical.diagnosis.generalConditions') }}</span>
      </div>
      <ul class="ms-6 space-y-1">
        <li
          v-for="condition in generalConditions"
          :key="condition.id"
          class="text-sm"
        >
          {{ getTreatmentLabel(condition) }}
        </li>
      </ul>
    </div>
  </div>
</template>
