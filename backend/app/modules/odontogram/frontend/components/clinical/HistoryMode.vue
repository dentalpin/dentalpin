<script setup lang="ts">
/**
 * HistoryMode - View historical odontogram states
 *
 * Features:
 * - Timeline slider to navigate through dates
 * - Read-only odontogram showing state at selected date
 * - List of changes that occurred on selected date
 */

import type { OdontogramHistoryEntry } from '~~/app/types'
import { parseDateOnly } from '~~/app/utils/wallClock'

const props = defineProps<{
  patientId: string
}>()

const { t } = useI18n()

// ============================================================================
// Composables
// ============================================================================

const {
  timelineDates,
  viewingDate,
  timelineLoading,
  isViewingHistory,
  historicalTreatments,
  treatments,
  fetchTimeline,
  fetchOdontogramAtDate,
  fetchTreatments,
  fetchPatientHistory,
  returnToCurrentView
} = useOdontogram()

// ============================================================================
// State
// ============================================================================

const loading = ref(false)
const historyData = ref<OdontogramHistoryEntry[]>([])
const historyLoading = ref(false)

// ============================================================================
// Computed
// ============================================================================

// Format viewing date for display
const formattedViewingDate = computed(() => {
  if (!viewingDate.value) return t('common.today')
  return parseDateOnly(viewingDate.value).toLocaleDateString()
})

// Changes at the currently selected date
const changesAtDate = computed(() => {
  if (!viewingDate.value) return []

  // Filter treatments that were recorded or performed on the viewing date
  return historicalTreatments.value.filter((treatment) => {
    const recordedDate = treatment.recorded_at?.split('T')[0]
    const performedDate = treatment.performed_at?.split('T')[0]
    return recordedDate === viewingDate.value || performedDate === viewingDate.value
  })
})

// ============================================================================
// Lifecycle
// ============================================================================

onMounted(async () => {
  loading.value = true
  try {
    await Promise.all([
      fetchTimeline(props.patientId),
      fetchTreatments(props.patientId)
    ])
    // If there are dates, select the most recent one by default
    const mostRecent = timelineDates.value.at(-1)
    if (mostRecent) {
      await fetchOdontogramAtDate(props.patientId, mostRecent.date)
    }
  } finally {
    loading.value = false
  }
})

// ============================================================================
// Methods
// ============================================================================

async function handleDateChange(date: string | null) {
  if (date) {
    await fetchOdontogramAtDate(props.patientId, date)
  } else {
    returnToCurrentView()
  }
}

async function onHistoryExpanded(expanded: boolean) {
  if (expanded && !historyData.value.length) {
    historyLoading.value = true
    const response = await fetchPatientHistory(props.patientId)
    if (response) historyData.value = response.data
    historyLoading.value = false
  }
}
</script>

<template>
  <div class="space-y-4">
    <!-- Loading state -->
    <div
      v-if="loading || timelineLoading"
      class="flex items-center justify-center py-8"
    >
      <UIcon
        name="i-lucide-loader-2"
        class="w-8 h-8 animate-spin text-primary-accent"
      />
    </div>

    <template v-else>
      <!-- No history available -->
      <UCard v-if="timelineDates.length === 0">
        <EmptyState
          icon="i-lucide-history"
          :title="t('odontogram.timeline.noHistory')"
          :description="t('clinical.history.noChanges')"
        />
      </UCard>

      <template v-else>
        <!-- Timeline Slider -->
        <UCard>
          <template #header>
            <SectionHeader
              icon="i-lucide-history"
              :title="t('odontogram.timeline.title')"
            >
              <template
                v-if="isViewingHistory"
                #action
              >
                <UButton
                  variant="ghost"
                  size="xs"
                  icon="i-lucide-arrow-right"
                  trailing
                  @click="handleDateChange(null)"
                >
                  {{ t('odontogram.timeline.returnToNow') }}
                </UButton>
              </template>
            </SectionHeader>
          </template>

          <TimelineSlider
            :dates="timelineDates"
            :current-date="viewingDate"
            @update:current-date="handleDateChange"
          />
        </UCard>

        <!-- Odontogram (read-only) -->
        <UCard>
          <template #header>
            <div class="flex items-center gap-2">
              <UIcon
                name="i-lucide-calendar"
                class="w-5 h-5 text-subtle"
              />
              <span>{{ t('clinical.history.stateAt') }}</span>
              <UBadge
                color="primary"
                variant="subtle"
              >
                {{ formattedViewingDate }}
              </UBadge>
            </div>
          </template>

          <OdontogramChart
            :patient-id="patientId"
            mode="view-only"
            :at-date="viewingDate"
          />
        </UCard>

        <!-- Changes on this date -->
        <UCard v-if="viewingDate">
          <template #header>
            <SectionHeader
              icon="i-lucide-file-diff"
              :title="t('clinical.history.changesOnDate')"
            />
          </template>

          <ChangesList :changes="changesAtDate" />
        </UCard>

        <!-- Treatment list -->
        <TreatmentListSection :treatments="treatments" />

        <!-- Change history -->
        <ChangeHistorySection
          :history="historyData"
          :treatments="treatments"
          :loading="historyLoading"
          @update:expanded="onHistoryExpanded"
        />
      </template>
    </template>
  </div>
</template>
