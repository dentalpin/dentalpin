<script setup lang="ts">
/**
 * SEPA chart orchestrator.
 *
 * Routes the inline edits from `PerioArchBlock` into the autosave
 * queue, and surfaces session actions (close / discard) on the top
 * header card instead of a sticky bottom bar — keeps the
 * periodontogram aligned with the rest of the patient file's "main
 * actions live up top" convention.
 */
import { computed, onBeforeUnmount, onMounted, watch } from 'vue'
import type { PerioIndices, PerioSnapshotDetail, PerioSnapshotSummary, PerioTooth, SiteCode } from '../types'
import { usePeriodontogramSession } from '../composables/usePeriodontogramSession'

// Mirrors backend constants — client-side live indices must match the
// formula the backend persists at close. Denominators anchor to
// (present teeth × 6 sites); unmeasured sites count as zero rather
// than dropping out, so a half-done exam doesn't report inflated
// percentages.
const DEEP_POCKET_THRESHOLD_MM = 5
const SITES_PER_TOOTH = 6

const props = defineProps<{
  snapshot: PerioSnapshotDetail
  readonly?: boolean
  // Mutators owned by the parent's ref so optimistic updates fire on
  // the same reactive object the timeline/view holds — mutating
  // `props.snapshot` directly is unreliable across Vue prop proxies.
  applySitePatch: (toothNumber: number, siteCode: SiteCode, patch: Record<string, unknown>) => void
  applyToothPatch: (toothNumber: number, patch: Record<string, unknown>) => void
}>()

const emit = defineEmits<{
  closed: [snapshot: PerioSnapshotDetail]
  discarded: []
}>()

const toast = useToast()
const { t } = useI18n()

const {
  saving,
  dirty,
  lastError,
  patchTooth,
  patchSite,
  flushPending,
  closeSession,
  discardDraft
} = usePeriodontogramSession()

watch(lastError, (err) => {
  if (err) {
    toast.add({
      title: t('periodontogram.errors.saveFailed'),
      description: t('periodontogram.errors.checkConnection'),
      color: 'error',
      icon: 'i-lucide-alert-triangle'
    })
  }
})

function _beforeUnload(event: BeforeUnloadEvent) {
  if (dirty.value || saving.value) {
    event.preventDefault()
    event.returnValue = ''
  }
}

onMounted(() => {
  if (typeof window !== 'undefined') {
    window.addEventListener('beforeunload', _beforeUnload)
  }
})

onBeforeUnmount(() => {
  if (typeof window !== 'undefined') {
    window.removeEventListener('beforeunload', _beforeUnload)
  }
})

const isReadOnly = computed(() => props.readonly || props.snapshot.status === 'closed')

const upperTeeth = computed(() =>
  props.snapshot.teeth.filter(t => Math.floor(t.tooth_number / 10) <= 2)
)
const lowerTeeth = computed(() =>
  props.snapshot.teeth.filter(t => Math.floor(t.tooth_number / 10) >= 3)
)

// Optimistic-first: the parent's mutator updates `currentSnapshot.value`
// so the cell repaints on the next frame, then we queue the debounced
// PATCH. No refetch round-trip — backend confirmation is silent and the
// saved indicator on the banner reflects the actual save state.
function handleEditSite(toothNumber: number, siteCode: SiteCode, patch: Record<string, unknown>) {
  if (isReadOnly.value) return
  props.applySitePatch(toothNumber, siteCode, patch)
  patchSite(props.snapshot.id, toothNumber, siteCode, patch)
}

function handleEditTooth(toothNumber: number, patch: Record<string, unknown>) {
  if (isReadOnly.value) return
  props.applyToothPatch(toothNumber, patch)
  patchTooth(props.snapshot.id, toothNumber, patch)
}

async function handleClose(notes: string | null) {
  await flushPending(props.snapshot.id)
  const closed = await closeSession(props.snapshot.id, notes ?? undefined)
  emit('closed', closed)
}

async function handleDiscard() {
  await discardDraft(props.snapshot.id)
  emit('discarded')
}

const summary = computed<PerioSnapshotSummary>(() => ({
  id: props.snapshot.id,
  patient_id: props.snapshot.patient_id,
  status: props.snapshot.status,
  recorded_at: props.snapshot.recorded_at,
  closed_at: props.snapshot.closed_at
}))

// Live indices recomputed from the in-memory teeth/sites on every edit
// (drafts only — closed snapshots show the frozen backend value).
// Mirrors `backend/app/modules/periodontogram/indices.py`.
function _computeIndices(teeth: PerioTooth[]): PerioIndices {
  const presentTeeth = teeth.filter(t => t.is_present)
  const totalSites = presentTeeth.length * SITES_PER_TOOTH
  if (totalSites === 0) {
    return { bop_pct: 0, pi_pct: 0, cal_mean_mm: 0, deep_pockets_count: 0 }
  }
  let bop = 0
  let plaque = 0
  let calSum = 0
  let deep = 0
  for (const t of presentTeeth) {
    let toothHasDeepPocket = false
    for (const s of t.sites) {
      if (s.bleeding_on_probing) bop++
      if (s.plaque) plaque++
      if (s.probing_depth_mm != null && s.gingival_margin_mm != null) {
        calSum += s.probing_depth_mm + s.gingival_margin_mm
      }
      if (s.probing_depth_mm != null && s.probing_depth_mm >= DEEP_POCKET_THRESHOLD_MM) {
        toothHasDeepPocket = true
      }
    }
    if (toothHasDeepPocket) deep++
  }
  return {
    bop_pct: (100 * bop) / totalSites,
    pi_pct: (100 * plaque) / totalSites,
    cal_mean_mm: calSum / totalSites,
    deep_pockets_count: deep
  }
}

const liveIndices = computed<PerioIndices | null>(() => {
  if (isReadOnly.value) return props.snapshot.indices
  return _computeIndices(props.snapshot.teeth)
})
</script>

<template>
  <div class="periodontogram-chart space-y-4">
    <PerioIndicesBanner
      :indices="liveIndices"
      :snapshot="summary"
      :saving="saving"
      :dirty="dirty"
      @close="handleClose"
      @discard="handleDiscard"
    />

    <div
      class="overflow-x-auto pb-2"
      role="region"
      :aria-label="t('periodontogram.chart.ariaLabel')"
    >
      <div class="min-w-[1100px] space-y-4">
        <PerioArchBlock
          arch="upper"
          :teeth="upperTeeth"
          :readonly="isReadOnly"
          @edit-tooth="handleEditTooth"
          @edit-site="handleEditSite"
        />
        <PerioArchBlock
          arch="lower"
          :teeth="lowerTeeth"
          :readonly="isReadOnly"
          @edit-tooth="handleEditTooth"
          @edit-site="handleEditSite"
        />
      </div>
    </div>
  </div>
</template>
