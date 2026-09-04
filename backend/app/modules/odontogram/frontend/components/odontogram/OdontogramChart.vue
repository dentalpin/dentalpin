<script setup lang="ts">
/**
 * OdontogramChart - Main dental chart component
 *
 * Features:
 * - Interactive tooth visualization with dual view (occlusal + lateral)
 * - Click-to-apply treatment mode with keyboard shortcuts
 * - Timeline slider for historical view
 * - Treatment management (add, edit, delete, perform)
 */

import type {
  ClinicalType,
  OdontogramHistoryEntry,
  Surface,
  ToothTreatmentView,
  Treatment,
  TreatmentCreate,
  TreatmentStatus
} from '~~/app/types'
import { PERMANENT_TEETH, DECIDUOUS_TEETH, TREATMENT_SHORTCUTS } from '~~/app/constants/odontogram'
import { calculateToothRange, getMultiToothConfig, isSameArch } from '~~/app/config/odontogramConstants'
import { viewsForTooth } from '~~/app/utils/treatmentView'
import { isSurfaceTreatment } from './TreatmentIcons'

export type OdontogramMode = 'full' | 'view-only' | 'diagnosis' | 'planning'

const props = withDefaults(defineProps<{
  patientId: string
  mode?: OdontogramMode
  statusFilter?: TreatmentStatus[]
  /** Teeth to highlight (for hover linking from parent) */
  highlightedTeethProp?: number[]
  /** Global treatment IDs to highlight in the globals strip (hover linking). */
  highlightedGlobalIds?: string[]
  /** Plan ID for filtering treatments in planning mode */
  planId?: string
  /** Plan title shown as context banner inside the TreatmentBar (planning mode). */
  planTitle?: string
}>(), {
  mode: 'full',
  highlightedTeethProp: () => [],
  highlightedGlobalIds: () => []
})

const emit = defineEmits<{
  treatmentAdd: [treatment: Treatment]
  treatmentPerform: [treatmentId: string]
  /** Fired after any treatment mutation (add/update/delete/perform) */
  treatmentsChanged: []
  /** Emitted when user hovers over a tooth (for hover linking) */
  toothHover: [toothNumber: number | null]
  /** Emitted when user hovers a chip in the globals strip. */
  globalHover: [treatmentId: string | null]
  /** Arch currently under hover (for painting the arch halo). */
  archHover: [arch: 'upper' | 'lower' | null]
}>()

const { t } = useI18n()
const toast = useToast()

// ============================================================================
// Composables
// ============================================================================

const {
  loading,
  error,
  fetchOdontogram,
  fetchPatientHistory,
  getToothRecord,
  treatments,
  treatmentsLoading,
  fetchTreatments,
  createTreatment,
  performTreatment,
  deleteTreatment,
  updateTreatment,
  getToothTreatments,
  timelineDates,
  viewingDate,
  timelineLoading,
  isViewingHistory,
  displayTreatments,
  fetchTimeline,
  fetchOdontogramAtDate,
  returnToCurrentView
} = useOdontogram()

const treatmentPlansApi = useTreatmentPlans()

// ============================================================================
// State
// ============================================================================

const dentitionMode = ref<'permanent' | 'deciduous'>('permanent')
const selectedTooth = ref<number | null>(null)
const showSurfaceSelector = ref(false)
const hoveredTooth = ref<number | null>(null)
const internalHighlightedTeeth = ref<number[]>([])
/** Arch currently under hover from the globals strip — paints a subtle halo. */
const hoveredArch = ref<'upper' | 'lower' | null>(null)

function handleGlobalHover(id: string | null) {
  emit('globalHover', id)
}
function handleArchHover(arch: 'upper' | 'lower' | null) {
  hoveredArch.value = arch
  emit('archHover', arch)
}

// Merge internal highlighted teeth with prop (for hover linking).
// Multi-tooth selection has its own dedicated style via `multi-selected-teeth`.
const highlightedTeeth = computed(() => [
  ...internalHighlightedTeeth.value,
  ...props.highlightedTeethProp
])

// Click-to-apply mode. Stores the clinical_type (e.g. 'crown', 'bridge') and/or
// catalog item selected via the TreatmentBar. Catalog-item selection is tracked
// separately in `selectedCatalogItemId`.
const selectedTreatmentType = ref<string | null>(null)
const selectedCatalogItemId = ref<string | null>(null)
const selectedTreatmentStatus = ref<TreatmentStatus>('existing')

