<script setup lang="ts">
/**
 * Human annotation overlays for one study (T2): ruler (mm when the study
 * carries pixel spacing), freehand drawing, text notes. Coordinates are
 * stored normalized 0-1; the original bytes are never touched. Overlays are
 * visualization aids, never diagnoses.
 */
import { useImagingViewer, type StudyAnnotation } from '../composables/useImagingViewer'
import { PERMISSIONS } from '~~/app/config/permissions'

const props = defineProps<{ studyId: string }>()

const { t } = useI18n()
const { can } = usePermissions()
const { frameUrl, fetchAnnotations, createAnnotation, deleteAnnotation } = useImagingViewer()

const annotations = ref<StudyAnnotation[]>([])
const tool = ref<'ruler' | 'freehand' | 'note' | null>(null)
const draft = ref<Array<[number, number]>>([])
const drawing = ref(false)
const noteText = ref('')
const noteAt = ref<[number, number] | null>(null)
const actionError = ref<string | null>(null)
const svgEl = ref<SVGSVGElement | null>(null)

const canWrite = computed(() => can(PERMISSIONS.imagingViewer.studies.write))

async function load() {
  actionError.value = null
  try {
    annotations.value = await fetchAnnotations(props.studyId)
  } catch {
    actionError.value = t('imagingViewer.annotations.loadFailed')
  }
}

function toNorm(e: PointerEvent): [number, number] {
  const rect = (svgEl.value as SVGSVGElement).getBoundingClientRect()
  const x = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width))
  const y = Math.min(1, Math.max(0, (e.clientY - rect.top) / rect.height))
  return [x, y]
}

function onPointerDown(e: PointerEvent) {
  if (!tool.value || !canWrite.value) return
  const p = toNorm(e)
  if (tool.value === 'note') {
    noteAt.value = p
    return
  }
  drawing.value = true
  draft.value = [p]
}

function onPointerMove(e: PointerEvent) {
  if (!drawing.value || tool.value !== 'freehand') return
  draft.value = [...draft.value, toNorm(e)]
}

async function onPointerUp(e: PointerEvent) {
  if (!drawing.value) return
  drawing.value = false
  if (tool.value === 'freehand') {
    await save('freehand', draft.value)
  } else if (tool.value === 'ruler') {
    draft.value = [...draft.value, toNorm(e)]
    if (draft.value.length >= 2) await save('ruler', draft.value.slice(0, 2))
  }
  draft.value = []
}

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
  load()
})
onMounted(load)
</script>

<template>
  <UCard>
    <template #header>
      <div class="flex flex-wrap items-center justify-between gap-2">
        <span class="font-medium">{{ t('imagingViewer.annotations.title') }}</span>
        <div
          v-if="canWrite"
          class="flex gap-2"
        >
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
        </div>
      </div>
    </template>
    <UAlert
      v-if="actionError"
      color="error"
      :title="actionError"
    />
    <div class="relative select-none">
      <img
        :src="frameUrl(studyId)"
        class="w-full rounded"
        alt=""
        draggable="false"
      >
      <svg
        ref="svgEl"
        class="absolute inset-0 h-full w-full"
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
      </svg>
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
          @click="remove(a.id)"
        />
      </li>
    </ul>
    <p class="mt-2 text-xs text-gray-500">
      {{ t('imagingViewer.annotations.aidNote') }}
    </p>
  </UCard>
</template>
