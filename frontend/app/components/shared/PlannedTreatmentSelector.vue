<script setup lang="ts">
import type { PlannedTreatmentItem } from '~/types'

const props = defineProps<{
  modelValue?: PlannedTreatmentItem[]
  patientId?: string
  placeholder?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [items: PlannedTreatmentItem[]]
}>()

const { t, locale } = useI18n()
const { fetchPatientPendingItems } = useTreatmentPlans()
const { formatPrice } = useCatalog()

// State
const pendingItems = ref<PlannedTreatmentItem[]>([])
const isLoading = ref(false)
const selectedItems = ref<PlannedTreatmentItem[]>(props.modelValue || [])
const showSelector = ref(false)
const searchQuery = ref('')

// Load pending items when patient changes
watch(() => props.patientId, async (newPatientId) => {
  if (newPatientId) {
    await loadPendingItems(newPatientId)
  } else {
    pendingItems.value = []
  }
}, { immediate: true })

async function loadPendingItems(patientId: string) {
  isLoading.value = true
  try {
    pendingItems.value = await fetchPatientPendingItems(patientId)
  } catch {
    pendingItems.value = []
  } finally {
    isLoading.value = false
  }
}

function handleSelect(item: PlannedTreatmentItem) {
  // Check if already selected
  if (selectedItems.value.some(s => s.id === item.id)) {
    return
  }

  selectedItems.value = [...selectedItems.value, item]
  emit('update:modelValue', selectedItems.value)
  showSelector.value = false
}

function removeItem(itemId: string) {
  selectedItems.value = selectedItems.value.filter(i => i.id !== itemId)
  emit('update:modelValue', selectedItems.value)
}

// Sync with parent
watch(() => props.modelValue, (newVal) => {
  selectedItems.value = newVal || []
})

// Catalog link lives on the Treatment; item.catalog_item is kept for historical
// records and may be absent, so fall back to treatment.catalog_item.
function getCatalog(item: PlannedTreatmentItem) {
  return item.catalog_item || item.treatment?.catalog_item
}

function getItemName(item: PlannedTreatmentItem): string {
  const catalog = getCatalog(item)
  const names = catalog?.names
  if (names) {
    const name = names[locale.value] || names.es
    if (name) return name
    if (catalog?.internal_code) return catalog.internal_code
  }
  const clinicalType = item.treatment?.clinical_type
  if (clinicalType) {
    const key = `odontogram.treatments.types.${clinicalType}`
    const translated = t(key)
    if (translated !== key) return translated
    return clinicalType
  }
  return t('treatmentPlans.unknownTreatment')
}

// Get price from item (reads the Treatment's frozen price_snapshot when present).
function getItemPrice(item: PlannedTreatmentItem): number | undefined {
  const snap = item.treatment?.price_snapshot
  if (snap) {
    const parsed = Number(snap)
    if (Number.isFinite(parsed)) return parsed
  }
  const def = getCatalog(item)?.default_price
  const parsed = typeof def === 'string' ? Number(def) : def
  return typeof parsed === 'number' && Number.isFinite(parsed) ? parsed : undefined
}

// Get tooth info string
function getToothInfo(item: PlannedTreatmentItem): string | null {
  const teeth = item.treatment?.teeth ?? []
  if (teeth.length === 0) {
    return t('treatmentPlans.globalTreatment')
  }
  const tooth = teeth[0]
  if (teeth.length === 1 && tooth) {
    const surfaces = (tooth.surfaces as string[] | undefined)?.join(', ')
    return surfaces ? `#${tooth.tooth_number} (${surfaces})` : `#${tooth.tooth_number}`
  }
  return `#${teeth.map(t => t.tooth_number).join(', ')}`
}

// Get plan display name
function getPlanLabel(item: PlannedTreatmentItem): string | null {
  if (!item.treatment_plan) return null
  return item.treatment_plan.title || item.treatment_plan.plan_number
}

// A confirmed plan whose budget the patient hasn't accepted yet is
// schedulable (#108), but the receptionist should see they're booking
// ahead of the acceptance.
function isAwaitingBudget(item: PlannedTreatmentItem): boolean {
  return item.treatment_plan?.status === 'pending'
}

// Items available for selection (not already selected)
const availableItems = computed(() => {
  const selectedIds = new Set(selectedItems.value.map(s => s.id))
  let items = pendingItems.value.filter(item => !selectedIds.has(item.id))

  // Filter by search query
  if (searchQuery.value.length >= 2) {
    const query = searchQuery.value.toLowerCase()
    items = items.filter((item) => {
      const name = getItemName(item).toLowerCase()
      const code = getCatalog(item)?.internal_code?.toLowerCase() || ''
      return name.includes(query) || code.includes(query)
    })
  }

  return items
})

// Check if patient has pending treatments
const hasPendingTreatments = computed(() => {
  return pendingItems.value.length > 0
})
</script>

