<script setup lang="ts">
/**
 * TimelineSlider - Horizontal slider for viewing odontogram history
 *
 * Features:
 * - Discrete date stops (no intermediate positions)
 * - Visual markers for each date with labels
 * - Smooth thumb animation between positions
 * - Keyboard navigation (←/→/Home/End)
 * - Touch/drag support
 */

const props = defineProps<{
  dates: Array<{ date: string, change_count: number }>
  currentDate: string | null
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:currentDate': [value: string | null]
}>()

const { t, locale } = useI18n()

// ============================================================================
// Refs & State
// ============================================================================

const sliderRef = ref<HTMLElement>()
const isDragging = ref(false)

// ============================================================================
// Computed Properties
// ============================================================================

/** Whether last date in array is today (merges with"Now" position) */
const lastDateIsToday = computed(() => {
  const lastDate = props.dates.at(-1)?.date
  const today = new Date().toISOString().slice(0, 10)
  return lastDate === today
})

/** Current index in dates array (null = viewing live/now state) */
const currentIndex = computed(() => {
  if (!props.currentDate) return null
  return props.dates.findIndex(item => item.date === props.currentDate)
})

/** Whether user is viewing historical data */
const isViewingHistory = computed(() => props.currentDate !== null)

/** Total number of positions on the slider */
const totalPositions = computed(() =>
  lastDateIsToday.value ? props.dates.length : props.dates.length + 1
)

/** Current thumb position as percentage */
const thumbPosition = computed(() => {
  if (currentIndex.value === null) {
    return lastDateIsToday.value
      ? getPositionPercent(props.dates.length - 1)
      : 100
  }
  return getPositionPercent(currentIndex.value)
})

/** Label to display in the thumb badge */
const thumbLabel = computed(() => {
  const current = currentIndex.value === null ? undefined : props.dates[currentIndex.value]
  return current ? formatDate(current.date) : t('common.now')
})

// ============================================================================
// Helper Functions
// ============================================================================

/** Format date for display (e.g.,"15 ene" or"Jan 15") */
function formatDate(dateStr: string): string {
  const date = new Date(dateStr + 'T00:00:00')
  return date.toLocaleDateString(locale.value, {
    day: 'numeric',
    month: 'short'
  })
}

/** Calculate position percentage for a date index */
function getPositionPercent(index: number): number {
  if (totalPositions.value <= 1) return 100
  return (index / (totalPositions.value - 1)) * 100
}

/** Get marker state for styling */
function getMarkerState(index: number): 'selected' | 'now' | 'past' | 'future' {
  const isLastAndToday = lastDateIsToday.value && index === props.dates.length - 1
  const isAtNow = currentIndex.value === null

  if (isLastAndToday && isAtNow) return 'now'
  if (currentIndex.value === index) return 'selected'
  if (currentIndex.value !== null && index < currentIndex.value) return 'past'
  return 'future'
}

/** Get label for a marker */
function getMarkerLabel(index: number): string {
  const isLastAndToday = lastDateIsToday.value && index === props.dates.length - 1
  const entry = props.dates[index]
  return isLastAndToday || !entry ? t('common.now') : formatDate(entry.date)
}

// ============================================================================
// Navigation
// ============================================================================

/** Select a specific date by index */
function selectIndex(index: number | null) {
  if (props.disabled) return

  // Out of bounds or null → go to"now"
  if (index === null || index < 0 || index >= props.dates.length) {
    emit('update:currentDate', null)
    return
  }

  // Last date is today → treat as"now"
  if (lastDateIsToday.value && index === props.dates.length - 1) {
    emit('update:currentDate', null)
    return
  }

  const entry = props.dates[index]
  if (entry) emit('update:currentDate', entry.date)
}

/** Navigate to previous date */
function goToPrevious() {
  if (props.disabled) return

  if (currentIndex.value === null) {
    // At"now" → go to last historical date
    const lastHistorical = lastDateIsToday.value
      ? props.dates.length - 2
      : props.dates.length - 1
    if (lastHistorical >= 0) selectIndex(lastHistorical)
  } else if (currentIndex.value > 0) {
    selectIndex(currentIndex.value - 1)
  }
}

/** Navigate to next date */
function goToNext() {
  if (props.disabled || currentIndex.value === null) return

  const lastHistorical = lastDateIsToday.value
    ? props.dates.length - 2
    : props.dates.length - 1

  if (currentIndex.value < lastHistorical) {
    selectIndex(currentIndex.value + 1)
  } else {
    selectIndex(null) // Go to"now"
  }
}

/** Return to current/live state */
function goToNow() {
  emit('update:currentDate', null)
}

// ============================================================================
// Event Handlers
// ============================================================================

function handleKeydown(event: KeyboardEvent) {
  if (props.disabled) return

  const handlers: Record<string, () => void> = {
    ArrowLeft: goToPrevious,
    ArrowRight: goToNext,
    Home: () => selectIndex(0),
    End: () => selectIndex(null)
  }

  const handler = handlers[event.key]
  if (handler) {
    event.preventDefault()
    handler()
  }
}

function handleTrackClick(event: MouseEvent) {
  if (props.disabled || !sliderRef.value) return

  const rect = sliderRef.value.getBoundingClientRect()
  const percent = ((event.clientX - rect.left) / rect.width) * 100
  const targetIndex = Math.round((percent / 100) * (totalPositions.value - 1))

  selectIndex(targetIndex >= props.dates.length ? null : targetIndex)
}

function handleDragStart() {
  if (!props.disabled) isDragging.value = true
}