// Multi-tooth selection (bridges, splints, multiple veneers/crowns)
const multiToothSelection = ref<{ teeth: number[], anchor: number | null }>({ teeth: [], anchor: null })
const showMultiToothConfirm = ref(false)

// Undo stack (single entry per Treatment, whether single- or multi-tooth).
const undoStack = ref<Array<{ treatmentId: string, type: string }>>([])

// History section
const historyData = ref<OdontogramHistoryEntry[]>([])
const historyLoading = ref(false)

// Treatment editing (per-tooth view — edit modal operates on single-tooth context).
const showTreatmentEditModal = ref(false)
const editingTreatment = ref<ToothTreatmentView | null>(null)

// Always show dual view
const showLateral = true

// ============================================================================
// Computed
// ============================================================================

const isReadonly = computed(() => props.mode === 'view-only' || isViewingHistory.value)
const isPlanningMode = computed(() => props.mode === 'planning')
const isDiagnosisMode = computed(() => props.mode === 'diagnosis')

// Map OdontogramChart mode to TreatmentBar mode
const treatmentBarMode = computed(() => {
  if (props.mode === 'diagnosis') return 'diagnosis'
  if (props.mode === 'planning') return 'planning'
  return 'full'
})
const isClickToApplyMode = computed(() => selectedTreatmentType.value !== null)

const multiToothConfig = computed(() => {
  if (!selectedTreatmentType.value) return null
  return getMultiToothConfig(selectedTreatmentType.value as string)
})

const isMultiToothMode = computed(() => multiToothConfig.value !== null)

const teethLayout = computed(() =>
  dentitionMode.value === 'permanent' ? PERMANENT_TEETH : DECIDUOUS_TEETH
)

const pendingTreatment = computed(() => {
  if (!selectedTreatmentType.value) return null
  // Multi-tooth keys (bridge, multiple_veneers...) are UI-only. Skip the single-tooth preview.
  if (isMultiToothMode.value) return null
  return {
    type: selectedTreatmentType.value as ClinicalType,
    status: selectedTreatmentStatus.value
  }
})

// ============================================================================
// Lifecycle
// ============================================================================

async function loadAll(patientId: string) {
  await Promise.all([
    fetchOdontogram(patientId),
    fetchTreatments(patientId),
    fetchTimeline(patientId)
  ])
}

onMounted(async () => {
  await loadAll(props.patientId)
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})

watch(() => props.patientId, async (newId) => {
  if (newId) {
    returnToCurrentView()
    await Promise.all([
      fetchOdontogram(newId),
      fetchTreatments(newId),
      fetchTimeline(newId)
    ])
  }
})

// Emit tooth hover for parent hover linking
watch(hoveredTooth, (toothNumber) => {
  emit('toothHover', toothNumber)
})

// ============================================================================
// Tooth Data Helpers
// ============================================================================

function getToothData(toothNumber: number) {
  const record = getToothRecord(toothNumber)
  return {
    generalCondition: record?.general_condition || 'healthy',
    isDisplaced: record?.is_displaced ?? false,
    isRotated: record?.is_rotated ?? false
  }
}

function treatmentIncludesTooth(treatment: Treatment, toothNumber: number): boolean {
  return treatment.teeth.some(t => t.tooth_number === toothNumber)
}

/** Return per-tooth views for a given tooth number, honoring statusFilter. */
function getFilteredTreatments(toothNumber: number): ToothTreatmentView[] {
  const source: Treatment[] = isViewingHistory.value
    ? displayTreatments.value.filter(t => treatmentIncludesTooth(t, toothNumber))
    : getToothTreatments(toothNumber)

  const views = viewsForTooth(source, toothNumber)
  if (!props.statusFilter?.length) return views
  return views.filter(v => props.statusFilter?.includes(v.status))
}

/** Treatment id shared by all teeth of a multi-tooth treatment (used for connectors). */
function getToothGroupId(toothNumber: number): string | null {
  const list = getFilteredTreatments(toothNumber)
  const multi = list.find(v => v.is_multi)
  return multi?.treatment_id ?? null
}

function getToothGroupStatus(toothNumber: number): TreatmentStatus | null {
  const list = getFilteredTreatments(toothNumber)
  const multi = list.find(v => v.is_multi)
  return multi?.status ?? null
}

function getToothGroupType(toothNumber: number): string | null {
  const list = getFilteredTreatments(toothNumber)
  const multi = list.find(v => v.is_multi)
  return multi?.clinical_type ?? null
}

/** If the bridge crosses the midline (e.g. 12-11-21-22), both teeth belong
 *  to the same group and the connector sits in the quadrant divider slot. */
