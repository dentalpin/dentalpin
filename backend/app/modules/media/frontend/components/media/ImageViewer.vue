<script setup lang="ts">
interface Props {
  blobUrl: string
}

defineProps<Props>()

const { t } = useI18n()

const scale = ref(1)
const MIN_SCALE = 0.25
const MAX_SCALE = 4
const SCALE_STEP = 0.25

const scalePercent = computed(() => Math.round(scale.value * 100))

function zoomIn() {
  scale.value = Math.min(MAX_SCALE, scale.value + SCALE_STEP)
}

function zoomOut() {
  scale.value = Math.max(MIN_SCALE, scale.value - SCALE_STEP)
}

function resetZoom() {
  scale.value = 1
}

function handleWheel(event: WheelEvent) {
  if (event.ctrlKey || event.metaKey) {
    event.preventDefault()
    if (event.deltaY < 0) {
      zoomIn()
    } else {
      zoomOut()
    }
  }
}
</script>

<template>
  <div class="flex flex-col h-full">
    <!-- Zoom controls -->
    <div class="flex items-center justify-center gap-2 py-2 border-b border-default bg-surface-muted">
      <UButton
        icon="i-lucide-minus"
        :aria-label="t('documents.viewer.zoomOut')"
        variant="ghost"
        size="xs"
        :disabled="scale <= MIN_SCALE"
        :title="t('documents.viewer.zoomOut', 'Zoom out')"
        @click="zoomOut"
      />
      <span class="text-sm font-medium min-w-[4rem] text-center">
        {{ scalePercent }}%
      </span>
      <UButton
        icon="i-lucide-plus"
        variant="ghost"
        size="xs"
        :disabled="scale >= MAX_SCALE"
        :title="t('documents.viewer.zoomIn', 'Zoom in')"
        @click="zoomIn"
      />
      <UButton
        icon="i-lucide-maximize-2"
        :aria-label="t('documents.viewer.resetZoom')"
        variant="ghost"
        size="xs"
        :disabled="scale === 1"
        :title="t('documents.viewer.resetZoom', 'Reset to 100%')"
        @click="resetZoom"
      />
    </div>

    <!-- Image container -->
    <div
      class="flex-1 overflow-auto flex items-center justify-center bg-surface-muted p-4"
      @wheel="handleWheel"
    >
      <img
        :src="blobUrl"
        :style="{ transform: `scale(${scale})` }"
        class="max-w-full max-h-full object-contain transition-transform duration-150 ease-out origin-center"
        alt=""
      >
    </div>

    <p class="text-caption text-subtle text-center py-1">
      {{ t('documents.viewer.zoomHint', 'Ctrl + scroll to zoom') }}
    </p>
  </div>
</template>
