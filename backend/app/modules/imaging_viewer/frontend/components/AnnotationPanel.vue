<script setup lang="ts">
/**
 * Human annotation overlays for one study (T2): ruler (mm when the study
 * carries pixel spacing), freehand drawing, text notes. Coordinates are
 * stored normalized 0-1; the original bytes are never touched. Overlays are
 * visualization aids, never diagnoses.
 */
import { useImagingViewer, type StudyAnnotation, type RoiStats } from '../composables/useImagingViewer'
import { PERMISSIONS } from '~~/app/config/permissions'
import { errorDetail } from '~~/app/utils/error'

const props = defineProps<{ studyId: string }>()

const { t } = useI18n()
const { can } = usePermissions()
const { fetchRenderBlobUrl, fetchAnnotations, createAnnotation, deleteAnnotation, fetchRoiStats } = useImagingViewer()

const annotations = ref<StudyAnnotation[]>([])
const renderBlobUrl = ref<string | null>(null)
const renderError = ref<string | null>(null)
const renderToken = ref(0)
const tool = ref<'ruler' | 'freehand' | 'note' | 'stats' | null>(null)
const draft = ref<Array<[number, number]>>([])
const drawing = ref(false)
const noteText = ref('')
const noteAt = ref<[number, number] | null>(null)
const roiRect = ref<Array<[number, number]> | null>(null)
const roiStats = ref<RoiStats | null>(null)
const roiError = ref<string | null>(null)
const statsToken = ref(0)
const actionError = ref<string | null>(null)
const svgEl = ref<SVGSVGElement | null>(null)

const canWrite = computed(() => can(PERMISSIONS.imagingViewer.studies.write))
/** The render failure wins: without the image the panel cannot be used at all. */
const shownError = computed(() => renderError.value ?? actionError.value)

async function load() {
  actionError.value = null
  try {
    annotations.value = await fetchAnnotations(props.studyId)
  } catch {
    actionError.value = t('imagingViewer.annotations.loadFailed')
  }
}

/** One render per study: the panel is the only surface that shows the PNG. */
async function loadRender() {
  // Token guard: clicking through studies faster than the network answers
  // would otherwise let a slow earlier response overwrite a newer render and
  // orphan its object URL.
  const token = ++renderToken.value
  renderError.value = null
  if (renderBlobUrl.value) URL.revokeObjectURL(renderBlobUrl.value)
  const url = await fetchRenderBlobUrl(props.studyId)
  if (token !== renderToken.value) {
    if (url) URL.revokeObjectURL(url)
    return
  }
  renderBlobUrl.value = url
  if (!url) {
    renderError.value = t('imagingViewer.viewer.unavailable')
  }
}

onMounted(() => {
  void load()
  void loadRender()
})
onBeforeUnmount(() => {
  if (renderBlobUrl.value) URL.revokeObjectURL(renderBlobUrl.value)
})

function toNorm(e: PointerEvent): [number, number] {
  const rect = (svgEl.value as SVGSVGElement).getBoundingClientRect()
  const x = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width))
  const y = Math.min(1, Math.max(0, (e.clientY - rect.top) / rect.height))
  return [x, y]
}

function onPointerDown(e: PointerEvent) {
  if (!tool.value) return
  // The stats tool is read-only: it measures, it does not persist, so it
  // stays available without the write permission.
  if (tool.value !== 'stats' && !canWrite.value) return
  // Nothing accepts pointers on the placeholder: an annotation or a
  // measurement over an image that is not rendered is meaningless.
  if (!renderBlobUrl.value) return
  const p = toNorm(e)
  if (tool.value === 'note') {
    noteAt.value = p
    return
  }
  drawing.value = true
  draft.value = [p]
}

function onPointerMove(e: PointerEvent) {
  if (!drawing.value) return
  if (tool.value === 'freehand') {
    draft.value = [...draft.value, toNorm(e)]
  } else if (tool.value === 'stats') {
    const a = draft.value[0]
    if (a) draft.value = [a, toNorm(e)]
  }
}

async function onPointerUp(e: PointerEvent) {
  if (!drawing.value) return
  drawing.value = false
  if (tool.value === 'freehand') {
    await save('freehand', draft.value)
  } else if (tool.value === 'ruler') {
    draft.value = [...draft.value, toNorm(e)]
    if (draft.value.length >= 2) await save('ruler', draft.value.slice(0, 2))
  } else if (tool.value === 'stats') {
    const a = draft.value[0]
    const b = toNorm(e)
    if (a) {
      roiRect.value = [a, b]
      await measure()
    }
  }
  draft.value = []
}

/** Rectangle drawn over the image as SVG attrs: the live drag, or the
 * last measured region. Corners are checked before use: a tuple indexed
 * out of a shorter array is never trusted. */