function midlineBridgeStatus(leftTooth: number, rightTooth: number): 'existing' | 'planned' | null {
  const leftId = getToothGroupId(leftTooth)
  const rightId = getToothGroupId(rightTooth)
  if (!leftId || leftId !== rightId) return null
  if (getToothGroupType(leftTooth) !== 'bridge') return null
  const status = getToothGroupStatus(leftTooth)
  if (status !== 'existing' && status !== 'planned') return null
  return status
}

const upperMidlineBridgeStatus = computed<'existing' | 'planned' | null>(() => {
  const right = teethLayout.value.upperRight
  const left = teethLayout.value.upperLeft
  const r = right[right.length - 1]
  const l = left[0]
  if (r === undefined || l === undefined) return null
  return midlineBridgeStatus(r, l)
})

const lowerMidlineBridgeStatus = computed<'existing' | 'planned' | null>(() => {
  const right = teethLayout.value.lowerRight
  const left = teethLayout.value.lowerLeft
  const r = right[right.length - 1]
  const l = left[0]
  if (r === undefined || l === undefined) return null
  return midlineBridgeStatus(r, l)
})

// ============================================================================
// Keyboard Shortcuts
// ============================================================================

function handleKeydown(e: KeyboardEvent) {
  if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return

  if (e.key === 'Escape') {
    if (isMultiToothMode.value && multiToothSelection.value.teeth.length > 0) {
      resetMultiToothSelection()
      return
    }
    cancelClickToApplyMode()
    return
  }

  if (e.key === 'Enter' && isMultiToothMode.value) {
    // When the confirm popup is open it owns the confirm action (including
    // per-tooth role toggles for bridges); let it handle Enter natively.
    if (!showMultiToothConfirm.value) {
      requestMultiToothConfirm()
    }
    return
  }

  if ((e.ctrlKey || e.metaKey) && e.key === 'z') {
    e.preventDefault()
    handleUndo()
    return
  }

  if (e.key.toLowerCase() === 'p') {
    selectedTreatmentStatus.value = 'planned'
    return
  }

  if (e.key.toLowerCase() === 'e') {
    selectedTreatmentStatus.value = 'existing'
    return
  }

  const shortcut = TREATMENT_SHORTCUTS[e.key]
  if (shortcut && !isReadonly.value) {
    selectedTreatmentType.value = shortcut
  }
}

// ============================================================================
// Click-to-Apply Mode
// ============================================================================

function handleSurfaceClick(toothNumber: number, surface: Surface) {
  if (isReadonly.value || !isClickToApplyMode.value) return

  // In multi-tooth mode, surface clicks collapse to tooth-level selection.
  if (isMultiToothMode.value) {
    handleMultiToothClick(toothNumber)
    return
  }

  if (isSurfaceTreatment(selectedTreatmentType.value!)) {
    applyTreatment(toothNumber, [surface])
  } else {
    applyTreatment(toothNumber)
  }
}

function handleToothClick(toothNumber: number) {
  if (isReadonly.value || !isClickToApplyMode.value) return

  if (isMultiToothMode.value) {
    handleMultiToothClick(toothNumber)
    return
  }

  if (isSurfaceTreatment(selectedTreatmentType.value!)) {
    selectedTooth.value = toothNumber
    showSurfaceSelector.value = true
  } else {
    applyTreatment(toothNumber)
  }
}

// ============================================================================
// Multi-tooth Selection
// ============================================================================

function handleMultiToothClick(toothNumber: number) {
  const cfg = multiToothConfig.value
  if (!cfg) return

  if (cfg.selectionMode === 'range') {
    if (multiToothSelection.value.anchor === null) {
      multiToothSelection.value = { teeth: [toothNumber], anchor: toothNumber }
      return
    }

    try {
      const range = calculateToothRange(multiToothSelection.value.anchor, toothNumber)
      if (range.length < cfg.minTeeth) {
        toast.add({
          title: t('odontogram.multiTooth.errors.tooFew', { n: cfg.minTeeth }),
          color: 'warning'
        })
        return
      }
      if (range.length > cfg.maxTeeth) {
        toast.add({
          title: t('odontogram.multiTooth.errors.tooMany', { n: cfg.maxTeeth }),
          color: 'warning'
        })
        return
      }
      multiToothSelection.value.teeth = range
      showMultiToothConfirm.value = true
    } catch {
      toast.add({
        title: t('odontogram.multiTooth.errors.sameArchRequired'),
        color: 'warning'
      })
    }
    return
  }

  // free selection mode
  const existing = multiToothSelection.value.teeth
  const idx = existing.indexOf(toothNumber)
  if (idx === -1) {
    const candidate = [...existing, toothNumber]
    if (cfg.requiresSameArch && !isSameArch(candidate)) {
      toast.add({
        title: t('odontogram.multiTooth.errors.sameArchRequired'),
        color: 'warning'
      })
      return
    }
    if (candidate.length > cfg.maxTeeth) {
      toast.add({
        title: t('odontogram.multiTooth.errors.tooMany', { n: cfg.maxTeeth }),
        color: 'warning'
      })
      return
    }
    multiToothSelection.value = { ...multiToothSelection.value, teeth: candidate }
  } else {
    multiToothSelection.value = {
      ...multiToothSelection.value,
      teeth: existing.filter(t => t !== toothNumber)
    }
  }
}