function handleDragMove(event: MouseEvent | TouchEvent) {
  if (!isDragging.value || !sliderRef.value) return

  const clientX = 'touches' in event ? event.touches[0]?.clientX : event.clientX
  if (clientX === undefined) return // touchmove can fire with an empty touch list
  const rect = sliderRef.value.getBoundingClientRect()
  const percent = Math.max(0, Math.min(100, ((clientX - rect.left) / rect.width) * 100))
  const targetIndex = Math.round((percent / 100) * (totalPositions.value - 1))

  selectIndex(targetIndex >= props.dates.length ? null : targetIndex)
}

function handleDragEnd() {
  isDragging.value = false
}

// ============================================================================
// Lifecycle
// ============================================================================

onMounted(() => {
  document.addEventListener('mousemove', handleDragMove)
  document.addEventListener('mouseup', handleDragEnd)
  document.addEventListener('touchmove', handleDragMove)
  document.addEventListener('touchend', handleDragEnd)
})

onUnmounted(() => {
  document.removeEventListener('mousemove', handleDragMove)
  document.removeEventListener('mouseup', handleDragEnd)
  document.removeEventListener('touchmove', handleDragMove)
  document.removeEventListener('touchend', handleDragEnd)
})
</script>

<template>
  <div
    class="w-full p-2 bg-surface-muted rounded-lg"
    :class="{ 'opacity-50 pointer-events-none': disabled }"
  >
    <!-- Header -->
    <div class="flex items-center justify-between h-6">
      <span class="flex items-center text-sm font-medium text-muted">
        <UIcon
          name="i-lucide-history"
          class="w-4 h-4 me-1"
        />
        {{ t('odontogram.timeline.title') }}
      </span>

      <!-- Return to Now button (fixed width container to prevent shift) -->
      <div class="w-32 flex justify-end">
        <UButton
          v-if="isViewingHistory"
          size="xs"
          color="primary"
          variant="soft"
          @click="goToNow"
        >
          {{ t('odontogram.timeline.returnToNow') }}
        </UButton>
      </div>
    </div>

    <!-- Slider track (fixed height) -->
    <div
      ref="sliderRef"
      class="relative h-10 mt-2 cursor-pointer select-none rounded focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2"
      tabindex="0"
      role="slider"
      :aria-valuenow="currentIndex ?? dates.length"
      :aria-valuemin="0"
      :aria-valuemax="dates.length"
      @click="handleTrackClick"
      @keydown="handleKeydown"
    >
      <!-- Background line -->
      <div class="absolute top-4 start-0 end-0 h-1 bg-surface-sunken  rounded-full" />

      <!-- Date markers -->
      <div
        v-for="(entry, index) in dates"
        :key="entry.date"
        class="absolute top-4 -translate-x-1/2 cursor-pointer group"
        :style="{ left: `${getPositionPercent(index)}%` }"
        :title="`${formatDate(entry.date)} (${entry.change_count} ${t('common.change', entry.change_count)})`"
        @click.stop="selectIndex(index)"
      >
        <!-- Marker dot -->
        <div
          class="w-3 h-3 rounded-full border-2 border-white  -translate-y-1/2 transition-all duration-150"
          :class="{
            'bg-[var(--color-success-accent)] scale-125': getMarkerState(index) === 'now',
            'bg-[var(--color-primary)] scale-125': getMarkerState(index) === 'selected',
            'bg-surface-sunken': getMarkerState(index) === 'past',
            'bg-[var(--color-text-subtle)]': getMarkerState(index) === 'future',
            'group-hover:scale-150 group-hover:bg-[var(--color-primary)]': getMarkerState(index) !== 'now'
          }"
        />

        <!-- Date label -->
        <span
          class="absolute top-3 left-1/2 -translate-x-1/2 text-xs whitespace-nowrap font-medium transition-colors duration-150"
          :class="{
            'text-success-accent': getMarkerState(index) === 'now',
            'text-primary-accent': getMarkerState(index) === 'selected',
            'text-muted': getMarkerState(index) === 'past' || getMarkerState(index) === 'future'
          }"
        >
          {{ getMarkerLabel(index) }}
        </span>
      </div>

      <!-- "Now" marker (only if last date is NOT today) -->
      <div
        v-if="!lastDateIsToday"
        class="absolute top-4 -translate-x-1/2 cursor-pointer group"
        style="left: 100%"
        @click.stop="goToNow"
      >
        <div
          class="w-3 h-3 rounded-full bg-[var(--color-success-accent)] border-2 border-[var(--color-surface)]  -translate-y-1/2 transition-all duration-150"
          :class="{
            'scale-125': currentIndex === null,
            'group-hover:scale-150': currentIndex !== null
          }"
        />
        <span
          class="absolute top-3 left-1/2 -translate-x-1/2 text-xs whitespace-nowrap font-medium transition-colors duration-150"
          :class="currentIndex === null ? 'text-success-accent' : 'text-muted'"
        >
          {{ t('common.now') }}
        </span>
      </div>

      <!-- Draggable thumb -->
      <div
        class="absolute top-4 -translate-x-1/2 transition-[left] duration-150 ease-out"
        :class="{ 'transition-none': isDragging }"
        :style="{ left: `${thumbPosition}%` }"
      >
        <!-- Badge above thumb -->
        <div class="absolute -top-6 left-1/2 -translate-x-1/2 whitespace-nowrap">
          <UBadge
            :color="currentIndex === null ? 'success' : 'primary'"
            variant="solid"
            size="xs"
          >
            {{ thumbLabel }}
          </UBadge>
        </div>

        <!-- Thumb circle -->
        <div
          class="w-5 h-5 -translate-y-1/2 bg-[var(--color-primary)] rounded-full shadow-lg cursor-grab border-2 border-white  transition-transform duration-100 hover:scale-110 active:cursor-grabbing active:scale-125"
          @mousedown="handleDragStart"
          @touchstart.prevent="handleDragStart"
        />
      </div>
    </div>
  </div>
</template>
