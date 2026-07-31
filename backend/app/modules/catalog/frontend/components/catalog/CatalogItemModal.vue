<script setup lang="ts">
import type {
  CatalogItemSessionInput,
  TreatmentCatalogCategory,
  TreatmentCatalogItem,
  TreatmentCatalogItemUpdate,
  TreatmentCatalogItemCreate
} from '~~/app/types'
import {
  ALL_TREATMENT_TYPES,
  TREATMENT_CATEGORIES,
  VISUALIZATION_RULES,
  isSurfaceTreatment
} from '~~/app/config/odontogramConstants'

const props = defineProps<{
  item: TreatmentCatalogItem | null
  categories: TreatmentCatalogCategory[]
  loading: boolean
}>()

const open = defineModel<boolean>('open', { default: false })
const emit = defineEmits<{
  save: [data: TreatmentCatalogItemUpdate]
  create: [data: TreatmentCatalogItemCreate]
}>()

const { t, locale } = useI18n()
const catalog = useCatalog()

// VAT Types
const {
  vatTypeOptions,
  defaultVatType,
  fetchVatTypes
} = useVatTypes()

onMounted(() => {
  fetchVatTypes()
})

const isCreateMode = computed(() => !props.item)
const isSystem = computed(() => !isCreateMode.value && props.item?.is_system)

// Tabs
type TabId = 'general' | 'pricing' | 'scheduling' | 'clinical'
const activeTab = ref<TabId>('general')
const tabs = computed(() => [
  { id: 'general' as TabId, label: t('catalog.tabs.general'), icon: 'i-lucide-info' },
  { id: 'pricing' as TabId, label: t('catalog.tabs.pricing'), icon: 'i-lucide-euro' },
  { id: 'scheduling' as TabId, label: t('catalog.tabs.scheduling'), icon: 'i-lucide-clock' },
  { id: 'clinical' as TabId, label: t('catalog.tabs.clinical'), icon: 'i-lucide-stethoscope' }
])

// Reset to first tab when modal opens
watch(open, (v) => {
  if (v) activeTab.value = 'general'
})

// Form state
const formData = ref<TreatmentCatalogItemUpdate>({})

const itemName = computed({
  get: () => formData.value.names?.[locale.value] || '',
  set: (value: string) => {
    if (!formData.value.names) {
      formData.value.names = {}
    }
    formData.value.names[locale.value] = value
  }
})

// Odontogram mapping
const odontogramType = ref<string | undefined>(undefined)
const clinicalCategory = ref<string | undefined>(undefined)

// Sessions
interface SessionRow {
  sequence?: number
  label: string
  default_price: number
}
const sessionsEnabled = ref(false)
const sessions = ref<SessionRow[]>([])

function sessionsToPayload(): CatalogItemSessionInput[] {
  return sessions.value.map((s, idx) => ({
    sequence: idx + 1,
    labels: { [locale.value]: s.label },
    default_price: Number(s.default_price) || 0
  }))
}

function addSession() {
  sessions.value.push({ label: '', default_price: 0 })
}

function removeSession(idx: number) {
  sessions.value.splice(idx, 1)
}

const sessionsSum = computed(() =>
  sessions.value.reduce((acc, s) => acc + (Number(s.default_price) || 0), 0)
)

const sessionsSumMatches = computed(() => {
  const total = Number(formData.value.default_price) || 0
  return Math.abs(sessionsSum.value - total) <= 0.01
})

const sessionsProgress = computed(() => {
  const total = Number(formData.value.default_price) || 0
  if (total <= 0) return 0
  return Math.min(100, Math.max(0, (sessionsSum.value / total) * 100))
})