function canConfirmFreeSelection(): boolean {
  const cfg = multiToothConfig.value
  if (!cfg || cfg.selectionMode !== 'free') return false
  return multiToothSelection.value.teeth.length >= cfg.minTeeth
}

function requestMultiToothConfirm() {
  if (canConfirmFreeSelection()) {
    showMultiToothConfirm.value = true
  }
}

async function confirmMultiToothSelection(
  teethRoles: Array<{ tooth_number: number, role: 'pillar' | 'pontic' }> | null = null
) {
  const cfg = multiToothConfig.value
  if (!cfg) return
  const sortedTeeth = [...multiToothSelection.value.teeth].sort((a, b) => a - b)

  let status: TreatmentStatus = selectedTreatmentStatus.value
  if (isDiagnosisMode.value) status = 'existing'
  else if (isPlanningMode.value) status = 'planned'

  const payload: TreatmentCreate = {
    scope: 'multi_tooth',
    status
  }
  if (cfg.mode === 'bridge' && teethRoles && teethRoles.length > 0) {
    payload.teeth = teethRoles
  } else {
    payload.tooth_numbers = sortedTeeth
  }
  if (cfg.mode === 'uniform') {
    payload.clinical_type = cfg.key as ClinicalType
  } else {
    payload.clinical_type = 'bridge'
  }
  if (selectedCatalogItemId.value) {
    payload.catalog_item_id = selectedCatalogItemId.value
  }

  const created = await createTreatment(props.patientId, payload)
  if (!created) {
    showMultiToothConfirm.value = false
    return
  }

  if (isPlanningMode.value && props.planId) {
    await treatmentPlansApi.addItem(props.planId, { treatment_id: created.id })
  }

  undoStack.value.push({ treatmentId: created.id, type: cfg.key })
  resetMultiToothSelection()
  emit('treatmentAdd', created)
  emit('treatmentsChanged')
  selectedTreatmentType.value = null
  selectedCatalogItemId.value = null
}

function resetMultiToothSelection() {
  multiToothSelection.value = { teeth: [], anchor: null }
  showMultiToothConfirm.value = false
}

function handleToothContextMenu(toothNumber: number, event: MouseEvent) {
  if (isReadonly.value) return
  event.preventDefault()
  // Context menu could be implemented here if needed
}

async function applyTreatment(toothNumber: number, surfaces?: Surface[]) {
  if (!selectedTreatmentType.value && !selectedCatalogItemId.value) return

  let status: TreatmentStatus = selectedTreatmentStatus.value
  if (isDiagnosisMode.value) status = 'existing'
  else if (isPlanningMode.value) status = 'planned'

  const payload: TreatmentCreate = {
    tooth_numbers: [toothNumber],
    status,
    scope: 'tooth'
  }
  if (selectedCatalogItemId.value) {
    payload.catalog_item_id = selectedCatalogItemId.value
  }
  if (selectedTreatmentType.value) {
    payload.clinical_type = selectedTreatmentType.value as ClinicalType
  }
  if (surfaces?.length) payload.surfaces = surfaces

  const treatment = await createTreatment(props.patientId, payload)
  if (!treatment) return

  // In planning mode linked to a specific plan, attach the new Treatment as a
  // PlannedTreatmentItem so it shows up in the plan's list.
  if (isPlanningMode.value && props.planId) {
    await treatmentPlansApi.addItem(props.planId, { treatment_id: treatment.id })
  }

  undoStack.value.push({ treatmentId: treatment.id, type: treatment.clinical_type })

  toast.add({
    title: `${t(`odontogram.treatments.types.${treatment.clinical_type}`, treatment.clinical_type)} - ${t('odontogram.tooth')} ${toothNumber}`,
    description: t('odontogram.treatments.treatmentAdded'),
    color: 'success',
    actions: [{ label: t('common.undo'), onClick: handleUndo }]
  })

  emit('treatmentAdd', treatment)
  emit('treatmentsChanged')
  selectedTreatmentType.value = null
  selectedCatalogItemId.value = null
}

