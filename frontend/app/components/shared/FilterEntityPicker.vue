<script setup lang="ts">
/**
 * FilterEntityPicker — async autocomplete chip for entity references.
 *
 * Replaces the UUID-text-input pattern that /payments uses today.
 * Caller supplies:
 *   - ``fetcher(q: string): Promise<Option[]>`` — debounced async source
 *   - ``modelValue`` — the selected entity's id (or null)
 *   - ``labelOf(id)`` — optional resolver to render the chip label when
 *     the value pre-exists (URL hydration); defaults to the id.
 */
interface Option {
  id: string
  label: string
  sublabel?: string
}

interface Props {
  /** Label shown when no entity is selected. */
  label: string
  modelValue: string | null
  fetcher: (query: string) => Promise<Option[]>
  /** Resolve a label from an id (e.g. on URL rehydration). */
  resolve?: (id: string) => Promise<Option | null>
  icon?: string
  placeholder?: string
}

const props = withDefaults(defineProps<Props>(), {
  resolve: undefined,
  icon: undefined,
  placeholder: undefined
})

const emit = defineEmits<{
  'update:modelValue': [value: string | null]
}>()

const { t } = useI18n()

const isOpen = ref(false)
const query = ref('')
const options = ref<Option[]>([])
const isLoading = ref(false)
const currentLabel = ref<string | null>(null)

let debounceTimer: ReturnType<typeof setTimeout> | null = null

async function search(q: string) {
  isLoading.value = true
  try {
    options.value = await props.fetcher(q)
  } finally {
    isLoading.value = false
  }
}

watch(query, (q) => {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => search(q), 250)
})

watch(
  () => props.modelValue,
  async (id) => {
    if (!id) {
      currentLabel.value = null
      return
    }
    if (props.resolve) {
      const opt = await props.resolve(id)
      currentLabel.value = opt?.label ?? id
    } else {
      currentLabel.value = id
    }
  },
  { immediate: true }
)

onBeforeUnmount(() => {
  if (debounceTimer) clearTimeout(debounceTimer)
})

function select(opt: Option) {
  emit('update:modelValue', opt.id)
  currentLabel.value = opt.label
  isOpen.value = false
  query.value = ''
}

function clear() {
  emit('update:modelValue', null)
  currentLabel.value = null
  query.value = ''
}

function onOpen() {
  if (!options.value.length) search('')
}

const displayLabel = computed(() => currentLabel.value ?? props.label)
const isActive = computed(() => Boolean(props.modelValue))
</script>

<template>
  <UPopover
    v-model:open="isOpen"
    @update:open="(o) => o && onOpen()"
  >
    <UButton
      :color="isActive ? 'primary' : 'neutral'"
      :variant="isActive ? 'soft' : 'outline'"
      size="sm"
      :icon="icon"
      trailing-icon="i-lucide-chevron-down"
    >
      {{ displayLabel }}
    </UButton>

    <template #content>
      <div class="p-2 w-[280px]">
        <UInput
          v-model="query"
          :placeholder="placeholder ?? t('lists.filter.searchPlaceholder')"
          icon="i-lucide-search"
          autofocus
        />
        <div class="mt-2 max-h-64 overflow-y-auto">
          <p
            v-if="isLoading"
            class="px-2 py-3 text-caption text-subtle"
          >
            {{ t('common.loading') }}
          </p>
          <p
            v-else-if="!options.length"
            class="px-2 py-3 text-caption text-subtle"
          >
            {{ t('lists.filter.noResults') }}
          </p>
          <button
            v-for="opt in options"
            :key="opt.id"
            type="button"
            class="w-full text-start px-2 py-2 rounded-token-sm hover:bg-surface-muted focus-visible:bg-surface-muted focus-visible:outline-none"
            @click="select(opt)"
          >
            <div class="text-ui text-default">
              {{ opt.label }}
            </div>
            <div
              v-if="opt.sublabel"
              class="text-caption text-subtle"
            >
              {{ opt.sublabel }}
            </div>
          </button>
        </div>
        <div
          v-if="isActive"
          class="pt-2 border-t border-subtle mt-2"
        >
          <UButton
            variant="ghost"
            color="neutral"
            size="sm"
            block
            @click="clear"
          >
            {{ t('lists.filter.clear') }}
          </UButton>
        </div>
      </div>
    </template>
  </UPopover>
</template>
