<script setup lang="ts">
import type { Arch, OdontogramTreatment, TreatmentStatus, TreatmentPlan } from '~~/app/types'
import { TREATMENT_ICONS, isSurfaceTreatment, resolveTreatmentIconKey } from './TreatmentIcons'
import {
  ATOMIC_MULTI_TOOTH_TYPES,
  MULTI_TOOTH_WRAPPER_BY_TYPE,
  TREATMENT_CATEGORIES,
  THERAPEUTIC_CATEGORIES,
  getAllowedStatusesForTreatment,
  getMultiToothConfig,
  getTreatmentColor,
  isMultiToothOnlyType,
  supportsBothModes,
  type TreatmentClinicalCategory
} from '~~/app/config/odontogramConstants'

export type TreatmentBarMode = 'diagnosis' | 'planning' | 'full'

/** Synthetic category key for whole-mouth / whole-arch treatments. Only surfaces
 *  in planning mode (never in diagnosis). */
const GLOBALS_CATEGORY = 'globals'

const props = withDefaults(defineProps<{
  /** Accepts both persisted TreatmentType values and UI-only multi-tooth keys (bridge, multiple_veneers...). */
  selectedTreatment?: string | null
  /** Catalog item id selected via the bar — enables price/duration/material snapshot. */
  selectedCatalogItemId?: string | null
  selectedStatus: TreatmentStatus
  selectedPlanId?: string | null
  patientId?: string
  treatmentPlans?: TreatmentPlan[]
  disabled?: boolean
  /** Mode determines which categories are shown and UI behavior */
  mode?: TreatmentBarMode
  /** When set (fixed-plan context), shows a"Adding to: {title}" banner instead of the plan selector. */
  planContextTitle?: string
}>(), {
  mode: 'full'
})

const emit = defineEmits<{
  'update:selectedTreatment': [treatment: string | null]
  'update:selectedCatalogItemId': [catalogItemId: string | null]
  'update:selectedStatus': [status: TreatmentStatus]
  'update:selectedPlanId': [planId: string | null]
  'treatmentSelect': [treatment: string]
  /** Fired after a global treatment is created and (optionally) added to the plan. */
  'treatmentApplied': [treatmentId: string]
  'createPlan': []
  'cancel': []
}>()

const { t, locale } = useI18n()

// Catalog integration - fetch treatments from catalog with fallback to constants
const treatmentCatalog = useTreatmentCatalog()

// Fetch treatments on mount (will use fallback if catalog is empty)
onMounted(async () => {
  if (!treatmentCatalog.initialized.value) {
    await treatmentCatalog.fetchTreatments()
  }
})

// Does the catalog have any global items? Drives visibility of the Globals tab.
const hasGlobalItems = computed(() =>
  treatmentCatalog.globalMouthItems.value.length > 0
  || treatmentCatalog.globalArchItems.value.length > 0
)

// Categories from catalog (with fallback to constants), filtered by mode
// NOTE: Must be defined before activeCategory watch that references it
const categories = computed(() => {
  // Always include all constant categories as base, then merge with catalog
  const constantCategories = TREATMENT_CATEGORIES.map(c => c.key)
  const catalogCategories = treatmentCatalog.clinicalCategories.value

  // Merge: use constant categories as base, ensuring all are present
  // Catalog may add extra categories but we always have the standard ones
  const allCategories = [...new Set([...constantCategories, ...catalogCategories])]

  // Diagnosis mode: show ALL categories (dentist needs to record existing treatments too)
  // Planning mode: show only therapeutic categories (no diagnostic conditions) + globals
  if (props.mode === 'planning') {
    const therapeutic = allCategories.filter(cat =>
      THERAPEUTIC_CATEGORIES.includes(cat as TreatmentClinicalCategory)
    )
    if (hasGlobalItems.value) therapeutic.push(GLOBALS_CATEGORY)
    return therapeutic
  }

  // 'full' and 'diagnosis' modes show all categories
  return allCategories
})

// Active category tab - default based on mode
const activeCategory = ref(props.mode === 'planning' ? 'restauradora' : 'diagnostico')

// Update active category when mode changes or if current category is not in filtered list
watch(() => props.mode, () => {
  if (!categories.value.includes(activeCategory.value)) {
    activeCategory.value = categories.value[0] || 'diagnostico'
  }
}, { immediate: true })

// All status options
const allStatusOptions: Array<{ value: TreatmentStatus, labelKey: string, color: string }> = [
  { value: 'existing', labelKey: 'odontogram.status.existing', color: 'neutral' },
  { value: 'planned', labelKey: 'odontogram.status.planned', color: 'error' }
]

// Get allowed statuses for a treatment (catalog-aware)
function getEffectiveAllowedStatuses(treatment: string): TreatmentStatus[] {
  // Check if treatment is diagnostic from catalog
  if (treatmentCatalog.treatmentIsDiagnostic(treatment)) {
    return ['existing']
  }
  // Fall back to constants
  return getAllowedStatusesForTreatment(treatment)
}

// Filtered status options based on selected treatment
const statusOptions = computed(() => {
  if (!props.selectedTreatment) {
    return allStatusOptions
  }
  const allowedStatuses = getEffectiveAllowedStatuses(props.selectedTreatment)
  return allStatusOptions.filter(opt => allowedStatuses.includes(opt.value))
})

// Status toggle only belongs in the free 'full' odontogram where the dentist
// may be logging existing or planned work. Diagnosis locks to 'existing',
// planning locks to 'planned' — showing a toggle there is misleading.
const showStatusToggle = computed(() => props.mode === 'full')

// Show diagnosis mode indicator
const isDiagnosisMode = computed(() => props.mode === 'diagnosis')

// Effective status — diagnosis locks to 'existing', planning locks to 'planned'.
const effectiveStatus = computed<TreatmentStatus>(() => {
  if (props.mode === 'diagnosis') return 'existing'
  if (props.mode === 'planning') return 'planned'
  return props.selectedStatus
})