// Populate form
watch(
  () => props.item,
  (newItem) => {
    if (newItem) {
      formData.value = {
        internal_code: newItem.internal_code,
        category_id: newItem.category_id,
        names: { ...newItem.names },
        descriptions: newItem.descriptions ? { ...newItem.descriptions } : undefined,
        default_price: newItem.default_price,
        cost_price: newItem.cost_price,
        pricing_strategy: newItem.pricing_strategy || 'flat',
        pricing_config: newItem.pricing_config ?? null,
        surface_prices: newItem.surface_prices ? { ...newItem.surface_prices } : null,
        default_duration_minutes: newItem.default_duration_minutes,
        requires_appointment: newItem.requires_appointment,
        vat_type_id: newItem.vat_type_id,
        treatment_scope: newItem.treatment_scope,
        is_diagnostic: newItem.is_diagnostic,
        requires_surfaces: newItem.requires_surfaces,
        material_notes: newItem.material_notes,
        is_active: newItem.is_active
      }
      if (newItem.odontogram_mapping) {
        odontogramType.value = newItem.odontogram_mapping.odontogram_treatment_type
        clinicalCategory.value = newItem.odontogram_mapping.clinical_category
      } else {
        odontogramType.value = undefined
        clinicalCategory.value = undefined
      }
      if (newItem.sessions && newItem.sessions.length > 0) {
        sessionsEnabled.value = true
        sessions.value = newItem.sessions
          .slice()
          .sort((a, b) => a.sequence - b.sequence)
          .map(s => ({
            sequence: s.sequence,
            label: s.labels?.[locale.value] || s.labels?.es || s.labels?.en || '',
            default_price: Number(s.default_price)
          }))
      } else {
        sessionsEnabled.value = false
        sessions.value = []
      }
    } else {
      formData.value = {
        internal_code: '',
        category_id: props.categories[0]?.id,
        names: { [locale.value]: '' },
        default_price: 0,
        cost_price: 0,
        pricing_strategy: 'flat',
        pricing_config: null,
        surface_prices: null,
        default_duration_minutes: 30,
        requires_appointment: true,
        vat_type_id: defaultVatType.value?.id,
        treatment_scope: 'tooth',
        is_diagnostic: false,
        requires_surfaces: false,
        is_active: true
      }
      odontogramType.value = undefined
      clinicalCategory.value = undefined
      sessionsEnabled.value = false
      sessions.value = []
    }
  },
  { immediate: true }
)

watch(sessionsEnabled, (enabled) => {
  if (!enabled) {
    sessions.value = []
  } else if (sessions.value.length === 0) {
    addSession()
  }
})

// Scope options with icons
const scopeOptionsVisual = computed(() => [
  { value: 'tooth', label: t('catalog.scopeTypes.tooth'), icon: 'i-lucide-circle-dot' },
  { value: 'multi_tooth', label: t('catalog.scopeTypes.multi_tooth'), icon: 'i-lucide-grip' },
  { value: 'global_arch', label: t('catalog.scopeTypes.global_arch'), icon: 'i-lucide-rectangle-horizontal' },
  { value: 'global_mouth', label: t('catalog.scopeTypes.global_mouth'), icon: 'i-lucide-scan-face' }
])

// Pricing strategy with icons
const strategyOptionsVisual = computed(() => [
  { value: 'flat', label: t('catalog.pricingStrategy.flat'), icon: 'i-lucide-equal' },
  { value: 'per_tooth', label: t('catalog.pricingStrategy.per_tooth'), icon: 'i-lucide-x' },
  { value: 'per_surface', label: t('catalog.pricingStrategy.per_surface'), icon: 'i-lucide-layers' },
  { value: 'per_role', label: t('catalog.pricingStrategy.per_role'), icon: 'i-lucide-link-2' }
])

const SURFACE_TIERS = ['1', '2', '3', '4', '5'] as const
const showSurfacePrices = computed(() => formData.value.pricing_strategy === 'per_surface')

watch(
  () => formData.value.pricing_strategy,
  (strategy) => {
    if (strategy === 'per_surface') {
      if (!formData.value.surface_prices) {
        const base = Number(formData.value.default_price) || 0
        formData.value.surface_prices = {
          1: base, 2: base, 3: base, 4: base, 5: base
        } as unknown as Record<string, number>
      }
    } else {
      formData.value.surface_prices = null
    }
  }
)

function getTierPrice(tier: string): number | undefined {
  const v = formData.value.surface_prices?.[tier]
  return typeof v === 'number' ? v : typeof v === 'string' ? Number(v) : undefined
}