const statsRectAttrs = computed<{ x: number, y: number, width: number, height: number } | null>(() => {
  const live = drawing.value && tool.value === 'stats'
  const corners = live ? draft.value : roiRect.value
  const a = corners?.[0]
  const b = live ? (corners?.[1] ?? a) : corners?.[1]
  if (!a || !b) return null
  return {
    x: Math.min(a[0], b[0]) * 100,
    y: Math.min(a[1], b[1]) * 100,
    width: Math.max(Math.abs(a[0] - b[0]) * 100, 0.4),
    height: Math.max(Math.abs(a[1] - b[1]) * 100, 0.4)
  }
})

function clearRoi() {
  // Invalidate any measurement still in flight: its response must never
  // paint into a cleared or switched-away panel.
  statsToken.value++
  roiRect.value = null
  roiStats.value = null
  roiError.value = null
}

async function measure() {
  const rect = roiRect.value
  const a = rect?.[0]
  const b = rect?.[1] ?? a
  if (!a || !b) return
  roiError.value = null
  roiStats.value = null
  const token = ++statsToken.value
  try {
    const res = await fetchRoiStats(
      props.studyId,
      Math.min(a[0], b[0]),
      Math.min(a[1], b[1]),
      Math.max(a[0], b[0]),
      Math.max(a[1], b[1])
    )
    if (token === statsToken.value) roiStats.value = res
  } catch (error: unknown) {
    if (token === statsToken.value) {
      // errorToast is false on this call, so the backend's own reason
      // (the render's refusal with its remedy) surfaces here.
      roiError.value = errorDetail(error) ?? t('imagingViewer.annotations.statsFailed')
    }
  }
}

function toggleStats() {
  if (tool.value === 'stats') {
    tool.value = null
    clearRoi()
  } else {
    tool.value = 'stats'
    clearRoi()
  }
}

watch(tool, (current) => {
  if (current !== 'stats') clearRoi()
})

async function save(kind: 'ruler' | 'freehand' | 'note', points: Array<[number, number]>, text?: string) {
  actionError.value = null
  try {
    await createAnnotation(props.studyId, kind, points, text)
    tool.value = null
    noteAt.value = null
    noteText.value = ''
    await load()
  } catch {
    actionError.value = t('imagingViewer.annotations.actionFailed')
  }
}

async function remove(id: string) {
  actionError.value = null
  try {
    await deleteAnnotation(id)
    await load()
  } catch {
    actionError.value = t('imagingViewer.annotations.actionFailed')
  }
}

function mmLabel(a: StudyAnnotation) {
  const mm = (a.payload as { mm?: number }).mm
  return typeof mm === 'number' ? t('imagingViewer.annotations.mm', { mm }) : t('imagingViewer.annotations.noSpacing')
}

watch(() => props.studyId, () => {
  tool.value = null
  draft.value = []
  noteAt.value = null
  void load()
  void loadRender()
})
</script>