// Atomic multi-tooth icon overlay shown on the catalog button (bridge, splint).
const ATOMIC_MULTI_ICONS: Record<string, string> = {
  bridge: 'i-lucide-link',
  splint: 'i-lucide-align-horizontal-distribute-center'
}

interface TreatmentBarItem {
  /** Unique key for the button (catalog item id, or odontogram type for fallback). */
  key: string
  /** Display label — catalog name when available, else i18n type label. */
  label: string
  /** Tooltip — label plus optional price-range hint when tiered pricing applies. */
  tooltip: string
  /** Backend clinical_type ('crown', 'bridge', ...). */
  odontogramType: string
  /** Catalog code is useful when a doctor searches by a short item identifier. */
  internalCode?: string
  /** Resolved icon key in TREATMENT_ICONS — may differ from odontogramType when a
   * catalog item has a variant icon (e.g. REST-BRIDGE-MARY → bridge_maryland). */
  iconKey: string
  /** Catalog item id, or null for the constants fallback. */
  catalogItemId: string | null
  /** True for atomic multi-tooth types (bridge, splint) — clicking enters multi-mode. */
  isAtomicMulti: boolean
  /** Icon name for atomic multi-tooth badge overlay. */
  atomicMultiIcon?: string
  /** True when the catalog item uses per-surface tiered pricing. */
  hasSurfacePricing: boolean
}

function formatSurfaceRangeLabel(
  surfacePrices: Record<string, number> | null | undefined
): string | null {
  if (!surfacePrices) return null
  const values = Object.values(surfacePrices)
    .map(v => (typeof v === 'string' ? Number(v) : v))
    .filter((v): v is number => typeof v === 'number' && Number.isFinite(v))
  if (values.length === 0) return null
  const min = Math.min(...values)
  const max = Math.max(...values)
  // Pricing-tier hint is purely numeric — full localized formatting
  // happens in <Money> elsewhere. We just want a compact range label.
  const fmt = (n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(2))
  return min === max ? fmt(min) : `${fmt(min)}–${fmt(max)}`
}

// One button per catalog item (no dedupe by type — Metal-cerámica vs Zirconio bridges
// have different prices/materials and must remain selectable as distinct catalog items).
// Pontic and bridge_abutment are filtered out (only valid as inner members of a bridge).
// In diagnosis-only mode (props.disabled) we still want to record existing work, but
// without the multi-tooth selection flow — currently the disabled prop blocks the whole
// bar so this branch is unused; left in case the prop semantics change.
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

function globalItemToBarItem(
  c: OdontogramTreatment,
  subGroup: 'mouth' | 'arch'
): TreatmentBarItem {
  // Unmapped global items (limpieza, primera visita...) have no odontogram
  // type — fall back to the neutral 'other' icon/color; labels come from
  // the catalog names, which real catalog items always carry.
  const oType = c.odontogram_treatment_type ?? 'other'
  const label = c.names[locale.value] || c.names.es || c.names.en || c.internal_code
  const price = c.default_price != null ? Number(c.default_price) : Number.NaN
  const tooltip = Number.isFinite(price)
    ? `${label}  •  ${Number.isInteger(price) ? String(price) : price.toFixed(2)}`
    : label
  return {
    key: c.id,
    label,
    tooltip,
    odontogramType: oType,
    internalCode: c.internal_code,
    iconKey: resolveTreatmentIconKey(oType, c.internal_code),
    catalogItemId: c.id,
    isAtomicMulti: false,
    atomicMultiIcon: subGroup === 'arch' ? 'i-lucide-layers-2' : 'i-lucide-scan-face',
    hasSurfacePricing: false
  }
}

const currentTreatments = computed<TreatmentBarItem[]>(() => {
  const catalogTreatments = treatmentCatalog.getTreatmentsForCategory(activeCategory.value)

  if (catalogTreatments.length > 0) {
    return catalogTreatments
      // Category-grouped items always carry a mapping (unmapped globals are
      // excluded from treatmentsByCategory); the null-check narrows the type.
      .filter(c => c.odontogram_treatment_type != null && !isMultiToothOnlyType(c.odontogram_treatment_type))
      .map((c) => {
        const oType = c.odontogram_treatment_type ?? 'other'
        const isAtomic = ATOMIC_MULTI_TOOTH_TYPES.has(oType)
        // Fallback items from useTreatmentCatalog use the treatment type as id;
        // only real catalog items (UUID ids) should flow into catalog_item_id.
        const isRealCatalogItem = UUID_RE.test(c.id)
        // Real catalog items carry localized names; fallback items have names
        // set to the raw type string, so translate via i18n instead.
        const label = isRealCatalogItem
          ? (c.names[locale.value] || c.names.es || c.names.en || oType)
          : t(`odontogram.treatments.types.${oType}`, oType)
        const rangeLabel = formatSurfaceRangeLabel(c.surface_prices)
        const tooltip = rangeLabel
          ? `${label}  •  ${t('odontogram.surfacePricingHint', { range: rangeLabel })}`
          : label
        return {
          key: c.id,
          label,
          tooltip,
          odontogramType: oType,
          internalCode: c.internal_code,
          iconKey: resolveTreatmentIconKey(oType, c.internal_code),
          catalogItemId: isRealCatalogItem ? c.id : null,
          isAtomicMulti: isAtomic,
          atomicMultiIcon: isAtomic ? ATOMIC_MULTI_ICONS[oType] : undefined,
          hasSurfacePricing: !!c.surface_prices && Object.keys(c.surface_prices).length > 0
        }
      })
  }

  // Constants fallback (catalog empty). One button per type, multi-tooth-only filtered.
  const fallback = TREATMENT_CATEGORIES.find(c => c.key === activeCategory.value)?.treatments || []
  return fallback
    .filter(type => !isMultiToothOnlyType(type))
    .map((type) => {
      const isAtomic = ATOMIC_MULTI_TOOTH_TYPES.has(type)
      const label = t(`odontogram.treatments.types.${type}`, type)
      return {
        key: type,
        label,
        tooltip: label,
        odontogramType: type,
        iconKey: type,
        catalogItemId: null,
        isAtomicMulti: isAtomic,
        atomicMultiIcon: isAtomic ? ATOMIC_MULTI_ICONS[type] : undefined,
        hasSurfacePricing: false
      }
    })
})

