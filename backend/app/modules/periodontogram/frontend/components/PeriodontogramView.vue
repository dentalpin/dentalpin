<script setup lang="ts">
/**
 * Entry point rendered by the `patient.diagnosis.subtabs` slot.
 *
 * Composes the SEPA chart with the timeline slider so the dentist can
 * walk between closed snapshots and the current draft, plus the
 * history banner when viewing a frozen state.
 */

import { computed, onMounted, ref, watch } from 'vue'
import { usePeriodontogram } from '../composables/usePeriodontogram'

const props = defineProps<{
  patientId: string
  readonly?: boolean
}>()

const { t } = useI18n()
const starting = ref(false)

const {
  timeline,
  currentSnapshot,
  isLoading,
  error,
  hasDraft,
  closedCount,
  isEmpty,
  fetchTimeline,
  fetchSnapshot,
  startDraft,
  applySitePatch,
  applyToothPatch
} = usePeriodontogram(() => props.patientId)

const viewingDate = ref<string | null>(null)
const isViewingHistory = computed(() => viewingDate.value !== null)

async function loadCurrentView() {
  if (hasDraft.value && timeline.value?.draft) {
    await fetchSnapshot(timeline.value.draft.id)
  } else if (timeline.value && timeline.value.dates.length > 0) {
    const last = timeline.value.dates[timeline.value.dates.length - 1]
    await fetchSnapshot(last.snapshot_id)
  } else {
    currentSnapshot.value = null
  }
  viewingDate.value = null
}

async function refreshAll() {
  await fetchTimeline()
  await loadCurrentView()
}

onMounted(refreshAll)
watch(() => props.patientId, refreshAll)

async function handleStart() {
  starting.value = true
  try {
    await startDraft()
    if (timeline.value?.draft) {
      await fetchSnapshot(timeline.value.draft.id)
    }
  } finally {
    starting.value = false
  }
}

async function handleDateChange(date: string | null) {
  if (date === null) {
    await loadCurrentView()
    return
  }
  const entry = timeline.value?.dates.find(d => d.date === date)
  if (!entry) return
  viewingDate.value = date
  await fetchSnapshot(entry.snapshot_id)
}

async function handleClosed() {
  await refreshAll()
}

async function handleDiscarded() {
  await refreshAll()
}
</script>

<template>
  <div class="periodontogram-view space-y-4">
    <div
      v-if="isLoading && !currentSnapshot"
      class="flex items-center gap-2 text-sm text-muted"
    >
      <UIcon
        name="i-lucide-loader-2"
        class="animate-spin"
      />
      <span>{{ t('periodontogram.loading') }}</span>
    </div>

    <UAlert
      v-else-if="error"
      color="error"
      variant="soft"
      icon="i-lucide-alert-triangle"
      :title="t('periodontogram.errors.loadFailed')"
    />

    <PerioEmptyState
      v-else-if="isEmpty"
      :loading="starting"
      @start="handleStart"
    />

    <template v-else-if="currentSnapshot">
      <PerioHistoryBanner
        v-if="isViewingHistory && viewingDate"
        :date="viewingDate"
        @return-to-current="handleDateChange(null)"
      />

      <TimelineSlider
        v-if="timeline && timeline.dates.length > 0"
        :dates="timeline.dates.map(d => ({ date: d.date, change_count: d.change_count }))"
        :current-date="viewingDate"
        @update:current-date="handleDateChange"
      />

      <PeriodontogramChart
        :snapshot="currentSnapshot"
        :readonly="readonly || isViewingHistory"
        :apply-site-patch="applySitePatch"
        :apply-tooth-patch="applyToothPatch"
        @closed="handleClosed"
        @discarded="handleDiscarded"
      />

      <UCard v-if="!hasDraft && !isViewingHistory">
        <div class="flex items-center justify-between">
          <span class="text-sm text-muted">
            {{ closedCount }} sesiones cerradas
          </span>
          <UButton
            size="sm"
            icon="i-lucide-plus"
            :loading="starting"
            :disabled="readonly"
            @click="handleStart"
          >
            {{ t('periodontogram.session.openDraft') }}
          </UButton>
        </div>
      </UCard>
    </template>
  </div>
</template>