function setTierPrice(tier: string, value: number | string | undefined) {
  if (!formData.value.surface_prices) {
    formData.value.surface_prices = {}
  }
  const n = value === undefined || value === '' ? 0 : Number(value)
  formData.value.surface_prices[tier] = Number.isFinite(n) ? n : 0
}

// Duration presets
const DURATION_PRESETS = [15, 30, 45, 60, 90] as const

const categoryOptions = computed(() =>
  props.categories.map(c => ({
    value: c.id,
    label: c.names[locale.value] || c.names.es || c.names.en || c.key
  }))
)

const odontogramTypeOptions = computed(() => [
  { value: undefined, label: t('catalog.noOdontogramMapping') },
  ...ALL_TREATMENT_TYPES.map(type => ({
    value: type,
    label: t(`odontogram.treatments.${type}`, type)
  }))
])

const clinicalCategoryOptions = computed(() =>
  TREATMENT_CATEGORIES.map(c => ({
    value: c.key,
    label: t(c.labelKey, c.key)
  }))
)

watch(odontogramType, (newType) => {
  if (newType) {
    const category = TREATMENT_CATEGORIES.find(c => c.treatments.includes(newType))
    if (category) {
      clinicalCategory.value = category.key
    }
    formData.value.requires_surfaces = isSurfaceTreatment(newType)
  }
})

function getVisualizationRules(treatmentType: string): string[] {
  const rules: string[] = []
  for (const [rule, treatments] of Object.entries(VISUALIZATION_RULES)) {
    if (treatments.includes(treatmentType)) {
      rules.push(rule)
    }
  }
  return rules
}

const isValid = computed(() => {
  if (!formData.value.internal_code || !itemName.value || !formData.value.category_id) {
    return false
  }
  if (sessionsEnabled.value) {
    if (sessions.value.length === 0) return false
    if (sessions.value.some(s => !s.label || s.default_price < 0)) return false
    if (!sessionsSumMatches.value) return false
  }
  return true
})

// Per-tab validation badge (red dot if invalid field on tab)
const generalHasError = computed(() =>
  !formData.value.internal_code || !itemName.value || !formData.value.category_id
)
const pricingHasError = computed(() =>
  sessionsEnabled.value && (
    sessions.value.length === 0
    || sessions.value.some(s => !s.label || s.default_price < 0)
    || !sessionsSumMatches.value
  )
)

function handleSubmit() {
  if (!isValid.value) return

  const cleanData: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(formData.value)) {
    if (value !== undefined) {
      cleanData[key] = value
    }
  }

  if (odontogramType.value && clinicalCategory.value) {
    cleanData.odontogram_mapping = {
      odontogram_treatment_type: odontogramType.value,
      visualization_rules: getVisualizationRules(odontogramType.value),
      visualization_config: {},
      clinical_category: clinicalCategory.value
    }
  }

  cleanData.sessions = sessionsEnabled.value ? sessionsToPayload() : []

  if (isCreateMode.value) {
    emit('create', cleanData as TreatmentCatalogItemCreate)
  } else {
    emit('save', cleanData as TreatmentCatalogItemUpdate)
  }
}

function handleClose() {
  open.value = false
}
</script>