// ============================================================================
// Globals tab: grouped rendering ("Boca completa")
// ============================================================================

interface TreatmentBarGroup {
  key: string
  /** Localized subheader — null for the single anonymous group of regular tabs. */
  label: string | null
  items: TreatmentBarItem[]
}

// Fixed clinical ordering for the globals tab; unknown categories go last.
const GLOBAL_GROUP_ORDER = [
  'diagnostico', 'preventivo', 'periodoncia', 'restauradora',
  'ortodoncia', 'estetica', 'protesis'
]

const globalsFilter = ref('')
const treatmentsFilter = ref('')

const globalItemCount = computed(() =>
  treatmentCatalog.globalMouthItems.value.length + treatmentCatalog.globalArchItems.value.length
)

// Only worth showing a filter box once the list is long.
const showGlobalsFilter = computed(() =>
  activeCategory.value === GLOBALS_CATEGORY && globalItemCount.value > 12
)

const showTreatmentsFilter = computed(() =>
  activeCategory.value !== GLOBALS_CATEGORY && currentTreatments.value.length > 8
)

const filteredTreatments = computed(() => {
  const query = treatmentsFilter.value.trim().toLocaleLowerCase(locale.value)
  if (!query) return currentTreatments.value
  return currentTreatments.value.filter(item =>
    item.label.toLocaleLowerCase(locale.value).includes(query)
    || item.odontogramType.toLocaleLowerCase(locale.value).includes(query)
    || item.internalCode?.toLocaleLowerCase(locale.value).includes(query)
  )
})

function matchesGlobalsFilter(c: OdontogramTreatment): boolean {
  const query = globalsFilter.value.trim().toLowerCase()
  if (!query) return true
  const name = c.names[locale.value] || c.names.es || c.names.en || ''
  return name.toLowerCase().includes(query) || c.internal_code.toLowerCase().includes(query)
}

/** What the grid renders: one anonymous group for regular tabs; on the globals
 *  tab, items grouped by catalog category (mouth items before arch items). */
const treatmentGroups = computed<TreatmentBarGroup[]>(() => {
  if (activeCategory.value !== GLOBALS_CATEGORY) {
    return filteredTreatments.value.length
      ? [{ key: activeCategory.value, label: null, items: filteredTreatments.value }]
      : []
  }

  const groups = new Map<string, { label: string, mouth: TreatmentBarItem[], arch: TreatmentBarItem[] }>()
  const add = (c: OdontogramTreatment, subGroup: 'mouth' | 'arch') => {
    const key = c.category_key || 'otros'
    let group = groups.get(key)
    if (!group) {
      group = {
        label: c.category_names[locale.value] || c.category_names.es || c.category_names.en || key,
        mouth: [],
        arch: []
      }
      groups.set(key, group)
    }
    group[subGroup].push(globalItemToBarItem(c, subGroup))
  }
  treatmentCatalog.globalMouthItems.value.filter(matchesGlobalsFilter).forEach(c => add(c, 'mouth'))
  treatmentCatalog.globalArchItems.value.filter(matchesGlobalsFilter).forEach(c => add(c, 'arch'))

  const orderOf = (key: string) => {
    const idx = GLOBAL_GROUP_ORDER.indexOf(key)
    return idx === -1 ? GLOBAL_GROUP_ORDER.length : idx
  }
  return [...groups.entries()]
    .sort(([a], [b]) => orderOf(a) - orderOf(b) || a.localeCompare(b))
    .map(([key, g]) => ({ key, label: g.label, items: [...g.mouth, ...g.arch] }))
})

const globalsFilterHasNoResults = computed(() =>
  activeCategory.value === GLOBALS_CATEGORY
  && globalsFilter.value.trim() !== ''
  && treatmentGroups.value.length === 0
)
const treatmentsFilterHasNoResults = computed(() =>
  activeCategory.value !== GLOBALS_CATEGORY
  && treatmentsFilter.value.trim() !== ''
  && filteredTreatments.value.length === 0
)

// Leaving the globals tab resets the filter — stale queries would silently
// empty the tab on return.
watch(activeCategory, () => {
  globalsFilter.value = ''
  treatmentsFilter.value = ''
})

// ============================================================================
// Global treatments (boca completa / arcada)
// ============================================================================

const toast = useToast()
const { createGlobalTreatment } = useTreatments()
const treatmentPlansApi = useTreatmentPlans()

// Arch picker state: non-null while user must choose upper/lower for a global_arch.
const archPickerItem = ref<OdontogramTreatment | null>(null)
const applyingGlobal = ref(false)
let globalApplySequence = 0

watch([() => props.patientId, () => props.selectedPlanId], () => {
  globalApplySequence++
  applyingGlobal.value = false
  archPickerItem.value = null
})

function isGlobalItem(item: TreatmentBarItem): {
  catalog: OdontogramTreatment
  scope: 'global_mouth' | 'global_arch'
} | null {
  if (!item.catalogItemId) return null
  const mouth = treatmentCatalog.globalMouthItems.value.find(i => i.id === item.catalogItemId)
  if (mouth) return { catalog: mouth, scope: 'global_mouth' }
  const arch = treatmentCatalog.globalArchItems.value.find(i => i.id === item.catalogItemId)
  if (arch) return { catalog: arch, scope: 'global_arch' }
  return null
}

