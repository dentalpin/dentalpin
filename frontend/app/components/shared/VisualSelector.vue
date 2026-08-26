<script setup lang="ts" generic="T extends { id: string }">
const props = defineProps<{
  modelValue?: T | null
  initialItems: T[]
  searchResults: T[]
  isSearching: boolean
  placeholder?: string
  emptyLabel?: string
  gridCols?: number
  inModal?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [item: T | null]
  'search': [query: string]
  'footer-enter': [query: string]
}>()

const { t } = useI18n()

// Local state
const searchQuery = ref('')
const isOpen = ref(false)
const highlightedIndex = ref(-1)
const inputRef = ref<HTMLInputElement | null>(null)
const containerRef = ref<HTMLElement | null>(null)
const dropdownStyle = ref<Record<string, string>>({})

// Calculate dropdown position
function updateDropdownPosition() {
  if (!containerRef.value) return

  const rect = containerRef.value.getBoundingClientRect()
  dropdownStyle.value = {
    position: 'fixed',
    top: `${rect.bottom + 4}px`,
    left: `${rect.left}px`,
    width: `${rect.width}px`,
    zIndex: '9999'
  }
}

// Debounce search
let searchTimeout: ReturnType<typeof setTimeout> | null = null

watch(searchQuery, (val) => {
  if (searchTimeout) clearTimeout(searchTimeout)

  if (val.length < 2) {
    emit('search', '')
    return
  }

  searchTimeout = setTimeout(() => {
    emit('search', val)
  }, 300)
})

// Items to display: search results if searching, otherwise initial items
const displayItems = computed(() => {
  if (searchQuery.value.length >= 2) {
    return props.searchResults
  }
  return props.initialItems
})

// Grid columns class
const gridClass = computed(() => {
  const cols = props.gridCols || 2
  if (cols === 3) return 'grid-cols-1 sm:grid-cols-2 md:grid-cols-3'
  if (cols === 4) return 'grid-cols-2 sm:grid-cols-3 md:grid-cols-4'
  return 'grid-cols-1 sm:grid-cols-2'
})

function selectItem(item: T) {
  emit('update:modelValue', item)
  isOpen.value = false
  highlightedIndex.value = -1
}

function clearSelection() {
  emit('update:modelValue', null)
  searchQuery.value = ''
}

function handleFocus() {
  updateDropdownPosition()
  isOpen.value = true
  highlightedIndex.value = -1
}

function handleBlur() {
  // Delay to allow click on results
  setTimeout(() => {
    isOpen.value = false
    highlightedIndex.value = -1
  }, 200)
}

// Keyboard navigation
function handleKeydown(event: KeyboardEvent) {
  if (!isOpen.value) {
    return
  }

  switch (event.key) {
    case 'ArrowDown':
      if (displayItems.value.length === 0) return
      event.preventDefault()
      highlightedIndex.value = Math.min(
        highlightedIndex.value + 1,
        displayItems.value.length - 1
      )
      break
    case 'ArrowUp':
      if (displayItems.value.length === 0) return
      event.preventDefault()
      highlightedIndex.value = Math.max(highlightedIndex.value - 1, 0)
      break
    case 'Enter': {
      const item = displayItems.value[highlightedIndex.value]
      if (highlightedIndex.value >= 0 && item) {
        event.preventDefault()
        selectItem(item)
      } else if (searchQuery.value.trim().length >= 2) {
        // No item to select — give the parent a chance to handle (e.g. inline create).
        event.preventDefault()
        emit('footer-enter', searchQuery.value.trim())
      }
      break
    }
    case 'Escape':
      event.preventDefault()
      isOpen.value = false
      highlightedIndex.value = -1
      break
  }
}

// Reset highlight when results change
watch(displayItems, () => {
  highlightedIndex.value = -1
})

// Expose for parent to control
defineExpose({
  focus: () => inputRef.value?.focus(),
  clear: clearSelection
})
</script>

<template>
  <div
    ref="containerRef"
    class="relative"
  >
    <UInput
      ref="inputRef"
      v-model="searchQuery"
      :placeholder="placeholder || t('selector.typeToSearch')"
      icon="i-lucide-search"
      :loading="isSearching"
      data-testid="visual-selector-input"
      @focus="handleFocus"
      @blur="handleBlur"
      @keydown="handleKeydown"
    >
      <template
        v-if="modelValue"
        #trailing
      >
        <UButton
          variant="ghost"
          color="neutral"
          icon="i-lucide-x"
          :aria-label="t('common.clear')"
          size="xs"
          class="-mr-2"
          @click.stop="clearSelection"
        />
      </template>
    </UInput>

    <!-- Dropdown panel - teleported to body unless in modal -->
    <Teleport
      to="body"
      :disabled="inModal"
    >
      <div
        v-if="isOpen && !modelValue"
        :style="inModal ? {} : dropdownStyle"
        :class="[
          'bg-surface border border-default rounded-lg shadow-lg overflow-hidden',
          inModal ? 'absolute left-0 right-0 top-full mt-1 z-50' : ''
        ]"
      >
        <!-- Loading state -->
        <div
          v-if="isSearching"
          class="p-4 text-center text-subtle"
        >
          <UIcon
            name="i-lucide-loader-2"
            class="w-5 h-5 animate-spin mx-auto"
          />
        </div>

        <!-- Empty state -->
        <div
          v-else-if="displayItems.length === 0"
          class="p-4 text-center text-subtle text-sm"
        >
          {{ emptyLabel || t('common.noData') }}
        </div>

        <!-- Grid of items -->
        <div
          v-else
          class="max-h-72 overflow-y-auto p-2"
        >
          <div :class="['grid gap-2', gridClass]">
            <div
              v-for="(item, index) in displayItems"
              :key="item.id"
              class="p-2 rounded-lg cursor-pointer transition-colors border"
              :class="index === highlightedIndex
                ? 'bg-[var(--color-primary-soft)] border-[var(--color-primary)]'
                : 'hover:bg-surface-muted border-transparent'"
              @mousedown.prevent.stop
              @click.stop="selectItem(item)"
              @mouseenter="highlightedIndex = index"
            >
              <slot
                name="item"
                :item="item"
                :highlighted="index === highlightedIndex"
              />
            </div>
          </div>
        </div>

        <!-- Optional footer (e.g. inline "+ create" action). -->
        <!-- Rendered regardless of grid/empty/loading state so consumers -->
        <!-- can offer the action when there are no results. -->
        <div
          v-if="$slots.footer"
          class="border-t border-default"
          @mousedown.prevent.stop
        >
          <slot
            name="footer"
            :query="searchQuery.trim()"
            :has-results="displayItems.length > 0"
            :is-searching="isSearching"
          />
        </div>
      </div>
    </Teleport>
  </div>
</template>