function handleSurfaceConfirm(surfaces: Surface[]) {
  if (selectedTooth.value && surfaces.length) {
    applyTreatment(selectedTooth.value, surfaces)
  }
  selectedTooth.value = null
}

async function handleUndo() {
  const lastAction = undoStack.value.pop()
  if (!lastAction) return
  await deleteTreatment(lastAction.treatmentId)
  emit('treatmentsChanged')
  toast.add({ title: t('common.undone'), color: 'neutral' })
}

function cancelClickToApplyMode() {
  selectedTreatmentType.value = null
  selectedCatalogItemId.value = null
  hoveredTooth.value = null
  resetMultiToothSelection()
}

// Global treatments are created inside TreatmentBar using its own useTreatments()
// instance, so the chart's local treatments[] doesn't see them — refetch so the
// globals strip and any parent listeners stay in sync.
async function handleGlobalTreatmentApplied(treatment: Treatment) {
  await fetchTreatments(props.patientId)
  emit('treatmentAdd', treatment)
  emit('treatmentsChanged')
}

// ============================================================================
// Treatment Editing
// ============================================================================

function handleEditTreatment(treatment: ToothTreatmentView) {
  editingTreatment.value = treatment
  showTreatmentEditModal.value = true
}

async function handleTreatmentUpdate(
  treatmentId: string,
  data: { status?: TreatmentStatus, notes?: string, surfaces?: Surface[] }
) {
  // useTreatments toasts on failure and returns null — keep the modal
  // open with the user's edits so nothing is lost and a retry works.
  const updated = await updateTreatment(treatmentId, data)
  if (!updated) return
  emit('treatmentsChanged')
  showTreatmentEditModal.value = false
  editingTreatment.value = null
}

// Deleting a treatment is destructive and has no undo endpoint — the
// edit modal's delete button opens a confirmation first (issue #101).
const showDeleteTreatmentConfirm = ref(false)
const deletingTreatment = ref(false)
const pendingDeleteTreatmentId = ref<string | null>(null)

const deleteTreatmentLabel = computed(() => {
  const tr = editingTreatment.value
  if (!tr) return ''
  return t(`odontogram.treatments.types.${tr.clinical_type}`, tr.clinical_type)
})

function handleTreatmentDelete(treatmentId: string) {
  pendingDeleteTreatmentId.value = treatmentId
  showDeleteTreatmentConfirm.value = true
}

async function confirmTreatmentDelete() {
  if (!pendingDeleteTreatmentId.value) return
  deletingTreatment.value = true
  try {
    // deleteTreatment toasts on failure and returns false — keep the edit
    // modal open so a retry works; only tear down on success.
    const ok = await deleteTreatment(pendingDeleteTreatmentId.value)
    showDeleteTreatmentConfirm.value = false
    pendingDeleteTreatmentId.value = null
    if (!ok) return
    emit('treatmentsChanged')
    showTreatmentEditModal.value = false
    editingTreatment.value = null
  } finally {
    deletingTreatment.value = false
  }
}

async function handleTreatmentPerform(treatmentId: string) {
  // Same contract: performTreatment toasts on failure and returns null —
  // keep the modal open instead of closing over a failed mutation.
  const updated = await performTreatment(treatmentId)
  if (!updated) return
  emit('treatmentPerform', treatmentId)
  emit('treatmentsChanged')
  showTreatmentEditModal.value = false
  editingTreatment.value = null
}

// ============================================================================
// Timeline & History
// ============================================================================