async function applyGlobalTreatment(
  catalogItemId: string,
  scope: 'global_mouth' | 'global_arch',
  arch?: Arch
) {
  if (applyingGlobal.value) return
  const patientId = props.patientId
  const planId = props.selectedPlanId
  if (!patientId) {
    console.error('TreatmentBar: patientId is required to apply a global treatment')
    return
  }
  const requestId = ++globalApplySequence
  applyingGlobal.value = true
  try {
    let treatmentId: string
    const catalogItem = scope === 'global_mouth'
      ? treatmentCatalog.globalMouthItems.value.find(item => item.id === catalogItemId)
      : treatmentCatalog.globalArchItems.value.find(item => item.id === catalogItemId)

    // Create the treatment and its plan item in one server transaction.
    if (planId) {
      const item = await treatmentPlansApi.addItem(planId, {
        create_treatment: {
          catalog_item_id: catalogItemId,
          scope,
          arch,
          status: 'planned'
        }
      })
      if (!item) return
      treatmentId = item.treatment_id
    } else {
      const created = await createGlobalTreatment(patientId, {
        catalogItemId,
        scope,
        arch,
        status: 'planned'
      })
      if (!created) return
      treatmentId = created.id
    }

    if (
      requestId !== globalApplySequence
      || patientId !== props.patientId
      || planId !== props.selectedPlanId
    ) return

    toast.add({
      title: t('odontogram.globals.applied', {
        name: catalogItem?.names?.[locale.value]
          || catalogItem?.names?.es
          || catalogItem?.names?.en
          || t('odontogram.treatments.types.other')
      }),
      color: 'success'
    })
    emit('treatmentApplied', treatmentId)
  } finally {
    if (requestId === globalApplySequence) applyingGlobal.value = false
  }
}

async function selectGlobalArch(arch: Arch) {
  const item = archPickerItem.value
  archPickerItem.value = null
  if (!item) return
  await applyGlobalTreatment(item.id, 'global_arch', arch)
}

function cancelArchPicker() {
  archPickerItem.value = null
}

function selectTreatment(item: TreatmentBarItem) {
  // Globals shortcut: apply directly (mouth) or prompt for arch (arch).
  const global = isGlobalItem(item)
  if (global) {
    if (global.scope === 'global_mouth') {
      void applyGlobalTreatment(global.catalog.id, 'global_mouth')
    } else {
      archPickerItem.value = global.catalog
    }
    return
  }
  return selectTreatmentRegular(item)
}

function selectTreatmentRegular(item: TreatmentBarItem) {
  // Check allowed statuses and auto-set if restricted
  const allowedStatuses = getEffectiveAllowedStatuses(item.odontogramType)
  const [fallbackStatus] = allowedStatuses
  if (fallbackStatus && !allowedStatuses.includes(props.selectedStatus)) {
    emit('update:selectedStatus', fallbackStatus)
  }

  // Atomic multi-tooth (bridge, splint) and regular treatments share the same flow:
  // emit the odontogram type. The wrapper-key swap for crown/veneer happens via
  // setMultiMode() once the user picks"Multiple teeth" from the toggle.
  emit('update:selectedCatalogItemId', item.catalogItemId)
  emit('update:selectedTreatment', item.odontogramType)
  emit('treatmentSelect', item.odontogramType)
}

// Derived from props so a parent-driven selectedTreatment change keeps the chip
// state in sync (e.g. on cancel + re-select, or SSR-restored state).
const selectedMultiMode = computed(() =>
  props.selectedTreatment !== null
  && props.selectedTreatment !== undefined
  && Object.values(MULTI_TOOTH_WRAPPER_BY_TYPE).includes(props.selectedTreatment)
)

function setMultiMode(multi: boolean) {
  const sel = props.selectedTreatment
  if (!sel) return
  if (multi) {
    const wrapperKey = MULTI_TOOTH_WRAPPER_BY_TYPE[sel]
    if (wrapperKey) {
      emit('update:selectedTreatment', wrapperKey)
      emit('treatmentSelect', wrapperKey)
    }
  } else {
    const cfg = getMultiToothConfig(sel)
    if (cfg) {
      emit('update:selectedTreatment', cfg.key)
      emit('treatmentSelect', cfg.key)
    }
  }
}

function selectStatus(status: TreatmentStatus) {
  emit('update:selectedStatus', status)
}

function handleCancel() {
  emit('update:selectedTreatment', null)
  emit('update:selectedCatalogItemId', null)
  emit('cancel')
}

// A button is"selected" when it matches the active selection. Catalog items must
// match by id (multiple buttons can share the same odontogram type — only the one
// the user clicked should highlight). Fallback items match by odontogram type.
function isSelected(item: TreatmentBarItem): boolean {
  if (item.catalogItemId !== null) {
    return props.selectedCatalogItemId === item.catalogItemId
  }
  return props.selectedTreatment === item.odontogramType
}

// Check if any treatment is selected
const hasActiveMode = computed(() => props.selectedTreatment !== null)

// Multi-tooth config for the current selection, if any
const activeMultiToothConfig = computed(() =>
  props.selectedTreatment ? getMultiToothConfig(props.selectedTreatment) : null
)

// Get category label - catalog aware
function getCategoryLabel(categoryKey: string): string {
  if (categoryKey === GLOBALS_CATEGORY) {
    return t('odontogram.globals.category')
  }
  const label = treatmentCatalog.getCategoryLabel(categoryKey)
  // If label looks like an i18n key, translate it
  if (label.startsWith('odontogram.')) {
    return t(label, categoryKey)
  }
  return label
}

// Plan selector - only visible when status is"planned" and not in diagnosis mode.
// Hidden when no `treatmentPlans` list is provided — caller is working in a fixed
// plan context (PlanDetailView) where switching plans makes no sense.
const showPlanSelector = computed(() => {
  if (props.mode === 'diagnosis') return false
  if (!props.treatmentPlans) return false
  return effectiveStatus.value === 'planned'
})

// Plan options for dropdown
const planOptions = computed(() => {
  const options: Array<{ value: string | null, label: string, icon?: string, isActive?: boolean }> = [
    { value: null, label: t('odontogram.noPlan'), icon: 'i-lucide-minus' }
  ]

  if (props.treatmentPlans) {
    for (const plan of props.treatmentPlans) {
      options.push({
        value: plan.id,
        label: plan.title || plan.plan_number,
        icon: plan.status === 'active' ? 'i-lucide-star' : 'i-lucide-file-text',
        isActive: plan.status === 'active'
      })
    }
  }

  return options
})