<template>
  <UCard>
    <template #header>
      <div class="flex flex-wrap items-center justify-between gap-2">
        <span class="font-medium">{{ t('imagingViewer.annotations.title') }}</span>
        <div class="flex gap-2">
          <UButton
            size="sm"
            :variant="tool === 'stats' ? 'solid' : 'soft'"
            icon="i-lucide-scan-search"
            @click="toggleStats"
          >
            {{ t('imagingViewer.annotations.stats') }}
          </UButton>
          <template v-if="canWrite">
            <UButton
              size="sm"
              :variant="tool === 'ruler' ? 'solid' : 'soft'"
              icon="i-lucide-ruler"
              @click="tool = tool === 'ruler' ? null : 'ruler'"
            >
              {{ t('imagingViewer.annotations.ruler') }}
            </UButton>
            <UButton
              size="sm"
              :variant="tool === 'freehand' ? 'solid' : 'soft'"
              icon="i-lucide-pen-line"
              @click="tool = tool === 'freehand' ? null : 'freehand'"
            >
              {{ t('imagingViewer.annotations.freehand') }}
            </UButton>
            <UButton
              size="sm"
              :variant="tool === 'note' ? 'solid' : 'soft'"
              icon="i-lucide-sticky-note"
              @click="tool = tool === 'note' ? null : 'note'"
            >
              {{ t('imagingViewer.annotations.note') }}
            </UButton>
          </template>
        </div>
      </div>
    </template>
    <UAlert
      v-if="shownError"
      color="error"
      :title="shownError"
    />
    <div class="relative select-none">
      <img
        v-if="renderBlobUrl"
        :src="renderBlobUrl"
        class="w-full rounded"
        alt=""
        draggable="false"
      >
      <div
        v-else
        class="flex h-32 flex-col items-center justify-center gap-1 rounded bg-gray-100 px-4 text-center"
      >
        <p class="text-sm font-medium text-gray-600">
          {{ t('imagingViewer.viewer.unavailable') }}
        </p>
        <p class="text-xs text-gray-500">
          {{ t('imagingViewer.viewer.fallbackHint') }}
        </p>
      </div>
      <svg
        ref="svgEl"
        class="absolute inset-0 h-full w-full touch-none"
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        @pointerdown="onPointerDown"
        @pointermove="onPointerMove"
        @pointerup="onPointerUp"
      >
        <g
          v-for="a in annotations"
          :key="a.id"
        >
          <line
            v-if="a.kind === 'ruler'"
            :x1="(a.payload.points[0]?.[0] as number) * 100"
            :y1="(a.payload.points[0]?.[1] as number) * 100"
            :x2="(a.payload.points[1]?.[0] as number) * 100"
            :y2="(a.payload.points[1]?.[1] as number) * 100"
            stroke="#22c55e"
            stroke-width="0.6"
            vector-effect="non-scaling-stroke"
          />
          <polyline
            v-else-if="a.kind === 'freehand'"
            :points="(a.payload.points as Array<[number, number]>).map((p) => `${p[0] * 100},${p[1] * 100}`).join(' ')"
            fill="none"
            stroke="#3b82f6"
            stroke-width="2"
            vector-effect="non-scaling-stroke"
          />
          <circle
            v-else
            :cx="(a.payload.points[0]?.[0] as number) * 100"
            :cy="(a.payload.points[0]?.[1] as number) * 100"
            r="1.2"
            fill="#f59e0b"
          />
        </g>
        <rect
          v-if="statsRectAttrs"
          :x="statsRectAttrs.x"
          :y="statsRectAttrs.y"
          :width="statsRectAttrs.width"
          :height="statsRectAttrs.height"
          fill="rgba(245, 158, 11, 0.15)"
          stroke="#f59e0b"
          stroke-width="0.6"
          stroke-dasharray="2 1"
          vector-effect="non-scaling-stroke"
        />
      </svg>
    </div>
    <div
      v-if="tool === 'stats'"
      class="mt-2"
    >
      <UAlert
        v-if="roiError"
        color="warning"
        :title="roiError"
      />
      <p
        v-else-if="!roiStats"
        class="text-xs text-gray-500"
      >
        {{ t('imagingViewer.annotations.statsHint') }}
      </p>
      <div
        v-else
        class="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm"
      >
        <span>
          {{ t('imagingViewer.annotations.statsMean') }}:
          <span class="font-medium">{{ roiStats.mean.toFixed(2) }}</span>
        </span>
        <span>
          {{ t('imagingViewer.annotations.statsStd') }}:
          <span class="font-medium">{{ roiStats.std.toFixed(2) }}</span>
        </span>
        <span>
          {{ t('imagingViewer.annotations.statsMin') }}:
          <span class="font-medium">{{ roiStats.min.toFixed(2) }}</span>
        </span>
        <span>
          {{ t('imagingViewer.annotations.statsMax') }}:
          <span class="font-medium">{{ roiStats.max.toFixed(2) }}</span>
        </span>
        <span>
          {{ t('imagingViewer.annotations.statsCount') }}:
          <span class="font-medium">{{ roiStats.count }}</span>
        </span>
      </div>
    </div>
    <div
      v-if="noteAt && tool === 'note'"
      class="mt-2 flex gap-2"
    >
      <UInput
        v-model="noteText"
        :placeholder="t('imagingViewer.annotations.notePlaceholder')"
        class="flex-1"
      />
      <UButton
        :disabled="!noteText.trim()"
        @click="save('note', [noteAt], noteText)"
      >
        {{ t('imagingViewer.annotations.saveNote') }}
      </UButton>
    </div>
    <ul class="mt-2 flex flex-col gap-1">
      <li
        v-for="a in annotations"
        :key="a.id"
        class="flex items-center justify-between gap-2 text-sm"
      >
        <span>
          {{ t(`imagingViewer.annotations.kind_${a.kind}`) }}
          <span
            v-if="a.kind === 'ruler'"
            class="text-gray-500"
          > — {{ mmLabel(a) }}</span>
          <span
            v-if="a.kind === 'note'"
            class="text-gray-500"
          > — {{ (a.payload as { text?: string }).text }}</span>
        </span>
        <UButton
          v-if="canWrite"
          size="xs"
          color="error"
          variant="soft"
          icon="i-lucide-trash-2"
          :aria-label="t('imagingViewer.annotations.deleteLabel')"
          @click="remove(a.id)"
        />
      </li>
    </ul>
    <p class="mt-2 text-xs text-gray-500">
      {{ t('imagingViewer.annotations.aidNote') }}
    </p>
  </UCard>
</template>