async function handleTimelineDateChange(date: string | null) {
  if (date === null) {
    returnToCurrentView()
  } else {
    await fetchOdontogramAtDate(props.patientId, date)
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

// Exposed so parents (PlanDetailView) can refresh the local treatments cache
// after mutations they own (remove item, complete item).
defineExpose({
  refetchTreatments: () => fetchTreatments(props.patientId)
})
</script>

<template>
  <div class="odontogram-chart">
    <!-- Header -->
    <div class="flex items-center justify-between mb-4">
      <div class="flex items-center gap-2">
        <h3 class="text-h1 text-default">
          {{ t('odontogram.title') }}
        </h3>
        <UBadge
          v-if="mode === 'view-only'"
          :label="t('odontogram.readOnly')"
          color="neutral"
          variant="subtle"
        />
        <UBadge
          v-if="mode === 'planning'"
          :label="t('odontogram.planning')"
          color="warning"
          variant="subtle"
        />
        <UBadge
          v-if="isClickToApplyMode"
          :label="multiToothConfig
            ? t(multiToothConfig.labelKey)
            : t(`odontogram.treatments.types.${selectedTreatmentType}`)"
          color="primary"
          variant="solid"
        />
      </div>

      <!-- Dentition toggle -->
      <SegmentedControl
        :model-value="dentitionMode"
        :options="[
          { value: 'permanent', label: t('odontogram.dentition.permanent') },
          { value: 'deciduous', label: t('odontogram.dentition.deciduous') }
        ]"
        @update:model-value="(v) => (dentitionMode = v as 'permanent' | 'deciduous')"
      />
    </div>

    <!-- Timeline Slider (only in standalone 'full' mode; HistoryMode renders its own) -->
    <TimelineSlider
      v-if="mode === 'full' && timelineDates.length > 1"
      :dates="timelineDates"
      :current-date="viewingDate"
      :disabled="timelineLoading"
      class="mb-4"
      @update:current-date="handleTimelineDateChange"
    />

    <!-- Loading -->
    <div
      v-if="loading || treatmentsLoading || timelineLoading"
      class="flex items-center justify-center py-16"
    >
      <UIcon
        name="i-lucide-loader-2"
        class="w-8 h-8 animate-spin text-subtle"
      />
    </div>

    <!-- Load error — never fall through to a fabricated healthy mouth. -->
    <UAlert
      v-else-if="error"
      icon="i-lucide-triangle-alert"
      color="error"
      variant="subtle"
      :title="t('odontogram.messages.loadError')"
      :actions="[{
        label: t('common.retry'),
        color: 'error',
        variant: 'soft',
        onClick: () => loadAll(props.patientId)
      }]"
    />

    <!-- Chart -->
    <div
      v-else
      class="flex flex-col gap-4"
    >
      <div class="odontogram-wrapper" dir="ltr">
        <div
          class="odontogram-grid bg-surface rounded-lg border border-default p-4"
          :class="{ 'cursor-crosshair': isClickToApplyMode }"
        >
          <!-- Upper arch -->
          <div
            class="mb-6 arch-container"
            :class="{ 'arch-halo': hoveredArch === 'upper' }"
          >
            <div class="text-caption text-subtle text-center mb-2">
              {{ t('odontogram.quadrants.upper') }}
            </div>
            <div class="flex justify-center gap-1 relative">
              <div
                v-if="upperMidlineBridgeStatus"
                class="midline-bridge upper"
                :class="'status-' + upperMidlineBridgeStatus"
              />
              <ToothQuadrant
                :teeth="teethLayout.upperRight"
                :get-tooth-data="getToothData"
                :get-treatments="getFilteredTreatments"
                :readonly="isReadonly"
                :selected-tooth="selectedTooth"
                :show-lateral="showLateral"
                :hovered-tooth="hoveredTooth"
                :highlighted-teeth="highlightedTeeth"
                :pending-treatment="pendingTreatment"
                :get-group-id="getToothGroupId"
                :get-group-status="getToothGroupStatus"
                :get-group-type="getToothGroupType"
                :multi-selected-teeth="multiToothSelection.teeth"
                @surface-click="handleSurfaceClick"
                @tooth-click="handleToothClick"
                @tooth-context-menu="handleToothContextMenu"
                @tooth-hover="hoveredTooth = $event"
                @edit-treatment="handleEditTreatment"
              />

              <div class="w-px bg-surface-sunken  mx-2" />

              <ToothQuadrant
                :teeth="teethLayout.upperLeft"
                :get-tooth-data="getToothData"
                :get-treatments="getFilteredTreatments"
                :readonly="isReadonly"
                :selected-tooth="selectedTooth"
                :show-lateral="showLateral"
                :hovered-tooth="hoveredTooth"
                :highlighted-teeth="highlightedTeeth"
                :pending-treatment="pendingTreatment"
                :get-group-id="getToothGroupId"
                :get-group-status="getToothGroupStatus"
                :get-group-type="getToothGroupType"
                :multi-selected-teeth="multiToothSelection.teeth"
                @surface-click="handleSurfaceClick"
                @tooth-click="handleToothClick"
                @tooth-context-menu="handleToothContextMenu"
                @tooth-hover="hoveredTooth = $event"
                @edit-treatment="handleEditTreatment"
              />
            </div>
          </div>

          <div class="h-px bg-surface-sunken my-4" />

          <!-- Lower arch -->
          <div
            class="arch-container"
            :class="{ 'arch-halo': hoveredArch === 'lower' }"
          >
            <div class="flex justify-center gap-1 relative">
              <div
                v-if="lowerMidlineBridgeStatus"
                class="midline-bridge lower"
                :class="'status-' + lowerMidlineBridgeStatus"
              />
              <ToothQuadrant
                :teeth="teethLayout.lowerRight"
                :get-tooth-data="getToothData"
                :get-treatments="getFilteredTreatments"
                :readonly="isReadonly"
                :selected-tooth="selectedTooth"
                :show-lateral="showLateral"
                :hovered-tooth="hoveredTooth"
                :highlighted-teeth="highlightedTeeth"
                :pending-treatment="pendingTreatment"
                :get-group-id="getToothGroupId"
                :get-group-status="getToothGroupStatus"
                :get-group-type="getToothGroupType"
                :multi-selected-teeth="multiToothSelection.teeth"
                @surface-click="handleSurfaceClick"
                @tooth-click="handleToothClick"
                @tooth-context-menu="handleToothContextMenu"
                @tooth-hover="hoveredTooth = $event"
                @edit-treatment="handleEditTreatment"
              />

              <div class="w-px bg-surface-sunken  mx-2" />

              <ToothQuadrant
                :teeth="teethLayout.lowerLeft"
                :get-tooth-data="getToothData"
                :get-treatments="getFilteredTreatments"
                :readonly="isReadonly"
                :selected-tooth="selectedTooth"
                :show-lateral="showLateral"
                :hovered-tooth="hoveredTooth"
                :highlighted-teeth="highlightedTeeth"
                :pending-treatment="pendingTreatment"
                :get-group-id="getToothGroupId"
                :get-group-status="getToothGroupStatus"
                :get-group-type="getToothGroupType"
                :multi-selected-teeth="multiToothSelection.teeth"
                @surface-click="handleSurfaceClick"
                @tooth-click="handleToothClick"
                @tooth-context-menu="handleToothContextMenu"
                @tooth-hover="hoveredTooth = $event"
                @edit-treatment="handleEditTreatment"
              />
            </div>
            <div class="text-caption text-subtle text-center mt-2">
              {{ t('odontogram.quadrants.lower') }}
            </div>
          </div>
        </div>
      </div>

      <!-- Globals strip (boca completa / arcada) — sits between the chart and the
           treatment bar so the dentist sees active global treatments without
           scrolling. -->
      <GlobalTreatmentsStrip
        :treatments="displayTreatments"
        :highlighted-ids="highlightedGlobalIds"
        @treatment-hover="handleGlobalHover"
        @arch-hover="handleArchHover"
      />

      <!-- Treatment Bar -->
      <TreatmentBar
        v-if="!isReadonly"
        v-model:selected-treatment="selectedTreatmentType"
        v-model:selected-catalog-item-id="selectedCatalogItemId"
        :selected-status="selectedTreatmentStatus"
        :selected-plan-id="planId"
        :plan-context-title="planTitle"
        :patient-id="patientId"
        :mode="treatmentBarMode"
        :disabled="isReadonly"
        @update:selected-status="selectedTreatmentStatus = $event"
        @treatment-select="selectedTreatmentType = $event"
        @treatment-applied="handleGlobalTreatmentApplied"
        @cancel="cancelClickToApplyMode"
      />

      <!-- Legend -->
      <OdontogramLegend />

      <!-- Treatment List (only in standalone 'full' mode; other modes' parents render their own) -->
      <TreatmentListSection
        v-if="mode === 'full'"
        :treatments="treatments"
      />

      <!-- History (only in standalone 'full' mode) -->
      <ChangeHistorySection
        v-if="mode === 'full'"
        :history="historyData"
        :treatments="treatments"
        :loading="historyLoading"
        @update:expanded="onHistoryExpanded"
      />
    </div>

    <!-- Surface selector popup -->
    <SurfaceSelectorPopup
      v-model:open="showSurfaceSelector"
      :tooth-number="selectedTooth || 0"
      :treatment-type="(selectedTreatmentType as ClinicalType) || 'filling_composite'"
      :status="selectedTreatmentStatus"
      @confirm="handleSurfaceConfirm"
      @cancel="selectedTooth = null"
    />

    <!-- Treatment edit modal -->
    <TreatmentEditModal
      v-model:open="showTreatmentEditModal"
      :treatment="editingTreatment"
      @update="handleTreatmentUpdate"
      @delete="handleTreatmentDelete"
      @perform="handleTreatmentPerform"
    />

    <!-- Delete-treatment confirmation (no undo endpoint exists) -->
    <UModal v-model:open="showDeleteTreatmentConfirm">
      <template #content>
        <div class="p-4 space-y-4">
          <h2 class="text-h3 text-default">
            {{ t('common.delete') }}
          </h2>
          <p class="text-caption text-subtle">
            {{ t('odontogram.treatments.deleteConfirm', {
              name: deleteTreatmentLabel,
              tooth: editingTreatment?.tooth_number ?? ''
            }) }}
          </p>
          <div class="flex justify-end gap-2">
            <UButton
              variant="ghost"
              @click="showDeleteTreatmentConfirm = false"
            >
              {{ t('actions.cancel') }}
            </UButton>
            <UButton
              color="error"
              :loading="deletingTreatment"
              @click="confirmTreatmentDelete"
            >
              {{ t('common.delete') }}
            </UButton>
          </div>
        </div>
      </template>
    </UModal>

    <!-- Multi-tooth confirmation popup -->
    <MultiToothConfirmPopup
      v-if="multiToothConfig"
      v-model:open="showMultiToothConfirm"
      :config="multiToothConfig"
      :teeth="multiToothSelection.teeth"
      :status="isDiagnosisMode ? 'existing' : isPlanningMode ? 'planned' : selectedTreatmentStatus"
      @confirm="confirmMultiToothSelection"
      @cancel="resetMultiToothSelection"
    />

    <!-- Free-mode selection summary bar (prompts user to confirm) -->
    <div
      v-if="multiToothConfig && multiToothConfig.selectionMode === 'free' && multiToothSelection.teeth.length > 0 && !showMultiToothConfirm"
      class="fixed bottom-4 left-1/2 -translate-x-1/2 z-40 flex items-center gap-3 rounded-lg border border-default bg-surface shadow-lg px-4 py-2"
    >
      <UIcon
        name="i-lucide-link"
        class="w-4 h-4 text-primary"
      />
      <span class="text-sm font-medium">
        {{ t(multiToothConfig.labelKey) }}
      </span>
      <UBadge
        color="primary"
        variant="subtle"
      >
        {{ multiToothSelection.teeth.length }}
      </UBadge>
      <UButton
        size="xs"
        variant="ghost"
        @click="resetMultiToothSelection"
      >
        {{ t('common.cancel') }}
      </UButton>
      <UButton
        size="xs"
        color="primary"
        :disabled="!canConfirmFreeSelection()"
        @click="requestMultiToothConfirm"
      >
        {{ t('common.confirm') }}
      </UButton>
    </div>
  </div>
</template>

<style scoped>
.odontogram-wrapper {
  container-type: inline-size;
  overflow: hidden;
}

/* Arch halo: highlights the upper or lower arch when the user hovers a global_arch
   chip in the globals strip. Paints a subtle blue outline around the full arch. */
.arch-container {
  position: relative;
  border-radius: 12px;
  transition: background 0.2s ease, box-shadow 0.2s ease;
}

.arch-container.arch-halo {
  background: rgba(59, 130, 246, 0.08);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.35), 0 4px 12px rgba(59, 130, 246, 0.15);
}