// Selected plan label
const selectedPlanLabel = computed(() => {
  if (!props.selectedPlanId) {
    return t('odontogram.noPlan')
  }
  const plan = props.treatmentPlans?.find(p => p.id === props.selectedPlanId)
  return plan?.title || plan?.plan_number || t('odontogram.noPlan')
})

function selectPlan(planId: string | null) {
  emit('update:selectedPlanId', planId)
}

function handleCreatePlan() {
  emit('createPlan')
}

// Nuxt UI renders a dropdown from `:items`; there are no
// `UDropdownMenuItem`/`Group`/`Separator` components, so the previous
// markup resolved to nothing and the menu came up empty (#459). Nested
// arrays are rendered as groups with a separator between them.
const planMenuItems = computed(() => [
  planOptions.value.map(option => ({
    // `checkbox` gives the selected plan the check indicator for free;
    // `onSelect` still fires, so selection stays a single handler.
    type: 'checkbox' as const,
    label: option.label,
    icon: option.icon,
    checked: props.selectedPlanId === option.value,
    ui: option.isActive ? { itemLeadingIcon: 'text-warning-accent' } : undefined,
    onSelect: () => selectPlan(option.value)
  })),
  [{
    label: t('odontogram.createNewPlan'),
    icon: 'i-lucide-plus',
    color: 'primary' as const,
    onSelect: () => handleCreatePlan()
  }]
])
</script>

