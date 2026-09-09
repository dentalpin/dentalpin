<script setup lang="ts">
/**
 * FilterBar — single-row toolbar with three regions.
 *
 *  ┌──────────────┬───────────────────────────────────────────┬────────────┐
 *  │  #search     │  default slot (chips) — auto-collapses    │  #right    │
 *  │  fixed L     │  to "Filtros (N)" button when overflowing │  pinned R  │
 *  └──────────────┴───────────────────────────────────────────┴────────────┘
 *
 * Overflow detection (desktop): a ``ResizeObserver`` + ``MutationObserver``
 * watch the chips region. When ``scrollWidth > clientWidth`` (chips don't
 * fit), the inline chips are visually hidden and a "Filtros (N)" button
 * takes their place — preventing the right-side sort from being covered.
 *
 * Chips remain mounted at all times so that measurement stays stable
 * (hiding via ``visibility:hidden`` keeps the box dimensions, avoiding
 * the show-hide-show hysteresis you get with ``display:none``).
 *
 * The same ``USlideover`` is used by both the mobile trigger and the
 * desktop overflow trigger — chips are rendered inside, fully accessible.
 *
 * Mobile (<md): chips region is hidden via CSS, the mobile button is
 * always shown alongside the right slot.
 */
interface Props {
  /** Number of active filters (excluding search). Drives the button labels. */
  activeCount?: number
  /** Optional sticky position for tall lists. */
  sticky?: boolean
}

withDefaults(defineProps<Props>(), {
  activeCount: 0,
  sticky: false
})

const emit = defineEmits<{
  reset: []
}>()

const { t } = useI18n()
const isOpen = ref(false)

// --- Overflow detection (desktop) ---------------------------------------
const chipsRegion = ref<HTMLElement | null>(null)
const chipsInner = ref<HTMLElement | null>(null)
const hasOverflow = ref(false)

function measure() {
  const inner = chipsInner.value
  if (!inner) return
  // ``inner`` is ``position: absolute; inset: 0`` so its clientWidth equals
  // the parent region's available width. ``scrollWidth`` returns the
  // intrinsic content width (chips total). The +1 padding absorbs sub-
  // pixel rounding (Safari occasionally reports scrollWidth = clientWidth + 0.5).
  hasOverflow.value = inner.scrollWidth > inner.clientWidth + 1
}

let regionRO: ResizeObserver | null = null
let innerRO: ResizeObserver | null = null
let mutationObs: MutationObserver | null = null

onMounted(() => {
  if (typeof ResizeObserver === 'undefined') return
  if (chipsRegion.value) {
    regionRO = new ResizeObserver(() => measure())
    regionRO.observe(chipsRegion.value)
  }
  if (chipsInner.value) {
    innerRO = new ResizeObserver(() => measure())
    innerRO.observe(chipsInner.value)
    // Chip count / labels can change at runtime (selections grow the label,
    // slot fillers come and go). Mutation observer catches those — RO alone
    // misses subtree label changes.
    mutationObs = new MutationObserver(() => measure())
    mutationObs.observe(chipsInner.value, {
      childList: true,
      subtree: true,
      characterData: true
    })
  }
  nextTick(measure)
})

onBeforeUnmount(() => {
  regionRO?.disconnect()
  innerRO?.disconnect()
  mutationObs?.disconnect()
})

function onReset() {
  emit('reset')
  isOpen.value = false
}
</script>

<template>
  <div
    class="flex items-center gap-2 w-full"
    :class="sticky && 'sticky top-0 z-10 bg-[var(--color-surface)] py-2'"
  >
    <!-- Search (always left) -->
    <div
      v-if="$slots.search"
      class="shrink-0 w-full max-w-xs"
    >
      <slot name="search" />
    </div>

    <!-- Desktop chips region: chips always rendered for measurement;
         visually hidden when overflow detected, replaced by "Filtros (N)". -->
    <div
      v-if="$slots.default"
      ref="chipsRegion"
      class="hidden md:block flex-1 min-w-0 relative h-9"
    >
      <div
        ref="chipsInner"
        class="absolute inset-0 flex items-center gap-2 overflow-hidden"
        :class="hasOverflow ? 'invisible pointer-events-none' : ''"
        :aria-hidden="hasOverflow ? 'true' : 'false'"
      >
        <slot />
      </div>
      <UButton
        v-show="hasOverflow"
        variant="outline"
        color="neutral"
        icon="i-lucide-sliders-horizontal"
        size="sm"
        class="absolute inset-y-0 start-0 my-auto h-fit"
        @click="isOpen = true"
      >
        {{ activeCount ? t('lists.filter.moreCount', { count: activeCount }) : t('lists.filter.more') }}
      </UButton>
    </div>

    <!-- Mobile trigger (<md) -->
    <UButton
      v-if="$slots.default"
      class="md:hidden shrink-0"
      variant="outline"
      color="neutral"
      icon="i-lucide-sliders-horizontal"
      size="sm"
      @click="isOpen = true"
    >
      <span class="sm:inline hidden">
        {{ activeCount > 0 ? t('lists.filter.moreCount', { count: activeCount }) : t('lists.filter.more') }}
      </span>
      <span class="sm:hidden">
        {{ activeCount || '' }}
      </span>
    </UButton>

    <!-- Right region: sort, pinned right -->
    <div
      v-if="$slots.right"
      class="shrink-0 ms-auto md:ms-0"
    >
      <slot name="right" />
    </div>

    <USlideover v-model:open="isOpen">
      <template #content>
        <UCard>
          <template #header>
            <div class="flex items-center justify-between">
              <h2 class="text-h2 text-default">
                {{ t('lists.filter.title') }}
              </h2>
              <UButton
                variant="ghost"
                color="neutral"
                icon="i-lucide-x"
                :aria-label="t('common.close')"
                @click="isOpen = false"
              />
            </div>
          </template>

          <div class="flex flex-col gap-3">
            <slot />
          </div>

          <template #footer>
            <div class="flex items-center justify-between gap-2">
              <UButton
                variant="ghost"
                color="neutral"
                @click="onReset"
              >
                {{ t('lists.filter.clear') }}
              </UButton>
              <UButton
                color="primary"
                @click="isOpen = false"
              >
                {{ t('lists.filter.apply') }}
              </UButton>
            </div>
          </template>
        </UCard>
      </template>
    </USlideover>
  </div>
</template>