:root.dark .arch-container.arch-halo {
  background: rgba(59, 130, 246, 0.18);
}

.odontogram-grid {
  zoom: 1;
}

/* Container queries - respond to actual container width, not viewport */
@container (max-width: 1000px) {
  .odontogram-grid {
    zoom: 0.9;
  }
}

@container (max-width: 900px) {
  .odontogram-grid {
    zoom: 0.8;
  }
}

@container (max-width: 800px) {
  .odontogram-grid {
    zoom: 0.7;
  }
}

@container (max-width: 700px) {
  .odontogram-grid {
    zoom: 0.6;
  }
}

@container (max-width: 600px) {
  .odontogram-grid {
    zoom: 0.5;
  }
}

/* Midline bridge connector: absolute overlay so the vertical divider keeps
   its original 17px footprint and teeth columns stay aligned across arches. */
.midline-bridge {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  width: 56px;
  height: 12px;
  border-radius: 2px;
  background: #F59E0B;
  pointer-events: none;
  z-index: 1;
}

.midline-bridge.upper {
  top: 88px;
}

.midline-bridge.lower {
  top: 78px;
}

.midline-bridge.status-planned {
  background: repeating-linear-gradient(
    90deg,
    #F59E0B 0,
    #F59E0B 4px,
    transparent 4px,
    transparent 8px
  );
}

.midline-bridge.status-existing {
  background: #F59E0B;
}
</style>
