<script setup lang="ts">
/**
 * ChangesList - Display odontogram changes at a specific date
 *
 * Shows treatments added, modified, or completed on the selected date.
 */

import type { ToothTreatmentView, Treatment } from '~~/app/types'
import { viewForTooth } from '~~/app/utils/treatmentView'

const props = defineProps<{
  changes: Treatment[]
}>()

const { t } = useI18n()

// Flatten Treatment[] into per-tooth rows, then split added vs completed.
const groupedChanges = computed(() => {
  const added: ToothTreatmentView[] = []
  const completed: ToothTreatmentView[] = []
  for (const change of props.changes) {
    for (const tooth of change.teeth) {
      const v = viewForTooth(change, tooth.tooth_number)
      if (!v) continue
      if (v.performed_at) completed.push(v)
      else added.push(v)
    }
  }
  return { added, completed }
})

function getTreatmentLabel(treatment: ToothTreatmentView): string {
  const key = `odontogram.treatments.types.${treatment.treatment_type}`
  const translated = t(key, treatment.treatment_type)
  return translated !== key ? translated : treatment.treatment_type
}

function formatToothInfo(treatment: ToothTreatmentView): string {
  let info = `${t('clinical.tooth')} ${treatment.tooth_number}`
  if (treatment.surfaces && treatment.surfaces.length > 0) {
    info += ` (${treatment.surfaces.join(', ')})`
  }
  return info
}
</script>

<template>
  <div class="space-y-3">
    <!-- No changes -->
    <div
      v-if="changes.length === 0"
      class="text-center py-4 text-muted"
    >
      <UIcon
        name="i-lucide-calendar-x"
        class="w-8 h-8 mx-auto mb-2 opacity-50"
      />
      <p>{{ t('clinical.history.noChanges') }}</p>
    </div>

    <!-- Treatments added -->
    <div v-if="groupedChanges.added.length > 0">
      <h4 class="text-caption text-muted mb-2 flex items-center gap-2">
        <UIcon
          name="i-lucide-plus-circle"
          class="w-4 h-4 text-info-accent"
        />
        {{ t('odontogram.changeHistory.treatmentAdded') }}
      </h4>
      <ul class="space-y-2">
        <li
          v-for="change in groupedChanges.added"
          :key="change.id"
          class="alert-surface-info rounded-token-md px-3 py-2 flex items-center gap-3"
        >
          <div class="flex-1">
            <span class="font-medium">{{ getTreatmentLabel(change) }}</span>
            <span class="text-sm text-muted ms-2">
              {{ formatToothInfo(change) }}
            </span>
          </div>
          <UBadge
            :color="change.status === 'planned' ? 'error' : 'neutral'"
            variant="subtle"
            size="xs"
          >
            {{ t(`odontogram.status.${change.status}`) }}
          </UBadge>
        </li>
      </ul>
    </div>

    <!-- Treatments completed -->
    <div v-if="groupedChanges.completed.length > 0">
      <h4 class="text-caption text-muted mb-2 flex items-center gap-2">
        <UIcon
          name="i-lucide-check-circle"
          class="w-4 h-4 text-success-accent"
        />
        {{ t('common.completed') }}
      </h4>
      <ul class="space-y-2">
        <li
          v-for="change in groupedChanges.completed"
          :key="change.id"
          class="alert-surface-success rounded-token-md px-3 py-2 flex items-center gap-3"
        >
          <div class="flex-1">
            <span class="font-medium">{{ getTreatmentLabel(change) }}</span>
            <span class="text-caption text-muted ms-2">
              {{ formatToothInfo(change) }}
            </span>
          </div>
          <UIcon
            name="i-lucide-check"
            class="w-4 h-4 text-success-accent"
          />
        </li>
      </ul>
    </div>
  </div>
</template>
