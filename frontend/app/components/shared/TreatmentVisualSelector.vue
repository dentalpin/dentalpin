<script setup lang="ts">
import type { TreatmentCatalogItem } from '~/types'

const props = defineProps<{
  modelValue?: TreatmentCatalogItem | null
  placeholder?: string
  inModal?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [item: TreatmentCatalogItem | null]
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

const selectedItem = ref<TreatmentCatalogItem | null>(props.modelValue || null)

onMounted(loadPopularItems)

function handleSelect(item: TreatmentCatalogItem | null) {
  selectedItem.value = item
  emit('update:modelValue', item)
}

watch(() => props.modelValue, (newVal) => {
  selectedItem.value = newVal || null
})
</script>

<template>
  <div class="relative">
    <!-- Selected item display -->
    <div
      v-if="selectedItem"
      class="p-3 bg-[var(--color-primary-soft)] rounded-lg"
    >
      <div class="flex items-center justify-between">
        <div class="min-w-0 flex-1">
          <p class="font-medium text-default">
            {{ getItemName(selectedItem) }}
          </p>
          <div class="flex items-center gap-2 mt-1">
            <span class="text-caption text-subtle">{{ selectedItem.internal_code }}</span>
            <UBadge
              v-if="getCategoryName(selectedItem)"
              size="xs"
              color="neutral"
              variant="subtle"
            >
              {{ getCategoryName(selectedItem) }}
            </UBadge>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <span class="text-h1 text-default text-primary-accent">
            {{ formatPrice(selectedItem.default_price) }}
          </span>
          <UButton
            variant="ghost"
            color="neutral"
            icon="i-lucide-x"
            :aria-label="t('common.clear')"
            size="sm"
            @click="handleSelect(null)"
          />
        </div>
      </div>
    </div>

    <!-- Visual selector when no selection -->
    <VisualSelector
      v-else
      :model-value="selectedItem"
      :initial-items="popularItems"
      :search-results="searchResults"
      :is-searching="isSearching || isLoadingPopular"
      :placeholder="placeholder || t('budget.items.searchCatalog')"
      :empty-label="t('selector.noCommonTreatments')"
      :grid-cols="2"
      :in-modal="inModal"
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
</template>