<template>
  <UModal
    v-model:open="open"
    :ui="{ content: '!max-w-3xl' }"
  >
    <template #content>
      <div class="bg-surface rounded-lg w-full max-h-[92vh] flex flex-col">
        <!-- Header: identity preview + tabs -->
        <div class="border-b border-default shrink-0">
          <div class="flex items-start justify-between gap-4 px-5 pt-4 pb-3">
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 mb-1">
                <UIcon
                  :name="isCreateMode ? 'i-lucide-plus-circle' : 'i-lucide-edit-3'"
                  class="w-4 h-4 text-primary-accent"
                />
                <span class="text-xs uppercase tracking-wide font-semibold text-muted">
                  {{ isCreateMode ? t('catalog.newItem') : t('catalog.editItem') }}
                </span>
              </div>
              <h3 class="font-semibold text-lg text-default dark:text-white truncate">
                {{ itemName || t('catalog.unnamed') }}
              </h3>
              <div class="flex items-center gap-2 mt-1.5 flex-wrap">
                <span class="font-mono text-xs text-muted px-2 py-0.5 rounded bg-surface-muted">
                  {{ formData.internal_code || '—' }}
                </span>
                <UBadge
                  variant="subtle"
                  color="primary"
                  size="xs"
                >
                  {{ catalog.formatPrice(formData.default_price ?? 0) }}
                </UBadge>
                <UBadge
                  v-if="formData.default_duration_minutes"
                  variant="subtle"
                  color="neutral"
                  size="xs"
                >
                  {{ formData.default_duration_minutes }} min
                </UBadge>
                <UBadge
                  v-if="!formData.is_active"
                  variant="subtle"
                  color="error"
                  size="xs"
                >
                  {{ t('common.inactive') }}
                </UBadge>
                <UBadge
                  v-if="item?.is_system"
                  variant="subtle"
                  color="info"
                  size="xs"
                >
                  {{ t('catalog.system') }}
                </UBadge>
              </div>
            </div>
            <UButton
              variant="ghost"
              color="neutral"
              icon="i-lucide-x"
              size="sm"
              @click="handleClose"
            />
          </div>

          <!-- Tabs -->
          <div class="flex gap-0 px-5 overflow-x-auto">
            <button
              v-for="tab in tabs"
              :key="tab.id"
              type="button"
              class="px-3 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap flex items-center gap-1.5 relative"
              :class="activeTab === tab.id
                ? 'border-primary-accent text-default dark:text-white'
                : 'border-transparent text-muted hover:text-default'"
              @click="activeTab = tab.id"
            >
              <UIcon
                :name="tab.icon"
                class="w-4 h-4"
              />
              {{ tab.label }}
              <span
                v-if="(tab.id === 'general' && generalHasError) || (tab.id === 'pricing' && pricingHasError)"
                class="w-1.5 h-1.5 rounded-full bg-danger-accent absolute top-2 right-1"
              />
            </button>
          </div>
        </div>

        <!-- Scrollable content -->
        <div class="overflow-y-auto flex-1 p-5">
          <form
            id="catalog-edit-form"
            @submit.prevent="handleSubmit"
          >
            <!-- ============= GENERAL ============= -->
            <div
              v-show="activeTab === 'general'"
              class="space-y-5"
            >
              <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                <UFormField
                  :label="t('catalog.code')"
                  class="md:col-span-1"
                >
                  <UInput
                    v-model="formData.internal_code"
                    :disabled="isSystem"
                    placeholder="TX-001"
                    required
                  />
                </UFormField>

                <UFormField
                  :label="t('catalog.category')"
                  class="md:col-span-2"
                >
                  <USelect
                    v-model="formData.category_id"
                    :items="categoryOptions"
                    value-key="value"
                    label-key="label"
                    :placeholder="t('catalog.selectCategory')"
                    :disabled="isSystem"
                  />
                </UFormField>
              </div>

              <UFormField :label="t('catalog.name')">
                <UInput
                  v-model="itemName"
                  required
                />
              </UFormField>

              <UFormField :label="t('catalog.materialNotes')">
                <UTextarea
                  v-model="formData.material_notes"
                  rows="2"
                  :placeholder="t('catalog.materialNotesPlaceholder')"
                />
              </UFormField>

              <div class="flex items-center justify-between p-3 rounded-lg border border-default bg-surface-muted/30">
                <div>
                  <div class="font-medium text-sm text-default dark:text-white">
                    {{ t('catalog.active') }}
                  </div>
                  <p class="text-xs text-muted mt-0.5">
                    {{ t('catalog.activeHint') }}
                  </p>
                </div>
                <USwitch
                  v-model="formData.is_active"
                  :disabled="isSystem"
                />
              </div>
            </div>

            <!-- ============= PRICING ============= -->
            <div
              v-show="activeTab === 'pricing'"
              class="space-y-5"
            >
              <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                <UFormField :label="t('catalog.defaultPrice')">
                  <UInput
                    v-model.number="formData.default_price"
                    type="number"
                    step="0.01"
                    min="0"
                  >
                    <template #trailing>
                      <span class="text-muted text-sm">€</span>
                    </template>
                  </UInput>
                </UFormField>

                <UFormField :label="t('catalog.costPrice')">
                  <UInput
                    v-model.number="formData.cost_price"
                    type="number"
                    step="0.01"
                    min="0"
                  >
                    <template #trailing>
                      <span class="text-muted text-sm">€</span>
                    </template>
                  </UInput>
                </UFormField>

                <UFormField :label="t('catalog.vatType')">
                  <USelect
                    v-model="formData.vat_type_id"
                    :items="vatTypeOptions"
                    value-key="value"
                    label-key="label"
                    :placeholder="t('catalog.selectVatType')"
                  />
                </UFormField>
              </div>

              <!-- Pricing strategy as visual cards -->
              <div>
                <label class="block text-sm font-medium text-default dark:text-white mb-2">
                  {{ t('catalog.pricingStrategy.label') }}
                </label>
                <div class="grid grid-cols-2 md:grid-cols-4 gap-2">
                  <button
                    v-for="opt in strategyOptionsVisual"
                    :key="opt.value"
                    type="button"
                    class="p-3 rounded-lg border-2 transition-all text-left disabled:opacity-50 disabled:cursor-not-allowed"
                    :class="formData.pricing_strategy === opt.value
                      ? 'border-primary-accent bg-primary-soft/30 shadow-sm'
                      : 'border-default hover:border-muted bg-surface'"
                    :disabled="isSystem"
                    @click="formData.pricing_strategy = opt.value"
                  >
                    <UIcon
                      :name="opt.icon"
                      class="w-5 h-5 mb-1.5"
                      :class="formData.pricing_strategy === opt.value ? 'text-primary-accent' : 'text-muted'"
                    />
                    <div class="text-xs font-medium leading-tight text-default dark:text-white">
                      {{ opt.label }}
                    </div>
                  </button>
                </div>
                <p class="text-xs text-muted mt-2">
                  {{ t('catalog.pricingStrategy.help') }}
                </p>
              </div>

              <!-- Surface tiers -->
              <div
                v-if="showSurfacePrices"
                class="rounded-lg border border-default bg-surface-muted/30 p-4"
              >
                <div class="flex items-center gap-2 mb-1">
                  <UIcon
                    name="i-lucide-layers"
                    class="w-4 h-4 text-primary-accent"
                  />
                  <h5 class="font-medium text-sm text-default dark:text-white">
                    {{ t('catalog.surfacePrices.title') }}
                  </h5>
                </div>
                <p class="text-xs text-muted mb-3">
                  {{ t('catalog.surfacePrices.help') }}
                </p>
                <div class="grid grid-cols-5 gap-2">
                  <UFormField
                    v-for="tier in SURFACE_TIERS"
                    :key="tier"
                    :label="t('catalog.surfacePrices.tier', { n: tier })"
                  >
                    <UInput
                      :model-value="getTierPrice(tier)"
                      type="number"
                      step="0.01"
                      min="0"
                      size="sm"
                      @update:model-value="setTierPrice(tier, $event)"
                    />
                  </UFormField>
                </div>
              </div>

              <!-- Sessions -->
              <div class="rounded-lg border border-default overflow-hidden">
                <div class="flex items-center justify-between p-3 bg-surface-muted/30">
                  <div class="flex-1 min-w-0">
                    <div class="font-medium text-sm text-default dark:text-white flex items-center gap-2">
                      <UIcon
                        name="i-lucide-calendar-clock"
                        class="w-4 h-4 text-primary-accent"
                      />
                      {{ t('catalog.sessions.title') }}
                    </div>
                    <p class="text-xs text-muted mt-0.5">
                      {{ t('catalog.sessions.help') }}
                    </p>
                  </div>
                  <USwitch v-model="sessionsEnabled" />
                </div>

                <div
                  v-if="sessionsEnabled"
                  class="border-t border-default"
                >
                  <div class="p-3 space-y-2">
                    <div
                      v-for="(session, idx) in sessions"
                      :key="idx"
                      class="flex items-center gap-2"
                    >
                      <div class="w-7 h-7 rounded-full bg-primary-soft/40 text-primary-accent font-semibold text-xs flex items-center justify-center shrink-0">
                        {{ idx + 1 }}
                      </div>
                      <UInput
                        v-model="session.label"
                        :placeholder="t('catalog.sessions.labelPlaceholder')"
                        class="flex-1"
                      />
                      <UInput
                        v-model.number="session.default_price"
                        type="number"
                        step="0.01"
                        min="0"
                        class="w-28"
                      >
                        <template #trailing>
                          <span class="text-muted text-xs">€</span>
                        </template>
                      </UInput>
                      <UButton
                        icon="i-lucide-trash-2"
                        color="error"
                        variant="ghost"
                        size="sm"
                        @click="removeSession(idx)"
                      />
                    </div>
                    <UButton
                      icon="i-lucide-plus"
                      variant="soft"
                      size="xs"
                      block
                      @click="addSession"
                    >
                      {{ t('catalog.sessions.add') }}
                    </UButton>
                  </div>

                  <!-- Sum visualization -->
                  <div class="px-3 pb-3 pt-1 border-t border-subtle">
                    <div class="flex items-center justify-between text-xs mb-1.5">
                      <span class="text-muted">
                        {{ sessionsSum.toFixed(2) }} € / {{ (Number(formData.default_price) || 0).toFixed(2) }} €
                      </span>
                      <span
                        class="flex items-center gap-1 font-medium"
                        :class="sessionsSumMatches ? 'text-success-accent' : 'text-danger-accent'"
                      >
                        <UIcon
                          :name="sessionsSumMatches ? 'i-lucide-check-circle-2' : 'i-lucide-alert-circle'"
                          class="w-3.5 h-3.5"
                        />
                        {{ sessionsProgress.toFixed(0) }}%
                      </span>
                    </div>
                    <div class="h-1.5 rounded-full bg-surface-muted overflow-hidden">
                      <div
                        class="h-full transition-all duration-300"
                        :class="sessionsSumMatches ? 'bg-success-accent' : 'bg-danger-accent'"
                        :style="{ width: `${Math.min(100, sessionsProgress)}%` }"
                      />
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- ============= SCHEDULING ============= -->
            <div
              v-show="activeTab === 'scheduling'"
              class="space-y-5"
            >
              <UFormField :label="t('catalog.duration')">
                <div class="flex items-center gap-3 flex-wrap">
                  <UInput
                    v-model.number="formData.default_duration_minutes"
                    type="number"
                    min="0"
                    max="480"
                    class="w-32"
                  >
                    <template #trailing>
                      <span class="text-muted text-sm">min</span>
                    </template>
                  </UInput>
                  <div class="flex gap-1 flex-wrap">
                    <UButton
                      v-for="preset in DURATION_PRESETS"
                      :key="preset"
                      type="button"
                      size="xs"
                      :variant="formData.default_duration_minutes === preset ? 'solid' : 'soft'"
                      :color="formData.default_duration_minutes === preset ? 'primary' : 'neutral'"
                      @click="formData.default_duration_minutes = preset"
                    >
                      {{ preset }}m
                    </UButton>
                  </div>
                </div>
              </UFormField>

              <div class="flex items-center justify-between p-3 rounded-lg border border-default bg-surface-muted/30">
                <div class="flex items-center gap-2">
                  <UIcon
                    name="i-lucide-calendar-check"
                    class="w-4 h-4 text-muted"
                  />
                  <span class="text-sm font-medium text-default dark:text-white">
                    {{ t('catalog.requiresAppointment') }}
                  </span>
                </div>
                <USwitch v-model="formData.requires_appointment" />
              </div>
            </div>

            <!-- ============= CLINICAL ============= -->
            <div
              v-show="activeTab === 'clinical'"
              class="space-y-5"
            >
              <!-- Scope as visual cards -->
              <div>
                <label class="block text-sm font-medium text-default dark:text-white mb-2">
                  {{ t('catalog.scope') }}
                </label>
                <div class="grid grid-cols-2 md:grid-cols-4 gap-2">
                  <button
                    v-for="opt in scopeOptionsVisual"
                    :key="opt.value"
                    type="button"
                    class="p-3 rounded-lg border-2 transition-all text-center disabled:opacity-50 disabled:cursor-not-allowed"
                    :class="formData.treatment_scope === opt.value
                      ? 'border-primary-accent bg-primary-soft/30 shadow-sm'
                      : 'border-default hover:border-muted bg-surface'"
                    :disabled="isSystem"
                    @click="formData.treatment_scope = opt.value"
                  >
                    <UIcon
                      :name="opt.icon"
                      class="w-5 h-5 mx-auto mb-1"
                      :class="formData.treatment_scope === opt.value ? 'text-primary-accent' : 'text-muted'"
                    />
                    <div class="text-xs font-medium text-default dark:text-white">
                      {{ opt.label }}
                    </div>
                  </button>
                </div>
              </div>

              <!-- Characteristic toggles -->
              <div class="grid grid-cols-1 md:grid-cols-2 gap-2">
                <div class="flex items-center justify-between p-3 rounded-lg border border-default bg-surface-muted/30">
                  <div class="flex items-center gap-2">
                    <UIcon
                      name="i-lucide-microscope"
                      class="w-4 h-4 text-muted"
                    />
                    <span class="text-sm font-medium text-default dark:text-white">
                      {{ t('catalog.isDiagnostic') }}
                    </span>
                  </div>
                  <USwitch
                    v-model="formData.is_diagnostic"
                    :disabled="isSystem"
                  />
                </div>
                <div class="flex items-center justify-between p-3 rounded-lg border border-default bg-surface-muted/30">
                  <div class="flex items-center gap-2">
                    <UIcon
                      name="i-lucide-square-stack"
                      class="w-4 h-4 text-muted"
                    />
                    <span class="text-sm font-medium text-default dark:text-white">
                      {{ t('catalog.requiresSurfaces') }}
                    </span>
                  </div>
                  <USwitch
                    v-model="formData.requires_surfaces"
                    :disabled="isSystem"
                  />
                </div>
              </div>

              <!-- Odontogram mapping -->
              <div class="rounded-lg border border-default overflow-hidden">
                <div class="flex items-center gap-2 p-3 bg-surface-muted/30 border-b border-default">
                  <UIcon
                    name="i-lucide-grid-3x3"
                    class="w-4 h-4 text-primary-accent"
                  />
                  <span class="font-medium text-sm text-default dark:text-white">
                    {{ t('catalog.odontogramMapping') }}
                  </span>
                </div>
                <div class="p-4 space-y-3">
                  <p class="text-xs text-muted">
                    {{ t('catalog.odontogramMappingDescription') }}
                  </p>
                  <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <UFormField :label="t('catalog.odontogramType')">
                      <USelect
                        v-model="odontogramType"
                        :items="odontogramTypeOptions"
                        value-key="value"
                        label-key="label"
                        :placeholder="t('catalog.selectOdontogramType')"
                      />
                    </UFormField>
                    <UFormField :label="t('catalog.clinicalCategory')">
                      <USelect
                        v-model="clinicalCategory"
                        :items="clinicalCategoryOptions"
                        value-key="value"
                        label-key="label"
                        :placeholder="t('catalog.selectClinicalCategory')"
                        :disabled="!odontogramType"
                      />
                    </UFormField>
                  </div>
                  <p
                    v-if="odontogramType"
                    class="text-xs text-info-accent flex items-start gap-1.5"
                  >
                    <UIcon
                      name="i-lucide-info"
                      class="w-3.5 h-3.5 mt-0.5 shrink-0"
                    />
                    {{ t('catalog.odontogramMappingHint') }}
                  </p>
                </div>
              </div>
            </div>
          </form>
        </div>

        <!-- Footer -->
        <div class="flex items-center justify-end gap-2 p-4 border-t border-default shrink-0">
          <UButton
            variant="ghost"
            @click="handleClose"
          >
            {{ t('common.cancel') }}
          </UButton>
          <UButton
            :loading="loading"
            :disabled="!isValid"
            icon="i-lucide-check"
            @click="handleSubmit"
          >
            {{ t('common.save') }}
          </UButton>
        </div>
      </div>
    </template>
  </UModal>
</template>