<template>
  <div
    class="treatment-bar"
    :class="{ disabled }"
  >
    <!-- Fixed-plan context banner: shown when adding treatments inside a plan detail view. -->
    <div
      v-if="planContextTitle && mode === 'planning'"
      class="plan-context-banner"
    >
      <UIcon
        name="i-lucide-clipboard-list"
        class="w-4 h-4"
      />
      <span class="plan-context-label">{{ t('clinical.plans.addingToPlan') }}:</span>
      <span class="plan-context-title">{{ planContextTitle }}</span>
    </div>

    <!-- Top row: Status + Categories + Instructions -->
    <div class="top-row">
      <!-- Diagnosis Mode Indicator -->
      <div
        v-if="isDiagnosisMode"
        class="diagnosis-mode-indicator"
      >
        <UIcon
          name="i-lucide-stethoscope"
          class="w-4 h-4"
        />
        <span class="diagnosis-label">{{ t('odontogram.diagnosisMode') }}</span>
      </div>

      <!-- Status Toggle (hidden in diagnosis mode) -->
      <div
        v-else-if="showStatusToggle"
        class="status-toggle"
      >
        <button
          v-for="option in statusOptions"
          :key="option.value"
          type="button"
          class="status-btn"
          :aria-pressed="effectiveStatus === option.value"
          :class="{
            selected: effectiveStatus === option.value,
            [`status-${option.color}`]: true
          }"
          @click="selectStatus(option.value)"
        >
          <span class="status-dot" />
          <span class="status-label">{{ t(option.labelKey) }}</span>
        </button>
      </div>

      <!-- Plan Selector (only when status is"planned") -->
      <Transition
        enter-active-class="transition-all duration-200 ease-out"
        enter-from-class="opacity-0 scale-95"
        enter-to-class="opacity-100 scale-100"
        leave-active-class="transition-all duration-150 ease-in"
        leave-from-class="opacity-100 scale-100"
        leave-to-class="opacity-0 scale-95"
      >
        <div
          v-if="showPlanSelector"
          class="plan-selector"
        >
          <span class="plan-selector-label">{{ t('odontogram.addToPlan') }}:</span>
          <UDropdownMenu :items="planMenuItems">
            <UButton
              variant="soft"
              color="neutral"
              size="sm"
              class="plan-dropdown-trigger"
              trailing-icon="i-lucide-chevron-down"
            >
              <UIcon
                v-if="selectedPlanId"
                name="i-lucide-file-text"
                class="w-3.5 h-3.5"
              />
              <span class="truncate max-w-[120px]">{{ selectedPlanLabel }}</span>
            </UButton>
          </UDropdownMenu>
        </div>
      </Transition>

      <!-- Divider -->
      <div class="divider" />

      <!-- Category Tabs -->
      <div class="category-tabs">
        <button
          v-for="categoryKey in categories"
          :key="categoryKey"
          type="button"
          class="category-tab"
          :aria-pressed="activeCategory === categoryKey"
          :class="{ active: activeCategory === categoryKey }"
          @click="activeCategory = categoryKey"
        >
          {{ getCategoryLabel(categoryKey) }}
        </button>
      </div>

      <!-- Spacer -->
      <div class="spacer" />

      <!-- Cancel button (when treatment or position action is selected) -->
      <div
        v-if="hasActiveMode"
        class="cancel-section"
      >
        <UButton
          color="neutral"
          variant="ghost"
          size="sm"
          icon="i-lucide-x"
          @click="handleCancel"
        >
          {{ t('common.cancel') }}
        </UButton>
      </div>

      <!-- Instructions + mode toggle -->
      <div
        class="instructions"
        :class="{ 'multi-tooth-hint': activeMultiToothConfig }"
      >
        <template v-if="activeMultiToothConfig">
          <UIcon
            name="i-lucide-link"
            class="w-4 h-4"
          />
          <span>
            {{ activeMultiToothConfig.selectionMode === 'range'
              ? t('odontogram.multiTooth.hints.range')
              : t('odontogram.multiTooth.hints.free') }}
          </span>
        </template>
        <template v-else-if="hasActiveMode">
          <UIcon
            name="i-lucide-mouse-pointer-click"
            class="w-4 h-4"
          />
          <span>{{ t('odontogram.instructions.clickTooth') }}</span>
        </template>
        <template v-else>
          <UIcon
            name="i-lucide-hand-pointer"
            class="w-4 h-4"
          />
          <span>{{ t('odontogram.instructions.selectTreatment') }}</span>
        </template>
      </div>
    </div>

    <!-- Arch picker: shown when user selected a global_arch item and must pick arch. -->
    <Transition
      enter-active-class="transition-all duration-200 ease-out"
      enter-from-class="opacity-0 -translate-y-2"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition-all duration-150 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="archPickerItem"
        class="arch-picker"
      >
        <div class="arch-picker-label">
          {{ t('odontogram.globals.archPickerTitle', {
            name: archPickerItem.names[locale] || archPickerItem.names.es || archPickerItem.internal_code
          }) }}
        </div>
        <div class="arch-picker-buttons">
          <button
            type="button"
            class="arch-btn"
            :disabled="applyingGlobal"
            @click="selectGlobalArch('upper')"
          >
            <UIcon
              name="i-lucide-arrow-up"
              class="w-4 h-4"
            />
            <span>{{ t('odontogram.globals.upperArch') }}</span>
          </button>
          <button
            type="button"
            class="arch-btn"
            :disabled="applyingGlobal"
            @click="selectGlobalArch('lower')"
          >
            <UIcon
              name="i-lucide-arrow-down"
              class="w-4 h-4"
            />
            <span>{{ t('odontogram.globals.lowerArch') }}</span>
          </button>
          <button
            type="button"
            class="arch-btn arch-btn-cancel"
            :disabled="applyingGlobal"
            @click="cancelArchPicker"
          >
            <UIcon
              name="i-lucide-x"
              class="w-4 h-4"
            />
            <span>{{ t('common.cancel') }}</span>
          </button>
        </div>
      </div>
    </Transition>

    <!-- Globals filter: only for the long "Boca completa" list. -->
    <div
      v-if="showGlobalsFilter"
      class="globals-filter"
    >
      <UInput
        v-model="globalsFilter"
        icon="i-lucide-search"
        size="sm"
        :placeholder="t('odontogram.globals.searchPlaceholder')"
        :aria-label="t('odontogram.globals.searchPlaceholder')"
        class="globals-filter-input"
      />
    </div>

    <div
      v-if="showTreatmentsFilter"
      class="globals-filter"
    >
      <UInput
        v-model="treatmentsFilter"
        icon="i-lucide-search"
        size="sm"
        :placeholder="t('odontogram.globals.searchPlaceholder')"
        :aria-label="t('odontogram.globals.searchPlaceholder')"
        class="globals-filter-input"
      />
    </div>

    <!-- Bottom row: Treatment Icons Grid (one button per catalog item).
         Regular tabs render a single anonymous group; the globals tab renders
         one grid per clinical category with a localized subheader. -->
    <div class="treatment-groups">
      <section
        v-for="group in treatmentGroups"
        :key="group.key"
        class="treatment-group"
      >
        <h4
          v-if="group.label"
          class="treatment-group-label"
        >
          {{ group.label }}
        </h4>
        <div class="treatment-grid">
          <div
            v-for="item in group.items"
            :key="item.key"
            class="treatment-cell"
          >
            <button
              type="button"
              class="treatment-btn"
              :disabled="disabled || applyingGlobal"
              :aria-pressed="isSelected(item)"
              :aria-label="item.label"
              :class="{
                'selected': isSelected(item),
                'is-surface': isSurfaceTreatment(item.odontogramType),
                'atomic-multi-btn': item.isAtomicMulti,
                'has-mode-selector': isSelected(item) && supportsBothModes(item.odontogramType),
                'has-surface-pricing': item.hasSurfacePricing
              }"
              :title="item.tooltip"
              @click="selectTreatment(item)"
            >
              <div
                class="treatment-icon"
                :style="{ color: getTreatmentColor(item.odontogramType) }"
              >
                <svg
                  viewBox="0 0 24 24"
                  width="24"
                  height="24"
                  v-html="TREATMENT_ICONS[item.iconKey] || TREATMENT_ICONS[item.odontogramType]"
                />
              </div>
              <span class="treatment-label">{{ item.label }}</span>
              <UIcon
                v-if="item.isAtomicMulti"
                :name="item.atomicMultiIcon!"
                class="multi-tooth-badge"
              />
              <UIcon
                v-else-if="supportsBothModes(item.odontogramType)"
                name="i-lucide-layers"
                class="multi-tooth-badge multi-tooth-badge-hint"
              />
            </button>

            <!-- Inline mode selector: anchored directly under selected crown/veneer.
             Replaces the disconnected mode-toggle that previously sat in the
             top instructions row. -->
            <div
              v-if="isSelected(item) && supportsBothModes(item.odontogramType)"
              class="mode-selector-inline"
            >
              <button
                type="button"
                class="mode-chip"
                :aria-pressed="!selectedMultiMode"
                :class="{ active: !selectedMultiMode }"
                @click.stop="setMultiMode(false)"
              >
                <UIcon
                  name="i-lucide-circle-dot"
                  class="w-3 h-3"
                />
                <span>{{ t('odontogram.oneTooth') }}</span>
              </button>
              <button
                type="button"
                class="mode-chip"
                :aria-pressed="selectedMultiMode"
                :class="{ active: selectedMultiMode }"
                @click.stop="setMultiMode(true)"
              >
                <UIcon
                  name="i-lucide-link"
                  class="w-3 h-3"
                />
                <span>{{ t('odontogram.multipleTeeth') }}</span>
              </button>
            </div>
          </div>
        </div>
      </section>

      <div
        v-if="globalsFilterHasNoResults || treatmentsFilterHasNoResults"
        class="globals-no-results"
      >
        {{ t('common.noResults') }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.treatment-bar {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
  background-color: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xs);
}

:root.dark .treatment-bar {
  background-color: var(--color-surface);
  border-color: var(--color-border);
}

.treatment-bar.disabled {
  opacity: 0.5;
  pointer-events: none;
}

/* Fixed-plan context banner */
.plan-context-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: linear-gradient(90deg, #FEF3C7 0%, #FDE68A 100%);
  border: 1px solid #FCD34D;
  border-radius: 8px;
  color: #78350F;
  font-size: 13px;
}

