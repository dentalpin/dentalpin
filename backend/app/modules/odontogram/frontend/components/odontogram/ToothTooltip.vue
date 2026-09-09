<script setup lang="ts">
import type { ToothTreatmentView, TreatmentStatus } from '~~/app/types'
import { getTreatmentColor } from '~~/app/config/odontogramConstants'
import { getTreatmentDisplayName } from '~~/app/utils/treatmentView'

const props = defineProps<{
  toothNumber: number
  treatments: ToothTreatmentView[]
}>()

const emit = defineEmits<{
  editTreatment: [treatment: ToothTreatmentView]
  performTreatment: [treatment: ToothTreatmentView]
  deleteTreatment: [treatment: ToothTreatmentView]
}>()

const { t, locale } = useI18n()

// Get tooth name based on number
function getToothName(toothNumber: number): string {
  const num = toothNumber % 10
  const quadrant = Math.floor(toothNumber / 10)
  const isUpper = quadrant === 1 || quadrant === 2 || quadrant === 5 || quadrant === 6
  const isRight = quadrant === 1 || quadrant === 4 || quadrant === 5 || quadrant === 8

  const names: Record<number, string> = {
    1: t('odontogram.toothNames.centralIncisor'),
    2: t('odontogram.toothNames.lateralIncisor'),
    3: t('odontogram.toothNames.canine'),
    4: t('odontogram.toothNames.firstPremolar'),
    5: t('odontogram.toothNames.secondPremolar'),
    6: t('odontogram.toothNames.firstMolar'),
    7: t('odontogram.toothNames.secondMolar'),
    8: t('odontogram.toothNames.thirdMolar')
  }

  const position = isUpper ? t('odontogram.positions.upper') : t('odontogram.positions.lower')
  const side = isRight ? t('odontogram.positions.right') : t('odontogram.positions.left')

  return `${names[num] || `#${num}`} ${position} ${side}`
}

// Group treatments by status
const groupedTreatments = computed(() => {
  const groups: Record<TreatmentStatus, ToothTreatmentView[]> = {
    planned: [],
    existing: []
  }
  for (const treatment of props.treatments) {
    groups[treatment.status]?.push(treatment)
  }
  return groups
})

const hasAnyTreatments = computed(() => props.treatments.length > 0)

function getTreatmentLabel(treatment: ToothTreatmentView): string {
  return getTreatmentDisplayName(treatment, locale.value, t)
}

function _getStatusColor(status: TreatmentStatus): string {
  const colorMap: Record<TreatmentStatus, string> = {
    existing: 'neutral',
    planned: 'warning'
  }
  return colorMap[status] || 'neutral'
}

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString()
}

function handleEditClick(event: Event, treatment: ToothTreatmentView) {
  event.stopPropagation()
  event.preventDefault()
  emit('editTreatment', treatment)
}
</script>

<template>
  <div class="tooth-tooltip">
    <!-- Header -->
    <div class="tooltip-header">
      <div class="flex items-center gap-2">
        <span class="tooth-number-badge">{{ toothNumber }}</span>
        <span class="tooth-name">{{ getToothName(toothNumber) }}</span>
      </div>
    </div>

    <!-- Treatments list -->
    <div
      v-if="hasAnyTreatments"
      class="treatments-section"
    >
      <!-- Planned treatments -->
      <div
        v-if="groupedTreatments.planned.length > 0"
        class="treatment-group"
      >
        <div class="group-header group-planned">
          <UIcon
            name="i-lucide-clock"
            class="w-3 h-3"
          />
          <span>{{ t('odontogram.status.planned') }}</span>
        </div>
        <div
          v-for="treatment in groupedTreatments.planned"
          :key="treatment.id"
          class="treatment-item"
          @click="handleEditClick($event, treatment)"
        >
          <div class="treatment-main">
            <span
              class="treatment-dot"
              :style="{ backgroundColor: getTreatmentColor(treatment.treatment_type) }"
            />
            <span class="treatment-name">{{ getTreatmentLabel(treatment) }}</span>
            <UBadge
              v-if="treatment.surfaces?.length"
              color="neutral"
              variant="subtle"
              size="xs"
            >
              {{ treatment.surfaces.join('-') }}
            </UBadge>
          </div>
        </div>
      </div>

      <!-- Existing treatments -->
      <div
        v-if="groupedTreatments.existing.length > 0"
        class="treatment-group"
      >
        <div class="group-header group-existing">
          <UIcon
            name="i-lucide-check-circle"
            class="w-3 h-3"
          />
          <span>{{ t('odontogram.status.existing') }}</span>
        </div>
        <div
          v-for="treatment in groupedTreatments.existing"
          :key="treatment.id"
          class="treatment-item"
          @click="handleEditClick($event, treatment)"
        >
          <div class="treatment-main">
            <span
              class="treatment-dot"
              :style="{ backgroundColor: getTreatmentColor(treatment.treatment_type) }"
            />
            <span class="treatment-name">{{ getTreatmentLabel(treatment) }}</span>
            <UBadge
              v-if="treatment.surfaces?.length"
              color="neutral"
              variant="subtle"
              size="xs"
            >
              {{ treatment.surfaces.join('-') }}
            </UBadge>
          </div>
          <div
            v-if="treatment.performed_at"
            class="treatment-date"
          >
            {{ formatDate(treatment.performed_at) }}
          </div>
        </div>
      </div>
    </div>

    <!-- Empty state -->
    <div
      v-else
      class="empty-state"
    >
      <span class="text-subtle text-xs">{{ t('odontogram.treatments.noTreatments') }}</span>
    </div>

    <!-- Click hint -->
    <div
      v-if="hasAnyTreatments"
      class="click-hint"
    >
      <UIcon
        name="i-lucide-mouse-pointer-click"
        class="w-3 h-3"
      />
      <span>{{ t('odontogram.tooltip.clickToEdit') }}</span>
    </div>
  </div>
</template>

<style scoped>
.tooth-tooltip {
  min-width: 200px;
  max-width: 280px;
}

.tooltip-header {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding-bottom: 8px;
  border-bottom: 1px solid #E5E7EB;
  margin-bottom: 8px;
}

:root.dark .tooltip-header {
  border-color: #374151;
}

.tooth-number-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 24px;
  height: 20px;
  padding: 0 6px;
  background: #3B82F6;
  color: white;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}

.tooth-name {
  font-size: 12px;
  font-weight: 500;
  color: #374151;
}

:root.dark .tooth-name {
  color: #E5E7EB;
}

.treatments-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 200px;
  overflow-y: auto;
}

.treatment-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.group-header {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.group-planned {
  color: #D97706;
}

.group-existing {
  color: #6B7280;
}

.treatment-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 6px 8px;
  margin-inline-start: 8px;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.15s;
}

.treatment-item:hover {
  background-color: #F3F4F6;
}

:root.dark .treatment-item:hover {
  background-color: #374151;
}

.treatment-main {
  display: flex;
  align-items: center;
  gap: 6px;
}

.treatment-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.treatment-name {
  font-size: 12px;
  font-weight: 500;
  color: #374151;
}

:root.dark .treatment-name {
  color: #E5E7EB;
}

.treatment-date {
  font-size: 10px;
  color: #9CA3AF;
  margin-inline-start: 14px;
}

.empty-state {
  padding: 8px 0;
  text-align: center;
}

.click-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding-top: 8px;
  margin-top: 8px;
  border-top: 1px solid #E5E7EB;
  font-size: 10px;
  color: #9CA3AF;
}

:root.dark .click-hint {
  border-color: #374151;
}
</style>
