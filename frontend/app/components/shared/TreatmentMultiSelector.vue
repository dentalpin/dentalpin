<script setup lang="ts">
import type { TreatmentCatalogItem } from '~/types'

const props = defineProps<{
  modelValue?: TreatmentCatalogItem[]
  placeholder?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [items: TreatmentCatalogItem[]]
}>()

const { t } = useI18n()
const {
  popularItems,
  searchResults,
  isSearching,
  isLoadingPopular,
  loadPopularItems,
  search,
  getItemName,
  formatPrice,
  getCategoryName
} = useTreatmentCatalogSearch()

const selectedItems = ref<TreatmentCatalogItem[]>(props.modelValue || [])
const showSelector = ref(false)

onMounted(loadPopularItems)

function handleSelect(item: TreatmentCatalogItem | null) {
  if (!item) return
  if (selectedItems.value.some(s => s.id === item.id)) return
  selectedItems.value = [...selectedItems.value, item]
  emit('update:modelValue', selectedItems.value)
  showSelector.value = false
}

function removeItem(itemId: string) {
  selectedItems.value = selectedItems.value.filter(i => i.id !== itemId)
  emit('update:modelValue', selectedItems.value)
}

watch(() => props.modelValue, (newVal) => {
  selectedItems.value = newVal || []
})

const availableItems = computed(() => {
  const selectedIds = new Set(selectedItems.value.map(s => s.id))
  return popularItems.value.filter(item => !selectedIds.has(item.id))
})

const availableSearchResults = computed(() => {
  const selectedIds = new Set(selectedItems.value.map(s => s.id))
  return searchResults.value.filter(item => !selectedIds.has(item.id))
})

const totalDuration = computed(() =>
  selectedItems.value.reduce((acc, item) => acc + (item.default_duration_minutes || 0), 0)
)
</script>

<template>
  <div class="space-y-3">
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
          <div class="flex items-center gap-2">
            <span class="text-caption text-subtle">{{ item.internal_code }}</span>
            <UBadge
              v-if="getCategoryName(item)"
              size="xs"
              color="neutral"
              variant="subtle"
            >
              {{ getCategoryName(item) }}
            </UBadge>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <span
            v-if="item.default_duration_minutes"
            class="text-caption text-subtle"
          >
            {{ t('common.durationMinutes', { value: item.default_duration_minutes }) }}
          </span>
          <span class="text-sm font-semibold text-primary-accent">
            {{ formatPrice(item.default_price) }}
          </span>
          <UButton
            variant="ghost"
            color="neutral"
            icon="i-lucide-x"
            size="xs"
            @click="removeItem(item.id)"
          />
        </div>
      </div>

      <!-- Summary -->
      <div
        v-if="totalDuration > 0"
        class="text-caption text-subtle text-right"
      >
        {{ t('appointments.estimatedDuration') }}: {{ t('common.durationMinutes', { value: totalDuration }) }}
      </div>
    </div>

    <!-- Add treatment button / selector -->
    <div v-if="!showSelector">
      <UButton
        variant="soft"
        color="primary"
        icon="i-lucide-plus"
        size="sm"
        block
        @click="showSelector = true"
      >
        {{ t('appointments.addTreatment') }}
      </UButton>
    </div>

    <!-- Visual selector when adding -->
    <div
      v-else
      class="border border-default rounded-lg p-3"
    >
      <div class="flex items-center justify-between mb-3">
        <span class="text-sm font-medium text-muted">
          {{ t('appointments.selectTreatment') }}
        </span>
        <UButton
          variant="ghost"
          color="neutral"
          icon="i-lucide-x"
          size="xs"
          @click="showSelector = false"
        />
      </div>

      <VisualSelector
        :model-value="null"
        :initial-items="availableItems"
        :search-results="availableSearchResults"
        :is-searching="isSearching || isLoadingPopular"
        :placeholder="placeholder || t('budget.items.searchCatalog')"
        :empty-label="t('selector.noCommonTreatments')"
        :grid-cols="2"
        in-modal
        @update:model-value="handleSelect"
        @search="search"
      >
        <template #item="{ item }">
          <div class="space-y-1">
            <p class="text-sm font-medium text-default line-clamp-1">
              {{ getItemName(item) }}
            </p>
            <div class="flex items-center justify-between">
              <span class="text-caption text-subtle">{{ item.internal_code }}</span>
              <span class="text-sm font-semibold text-primary-accent">
                {{ formatPrice(item.default_price) }}
              </span>
            </div>
            <UBadge
              v-if="getCategoryName(item)"
              size="xs"
              color="neutral"
              variant="subtle"
              class="truncate max-w-full"
            >
              {{ getCategoryName(item) }}
            </UBadge>
          </div>
        </template>
      </VisualSelector>
    </div>
  </div>
</template>