:root.dark .plan-context-banner {
  background: linear-gradient(90deg, rgba(251, 191, 36, 0.12) 0%, rgba(251, 191, 36, 0.22) 100%);
  border-color: rgba(251, 191, 36, 0.4);
  color: #FCD34D;
}

.plan-context-label {
  font-weight: 500;
  opacity: 0.8;
}

.plan-context-title {
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Top row */
.top-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

/* Diagnosis Mode Indicator */
.diagnosis-mode-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: #DBEAFE;
  border: 1px solid #93C5FD;
  border-radius: 8px;
  color: #1D4ED8;
}

:root.dark .diagnosis-mode-indicator {
  background: rgba(59, 130, 246, 0.15);
  border-color: rgba(59, 130, 246, 0.4);
  color: #60A5FA;
}

.diagnosis-label {
  font-size: 13px;
  font-weight: 500;
}

/* Status Toggle */
.status-toggle {
  display: flex;
  gap: 4px;
  background: #E4E4E7;
  padding: 3px;
  border-radius: 8px;
}

:root.dark .status-toggle {
  background: #3F3F46;
}

.status-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  min-height: 44px;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.15s ease;
  background: transparent;
  color: #71717A;
}

.status-btn:hover {
  background: rgba(255, 255, 255, 0.5);
}

:root.dark .status-btn:hover {
  background: rgba(0, 0, 0, 0.2);
}

.status-btn.selected {
  background: white;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

:root.dark .status-btn.selected {
  background: #27272A;
}

.status-btn.selected.status-red {
  color: #DC2626;
}

.status-btn.selected.status-gray {
  color: #52525B;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentColor;
}

.status-label {
  display: none;
}

@media (min-width: 768px) {
  .status-label {
    display: inline;
  }
}

/* Plan Selector */
.plan-selector {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  background: #FEF3C7;
  border: 1px solid #FDE68A;
  border-radius: 8px;
}

:root.dark .plan-selector {
  background: rgba(251, 191, 36, 0.1);
  border-color: rgba(251, 191, 36, 0.3);
}

.plan-selector-label {
  font-size: 12px;
  font-weight: 500;
  color: #92400E;
  white-space: nowrap;
}

:root.dark .plan-selector-label {
  color: #FCD34D;
}

.plan-dropdown-trigger {
  min-width: 0;
}

/* Divider */
.divider {
  width: 1px;
  height: 32px;
  background: #E4E4E7;
}

:root.dark .divider {
  background: #3F3F46;
}

/* Category Tabs — calm segmented pattern (DESIGN §6) */
.category-tabs {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  padding: 4px;
  background: var(--color-surface-muted);
  border-radius: var(--radius-md);
}

.category-tab {
  min-height: 40px;
  padding: 8px 12px;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-muted);
  border-radius: calc(var(--radius-md) - 2px);
  transition: background-color 150ms var(--motion-ease), color 150ms var(--motion-ease);
}

.category-tab:hover:not(.active) {
  color: var(--color-text);
}

.category-tab.active {
  background: var(--color-surface);
  color: var(--color-text);
  box-shadow: var(--shadow-xs);
}

/* Spacer */
.spacer {
  flex: 1;
}

/* Cancel Section */
.cancel-section {
  flex-shrink: 0;
}

/* Instructions */
.instructions {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--color-text-muted);
  flex-shrink: 0;
  padding: 6px 12px;
  background: var(--color-surface-muted);
  border-radius: var(--radius-md);
}

.instructions.multi-tooth-hint {
  background: var(--color-info-soft);
  color: var(--color-info-text);
  font-weight: 500;
}

/* Treatment Grid - Second row.
   CSS grid: auto-fill columns with a sensible min width let long names breathe
   across 2-3 lines, while grid's row-stretch keeps every button in the same row
   at equal height regardless of label length. */
.treatment-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
  gap: 8px;
  align-items: stretch;
}

.treatment-cell {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  position: relative;
}

.treatment-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  gap: 5px;
  padding: 9px 7px;
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
  background: var(--color-surface);
  transition: background-color 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
  width: 100%;
  height: 100%;
  min-height: 82px;
  cursor: pointer;
  touch-action: manipulation;
}

.treatment-btn.has-mode-selector {
  border-bottom-left-radius: 0;
  border-bottom-right-radius: 0;
}

:root.dark .treatment-btn {
  background: #27272A;
}

.treatment-btn:hover {
  border-color: var(--color-primary-accent);
  box-shadow: var(--shadow-xs);
}

.treatment-btn.selected {
  border-color: var(--color-primary-accent);
  background: var(--color-primary-soft);
  box-shadow: 0 0 0 2px color-mix(in oklab, var(--color-primary-accent) 24%, transparent);
}

:root.dark .treatment-btn.selected {
  background: var(--color-primary-soft);
}

.treatment-btn:focus-visible,
.mode-chip:focus-visible,
.category-tab:focus-visible {
  outline: 3px solid color-mix(in oklab, var(--color-primary-accent) 42%, transparent);
  outline-offset: 2px;
}

.treatment-btn.is-surface::after {
  content: '';
  position: absolute;
  top: 4px;
  right: 4px;
  width: 6px;
  height: 6px;
  background: #06B6D4;
  border-radius: 50%;
}

.treatment-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
}

.treatment-icon svg {
  width: 22px;
  height: 22px;
}

.treatment-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text);
  text-align: center;
  line-height: 1.35;
  word-break: break-word;
  overflow-wrap: anywhere;
  hyphens: auto;
  width: 100%;
}

:root.dark .treatment-label {
  color: var(--color-text);
}