<template>
  <div class="space-y-3">
    <!-- No patient selected message -->
    <div
      v-if="!patientId"
      class="text-sm text-muted text-center py-4"
    >
      {{ t('appointments.selectPatientFirst') }}
    </div>

    <!-- Loading state -->
    <div
      v-else-if="isLoading"
      class="flex items-center justify-center py-4"
    >
      <UIcon
        name="i-lucide-loader-2"
        class="w-5 h-5 animate-spin text-subtle"
      />
    </div>

    <!-- No pending treatments message -->
    <div
      v-else-if="!hasPendingTreatments && selectedItems.length === 0"
      class="text-sm text-muted text-center py-4 bg-surface-muted rounded-lg"
    >
      <UIcon
        name="i-lucide-clipboard-list"
        class="w-8 h-8 mx-auto mb-2 text-subtle"
      />
      <p>{{ t('appointments.noPendingTreatments') }}</p>
      <p class="text-xs mt-1">
        {{ t('appointments.createPlanFirst') }}
      </p>
    </div>

    <template v-else>
      <!-- Selected treatments list -->
      <div
        v-if="selectedItems.length > 0"
        class="space-y-2"
      >
        <div
          v-for="item in selectedItems"
          :key="item.id"
          class="flex items-center justify-between p-2 bg-[var(--color-primary-soft)] rounded-lg"
        >
          <div class="min-w-0 flex-1">
            <p class="text-sm font-medium text-default truncate">
              {{ getItemName(item) }}
            </p>
            <div class="flex items-center gap-2 flex-wrap">
              <span
                v-if="getCatalog(item)?.internal_code"
                class="text-caption text-subtle"
              >
                {{ getCatalog(item)?.internal_code }}
              </span>
              <UBadge
                v-if="getToothInfo(item)"
                size="xs"
                color="neutral"
                variant="subtle"
              >
                {{ getToothInfo(item) }}
              </UBadge>
              <UBadge
                v-if="getPlanLabel(item)"
                size="xs"
                color="primary"
                variant="subtle"
              >
                {{ getPlanLabel(item) }}
              </UBadge>
              <UBadge
                v-if="isAwaitingBudget(item)"
                size="xs"
                color="warning"
                variant="subtle"
                icon="i-lucide-hourglass"
              >
                {{ t('appointments.planAwaitingBudget') }}
              </UBadge>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <span
              v-if="getItemPrice(item)"
              class="text-sm font-semibold text-primary-accent"
            >
              {{ formatPrice(getItemPrice(item)) }}
            </span>
            <UButton
              variant="ghost"
              color="neutral"
              icon="i-lucide-x"
              :aria-label="t('common.remove')"
              size="xs"
              @click="removeItem(item.id)"
            />
          </div>
        </div>
      </div>

      <!-- Add treatment button / selector -->
      <div v-if="!showSelector && availableItems.length > 0">
        <UButton
          variant="soft"
          color="primary"
          icon="i-lucide-plus"
          size="sm"
          block
          @click="showSelector = true"
        >
          {{ t('appointments.addTreatmentFromPlan') }}
        </UButton>
      </div>

      <!-- Selector when adding -->
      <div
        v-if="showSelector"
        class="border border-default rounded-lg p-3"
      >
        <div class="flex items-center justify-between mb-3">
          <span class="text-sm font-medium text-muted">
            {{ t('appointments.selectPendingTreatment') }}
          </span>
          <UButton
            variant="ghost"
            color="neutral"
            icon="i-lucide-x"
            :aria-label="t('common.close')"
            size="xs"
            @click="showSelector = false"
          />
        </div>

        <!-- Search input -->
        <UInput
          v-model="searchQuery"
          :placeholder="placeholder || t('common.search')"
          icon="i-lucide-search"
          class="mb-3"
        />

        <!-- Items grid -->
        <div class="grid grid-cols-1 gap-2 max-h-60 overflow-y-auto">
          <button
            v-for="item in availableItems"
            :key="item.id"
            type="button"
            class="text-left p-3 rounded-lg border border-default hover:border-[var(--color-primary)] hover:bg-[var(--color-primary-soft)] transition-colors"
            @click="handleSelect(item)"
          >
            <div class="flex items-start justify-between gap-2">
              <div class="min-w-0 flex-1">
                <p class="text-sm font-medium text-default line-clamp-1">
                  {{ getItemName(item) }}
                </p>
                <div class="flex items-center gap-2 mt-1 flex-wrap">
                  <span
                    v-if="getCatalog(item)?.internal_code"
                    class="text-caption text-subtle"
                  >
                    {{ getCatalog(item)?.internal_code }}
                  </span>
                  <UBadge
                    v-if="getToothInfo(item)"
                    size="xs"
                    color="neutral"
                    variant="subtle"
                  >
                    {{ getToothInfo(item) }}
                  </UBadge>
                  <UBadge
                    v-if="getPlanLabel(item)"
                    size="xs"
                    color="primary"
                    variant="subtle"
                  >
                    {{ getPlanLabel(item) }}
                  </UBadge>
                  <UBadge
                    v-if="isAwaitingBudget(item)"
                    size="xs"
                    color="warning"
                    variant="subtle"
                    icon="i-lucide-hourglass"
                  >
                    {{ t('appointments.planAwaitingBudget') }}
                  </UBadge>
                </div>
              </div>
              <span
                v-if="getItemPrice(item)"
                class="text-sm font-semibold text-primary-accent whitespace-nowrap"
              >
                {{ formatPrice(getItemPrice(item)) }}
              </span>
            </div>
          </button>

          <!-- Empty state -->
          <div
            v-if="availableItems.length === 0 && searchQuery.length >= 2"
            class="text-caption text-subtle text-center py-4"
          >
            {{ t('common.noResults') }}
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
