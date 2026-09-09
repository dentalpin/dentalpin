<script setup lang="ts">
/**
 * Settings command palette + visible search input.
 *
 * Visible input opens the modal palette. Cmd/Ctrl+K toggles the modal
 * from anywhere inside the settings layout. Index is built from
 * :composable:`useSettingsRegistry` and updated reactively as modules
 * register pages.
 */
import type { SearchEntry } from '~/composables/useSettingsRegistry'

const { t } = useI18n()
const router = useRouter()
const registry = useSettingsRegistry()

const isOpen = ref(false)
const query = ref('')
const activeIndex = ref(0)

const results = computed<SearchEntry[]>(() => registry.search(query.value))

function open() {
  isOpen.value = true
  query.value = ''
  activeIndex.value = 0
  nextTick(() => {
    const el = document.getElementById('settings-search-input')
    el?.focus()
  })
}

function close() {
  isOpen.value = false
}

function go(entry: SearchEntry) {
  isOpen.value = false
  router.push(entry.to)
}

function onKeydown(e: KeyboardEvent) {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault()
    if (isOpen.value) close()
    else open()
    return
  }
  if (!isOpen.value) return
  if (e.key === 'Escape') {
    close()
    return
  }
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    activeIndex.value = Math.min(activeIndex.value + 1, results.value.length - 1)
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    activeIndex.value = Math.max(activeIndex.value - 1, 0)
  } else if (e.key === 'Enter') {
    const target = results.value[activeIndex.value]
    if (target) go(target)
  }
}

onMounted(() => {
  if (import.meta.client) window.addEventListener('keydown', onKeydown)
})
onBeforeUnmount(() => {
  if (import.meta.client) window.removeEventListener('keydown', onKeydown)
})

watch(query, () => {
  activeIndex.value = 0
})

function categoryLabel(catId: string): string {
  const cat = registry.findCategory(catId)
  return cat ? t(cat.labelKey) : catId
}
</script>

<template>
  <div>
    <button
      type="button"
      class="inline-flex items-center gap-2 px-3 py-2 rounded-md ring-1 ring-[var(--color-border)] bg-(--color-surface) text-muted hover:text-default hover:ring-(--color-primary)/40 transition w-full sm:w-72 min-h-[40px]"
      @click="open"
    >
      <UIcon
        name="i-lucide-search"
        class="w-4 h-4"
      />
      <span class="text-caption flex-1 text-start truncate">
        {{ t('settings.search.placeholder') }}
      </span>
      <kbd class="hidden sm:inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-(--color-surface-muted) text-[10px] text-subtle ring-1 ring-[var(--color-border-subtle)]">
        <span>⌘</span>K
      </kbd>
    </button>

    <UModal v-model:open="isOpen">
      <template #content>
        <div class="bg-(--color-surface) rounded-[var(--radius-lg)] overflow-hidden">
          <div class="flex items-center gap-2 px-4 py-3 border-b border-[var(--color-border)]">
            <UIcon
              name="i-lucide-search"
              class="w-5 h-5 text-muted shrink-0"
            />
            <input
              id="settings-search-input"
              v-model="query"
              type="text"
              :placeholder="t('settings.search.placeholder')"
              class="flex-1 bg-transparent border-0 outline-0 text-body text-default placeholder:text-subtle"
              autocomplete="off"
              spellcheck="false"
            >
            <button
              type="button"
              class="text-caption text-muted hover:text-default"
              @click="close"
            >
              {{ t('common.cancel') }}
            </button>
          </div>

          <div
            v-if="results.length === 0"
            class="px-4 py-8 text-center text-muted"
          >
            {{ t('settings.search.empty') }}
          </div>

          <ul
            v-else
            class="max-h-96 overflow-y-auto py-1"
          >
            <li
              v-for="(entry, index) in results"
              :key="entry.id"
            >
              <button
                type="button"
                class="w-full flex items-center gap-3 px-4 py-2.5 text-start transition"
                :class="index === activeIndex ? 'bg-(--color-primary-soft)' : 'hover:bg-(--color-surface-muted)'"
                @mouseenter="activeIndex = index"
                @click="go(entry)"
              >
                <UIcon
                  :name="entry.icon"
                  class="w-5 h-5 shrink-0 text-muted"
                />
                <div class="min-w-0 flex-1">
                  <div class="flex items-center gap-2 flex-wrap">
                    <span class="text-body text-default truncate">
                      {{ entry.label }}
                    </span>
                    <UBadge
                      color="neutral"
                      variant="subtle"
                      size="sm"
                    >
                      {{ categoryLabel(entry.category) }}
                    </UBadge>
                  </div>
                  <p
                    v-if="entry.description"
                    class="text-caption text-subtle truncate"
                  >
                    {{ entry.description }}
                  </p>
                </div>
                <UIcon
                  name="i-lucide-corner-down-left"
                  class="w-4 h-4 shrink-0 text-subtle"
                />
              </button>
            </li>
          </ul>

          <div class="px-4 py-2 border-t border-[var(--color-border)] flex items-center gap-3 text-[10px] text-subtle">
            <span class="inline-flex items-center gap-1">
              <kbd class="px-1.5 py-0.5 rounded bg-(--color-surface-muted) ring-1 ring-[var(--color-border-subtle)]">↑↓</kbd>
              {{ t('settings.search.navigate') }}
            </span>
            <span class="inline-flex items-center gap-1">
              <kbd class="px-1.5 py-0.5 rounded bg-(--color-surface-muted) ring-1 ring-[var(--color-border-subtle)]">↵</kbd>
              {{ t('settings.search.open') }}
            </span>
            <span class="inline-flex items-center gap-1">
              <kbd class="px-1.5 py-0.5 rounded bg-(--color-surface-muted) ring-1 ring-[var(--color-border-subtle)]">Esc</kbd>
              {{ t('common.cancel') }}
            </span>
          </div>
        </div>
      </template>
    </UModal>
  </div>
</template>