@media (max-width: 640px) {
  .treatment-bar {
    gap: 12px;
    padding: 12px;
  }

  .top-row {
    align-items: center;
    gap: 8px;
  }

  .divider,
  .spacer {
    display: none;
  }

  .diagnosis-mode-indicator,
  .status-toggle {
    order: 1;
  }

  .plan-selector {
    order: 2;
    max-width: 100%;
  }

  .cancel-section {
    order: 3;
    margin-inline-start: auto;
  }

  .category-tabs {
    order: 4;
    width: 100%;
    flex-wrap: nowrap;
    overflow-x: auto;
    overscroll-behavior-inline: contain;
  }

  .category-tab {
    flex: 0 0 auto;
    min-height: 44px;
  }

  .instructions {
    order: 5;
    width: 100%;
    min-height: 44px;
    font-size: 13px;
  }

  .treatment-grid {
    grid-template-columns: repeat(auto-fill, minmax(min(100%, 92px), 1fr));
    gap: 7px;
  }

  .treatment-btn {
    min-height: 76px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .treatment-btn,
  .category-tab {
    transition: none;
  }
}

/* Atomic multi-tooth catalog buttons (bridge, splint) — distinguished by a small
   link badge in the top-right corner. */
.treatment-btn {
  position: relative;
}

.multi-tooth-badge {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 12px;
  height: 12px;
  color: #3B82F6;
  background: #DBEAFE;
  border-radius: 4px;
  padding: 1px;
}

:root.dark .multi-tooth-badge {
  background: rgba(59, 130, 246, 0.2);
  color: #60A5FA;
}

/* Multi-tooth hint badge (subtle layers icon) on dual-mode catalog buttons (crown,
   veneer) — signals that clicking opens mode chips below. */
.multi-tooth-badge-hint {
  color: #A1A1AA;
  background: #F4F4F5;
}

:root.dark .multi-tooth-badge-hint {
  color: #71717A;
  background: #27272A;
}

.treatment-btn.selected .multi-tooth-badge-hint {
  color: #3B82F6;
  background: #DBEAFE;
}

/* Inline mode selector — anchored directly under the selected crown/veneer button.
   Stacks two full-width chips vertically so labels never overflow the cell's
   narrow width. Shares the button's border on the seam so the relationship is
   visually unambiguous. */
.mode-selector-inline {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 3px;
  background: #EFF6FF;
  border: 2px solid #3B82F6;
  border-top: none;
  border-bottom-left-radius: 8px;
  border-bottom-right-radius: 8px;
  box-shadow: 0 8px 18px -4px rgba(59, 130, 246, 0.35), 0 2px 4px rgba(0, 0, 0, 0.05);
  animation: mode-selector-reveal 0.18s ease-out;
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  z-index: 20;
}

:root.dark .mode-selector-inline {
  background: #172554;
  box-shadow: 0 8px 18px -4px rgba(0, 0, 0, 0.5), 0 2px 4px rgba(0, 0, 0, 0.3);
}

@keyframes mode-selector-reveal {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: translateY(0); }
}

.mode-chip {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  padding: 5px 6px;
  font-size: 10.5px;
  font-weight: 500;
  color: #1D4ED8;
  border-radius: 4px;
  transition: background 0.15s ease, color 0.15s ease, box-shadow 0.15s ease;
  cursor: pointer;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  width: 100%;
}

.mode-chip > span {
  overflow: hidden;
  text-overflow: ellipsis;
}

:root.dark .mode-chip {
  color: #93C5FD;
}

.mode-chip:hover {
  background: rgba(255, 255, 255, 0.65);
}

:root.dark .mode-chip:hover {
  background: rgba(255, 255, 255, 0.08);
}

.mode-chip.active {
  background: white;
  color: #1E40AF;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.12);
}

:root.dark .mode-chip.active {
  background: #1E3A8A;
  color: #DBEAFE;
}

/* Arch picker */
.arch-picker {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px 12px;
  background: #EFF6FF;
  border: 2px solid #3B82F6;
  border-radius: 8px;
}

:root.dark .arch-picker {
  background: rgba(59, 130, 246, 0.1);
  border-color: rgba(59, 130, 246, 0.5);
}

.arch-picker-label {
  font-size: 13px;
  font-weight: 500;
  color: #1D4ED8;
}

:root.dark .arch-picker-label {
  color: #93C5FD;
}

.arch-picker-buttons {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.arch-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  font-size: 13px;
  font-weight: 600;
  color: #1E3A8A;
  background: white;
  border: 1px solid #93C5FD;
  border-radius: 6px;
  transition: all 0.15s ease;
  cursor: pointer;
  flex: 1;
  min-width: 120px;
  justify-content: center;
}

.arch-btn:hover:not(:disabled) {
  background: #DBEAFE;
  border-color: #3B82F6;
  transform: translateY(-1px);
  box-shadow: 0 2px 6px rgba(59, 130, 246, 0.2);
}

.arch-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

:root.dark .arch-btn {
  background: #1E293B;
  color: #BFDBFE;
  border-color: rgba(59, 130, 246, 0.4);
}

.arch-btn-cancel {
  background: transparent;
  color: #71717A;
  border-color: #D4D4D8;
  flex: 0 0 auto;
  min-width: 90px;
}

.arch-btn-cancel:hover:not(:disabled) {
  background: #F4F4F5;
}

:root.dark .arch-btn-cancel {
  color: #A1A1AA;
  border-color: #52525B;
}

:root.dark .arch-btn-cancel:hover:not(:disabled) {
  background: #27272A;
}

/* Grouped grids (globals tab) */
.treatment-groups {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.treatment-group-label {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-text-muted);
  margin-bottom: 6px;
}

.globals-filter {
  display: flex;
}

.globals-filter-input {
  width: 100%;
  max-width: 320px;
}

.globals-no-results {
  padding: 12px;
  font-size: 13px;
  color: var(--color-text-muted);
  text-align: center;
}

/* Responsive */
@media (max-width: 640px) {
  .top-row {
    flex-direction: column;
    align-items: stretch;
  }

  .divider {
    width: 100%;
    height: 1px;
  }

  .category-tabs {
    justify-content: center;
  }

  .spacer {
    display: none;
  }

  .cancel-section,
  .instructions {
    justify-content: center;
  }

  .treatment-grid {
    justify-content: center;
  }
}
</style>
