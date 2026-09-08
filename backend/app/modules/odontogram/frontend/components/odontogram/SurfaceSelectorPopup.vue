<script setup lang="ts">
import type { Surface, TreatmentStatus, TreatmentType } from '~~/app/types'
import { getOcclusalPath, getLateralPath, isUpperTooth, getToothTransform, TREATMENT_COLORS } from './ToothSVGPaths'
import { getToothNameKey, getToothPositionKeys } from '~~/app/config/odontogramConstants'

const props = defineProps<{
  open: boolean
  toothNumber: number
  treatmentType: TreatmentType
  status: TreatmentStatus
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'confirm': [surfaces: Surface[]]
  'cancel': []
}>()

const { t } = useI18n()

// Selected surfaces
const selectedSurfaces = ref<Surface[]>([])

// All surfaces
const allSurfaces: Surface[] = ['M', 'D', 'O', 'V', 'L']

// Get paths for the tooth
const occlusalPaths = computed(() => getOcclusalPath(props.toothNumber))
const lateralPaths = computed(() => getLateralPath(props.toothNumber))
const _isUpper = computed(() => isUpperTooth(props.toothNumber))
const toothTransform = computed(() => getToothTransform(props.toothNumber))

// Determine quadrant for symmetry
const quadrant = computed(() => Math.floor(props.toothNumber / 10))

// Check if the tooth is on the left side (quadrants 2, 3, 6, 7)
// For left side teeth, the tooth shape should be mirrored horizontally
// so that M (mesial) appears on the correct side relative to midline
const isLeftSide = computed(() => [2, 3, 6, 7].includes(quadrant.value))

// Check if the tooth is on the lower arch (quadrants 3, 4, 7, 8)
// For lower teeth, the tooth shape should be mirrored vertically
// so that V (vestibular) appears at the bottom and L (lingual) at the top
const isLower = computed(() => [3, 4, 7, 8].includes(quadrant.value))

// Build the transform string for the occlusal view based on quadrant
const occlusalGroupTransform = computed(() => {
  const transforms: string[] = []

  // Apply horizontal flip for left-side teeth
  if (isLeftSide.value) {
    transforms.push('translate(50, 0) scale(-1, 1)')
  }

  // Apply vertical flip for lower teeth
  if (isLower.value) {
    // If already horizontally flipped, we need to adjust
    if (isLeftSide.value) {
      // Reset and apply both flips: scale(-1, -1) centered
      return 'translate(50, 50) scale(-1, -1)'
    } else {
      transforms.push('translate(0, 50) scale(1, -1)')
    }
  }

  return transforms.join(' ')
})

// Get correct X position for M label based on quadrant
// M (mesial) is always toward midline: left side of view for right teeth, right side for left teeth
const mLabelX = computed(() => isLeftSide.value ? 43 : 4)
// Get correct X position for D label based on quadrant
const dLabelX = computed(() => isLeftSide.value ? 4 : 43)

// Get correct Y position for V label based on arch
// V (vestibular) faces outward: top for upper teeth, bottom for lower teeth
const vLabelY = computed(() => isLower.value ? 47 : 8)
// Get correct Y position for L label based on arch
// L (lingual) faces inward: bottom for upper teeth, top for lower teeth
const lLabelY = computed(() => isLower.value ? 8 : 47)
const toothName = computed(() => {
  const nameKey = getToothNameKey(props.toothNumber)
  const positionKeys = getToothPositionKeys(props.toothNumber)
  return `${t(nameKey)} ${t(positionKeys.vertical)} ${t(positionKeys.horizontal)}`
})

// Lateral view dimensions from viewBox
// Crop viewBox to crown + gum area only (hide root and root canal)
// to keep the popup compact.
const CROWN_TOP_PADDING = 6
const CROWN_BOTTOM_PADDING = 4
const lateralViewBox = computed(() => {
  const vb = lateralPaths.value.viewBox.split(' ').map(Number)
  const vbWidth = vb[2] || 60
  const vbHeight = vb[3] || 100

  // gumLine format: "M 0,<y> Q ..." — y marks top of the crown
  const match = lateralPaths.value.gumLine.match(/M\s*\d+(?:\.\d+)?\s*,\s*(\d+(?:\.\d+)?)/)
  const gumY = match && match[1] ? parseFloat(match[1]) : vbHeight * 0.65

  const cropY = Math.max(0, gumY - CROWN_TOP_PADDING)
  const cropH = vbHeight - cropY + CROWN_BOTTOM_PADDING
  return `0 ${cropY} ${vbWidth} ${cropH}`
})
const lateralDimensions = computed(() => {
  const vb = lateralViewBox.value.split(' ').map(Number)
  const vbWidth = vb[2] || 60
  const vbHeight = vb[3] || 100
  const aspectRatio = vbWidth / vbHeight

  // Keep display width at 160px for the popup
  const displayWidth = 160
  const displayHeight = Math.round(displayWidth / aspectRatio)

  return { displayWidth, displayHeight }
})

// Treatment color
const treatmentColor = computed(() => TREATMENT_COLORS[props.treatmentType] || '#3B82F6')

// Toggle surface selection
function toggleSurface(surface: Surface) {
  const index = selectedSurfaces.value.indexOf(surface)
  if (index >= 0) {
    selectedSurfaces.value.splice(index, 1)
  } else {
    selectedSurfaces.value.push(surface)
  }
}

// Check if surface is selected
function isSurfaceSelected(surface: Surface): boolean {
  return selectedSurfaces.value.includes(surface)
}

// Get surface fill color
function getSurfaceFill(surface: Surface): string {
  if (isSurfaceSelected(surface)) {
    if (props.status === 'planned') {
      return 'url(#surface-pattern)'
    }
    return treatmentColor.value
  }
  return 'var(--odontogram-fill, #FFFFFF)'
}

// Get surface opacity
function getSurfaceOpacity(surface: Surface): number {
  return isSurfaceSelected(surface) ? 0.8 : 1
}

// Confirm selection
function handleConfirm() {
  if (selectedSurfaces.value.length > 0) {
    emit('confirm', [...selectedSurfaces.value])
  }
  selectedSurfaces.value = []
  emit('update:open', false)
}

// Cancel selection
function handleCancel() {
  selectedSurfaces.value = []
  emit('cancel')
  emit('update:open', false)
}

// Reset when opening
watch(() => props.open, (isOpen) => {
  if (isOpen) {
    selectedSurfaces.value = []
  }
})
</script>

<template>
  <UModal
    :open="open"
    @update:open="handleCancel"
  >
    <template #header>
      <div class="flex items-center gap-3">
        <div
          class="w-8 h-8 rounded-lg flex items-center justify-center"
          :style="{ backgroundColor: treatmentColor + '20' }"
        >
          <div
            class="w-3 h-3 rounded-full"
            :style="{ backgroundColor: treatmentColor }"
          />
        </div>
        <div>
          <h3 class="text-base font-semibold">
            {{ t('odontogram.selectSurfaces') }}
          </h3>
          <p class="text-caption text-subtle">
            {{ t(`odontogram.treatments.types.${treatmentType}`) }} - {{ t('odontogram.tooth') }} {{ toothNumber }}
          </p>
        </div>
      </div>
    </template>

    <template #body>
      <div class="surface-selector">
        <!-- Tooth visualization -->
        <div class="tooth-views">
          <!-- Occlusal View -->
          <div class="view-container">
            <div class="view-label">
              {{ t('odontogram.views.occlusal') }}
            </div>
            <svg
              width="160"
              height="160"
              viewBox="0 0 50 50"
              class="tooth-svg"
            >
              <!-- Pattern definition -->
              <defs>
                <clipPath :id="`occlusal-surface-clip-${toothNumber}`">
                  <path :d="occlusalPaths.outline" />
                </clipPath>
                <pattern
                  id="surface-pattern"
                  patternUnits="userSpaceOnUse"
                  width="4"
                  height="4"
                  patternTransform="rotate(45)"
                >
                  <line
                    x1="0"
                    y1="0"
                    x2="0"
                    y2="4"
                    :stroke="treatmentColor"
                    stroke-width="2"
                  />
                </pattern>
              </defs>

              <!-- Tooth paths group with transform for quadrant symmetry -->
              <g :transform="occlusalGroupTransform">
                <!-- Outline (fill under, stroke redrawn after surfaces) -->
                <path
                  :d="occlusalPaths.outline"
                  fill="var(--odontogram-fill-shade)"
                  stroke="none"
                />

                <!-- Surfaces (clickable), clipped so silhouette stays anatomical -->
                <g :clip-path="`url(#occlusal-surface-clip-${toothNumber})`">
                  <path
                    v-for="(path, surface) in occlusalPaths.surfaces"
                    :key="surface"
                    :d="path"
                    :fill="getSurfaceFill(surface as Surface)"
                    :opacity="getSurfaceOpacity(surface as Surface)"
                    :stroke="isSurfaceSelected(surface as Surface) ? treatmentColor : 'var(--odontogram-outline-light)'"
                    :stroke-width="isSurfaceSelected(surface as Surface) ? 2 : 0.5"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    class="surface-path"
                    @click="toggleSurface(surface as Surface)"
                  />
                </g>

                <!-- Highlight details (fissures) — drawn after fills so they remain visible -->
                <g
                  :clip-path="`url(#occlusal-surface-clip-${toothNumber})`"
                  pointer-events="none"
                >
                  <path
                    v-for="(highlightPath, idx) in occlusalPaths.highlight"
                    :key="`occlusal-highlight-${idx}`"
                    :d="highlightPath"
                    fill="none"
                    stroke="var(--odontogram-detail)"
                    stroke-width="0.75"
                    stroke-linecap="round"
                  />
                </g>

                <!-- Crisp outline on top so the anatomical edge is never covered -->
                <path
                  :d="occlusalPaths.outline"
                  fill="none"
                  stroke="var(--odontogram-outline)"
                  stroke-width="1.25"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  pointer-events="none"
                />
              </g>

              <!-- Surface labels (outside transform to remain readable) -->
              <text
                :x="mLabelX"
                y="27"
                class="surface-label"
                @click="toggleSurface('M')"
              >M</text>
              <text
                :x="dLabelX"
                y="27"
                class="surface-label"
                @click="toggleSurface('D')"
              >D</text>
              <text
                x="24"
                :y="vLabelY"
                class="surface-label"
                @click="toggleSurface('V')"
              >V</text>
              <text
                x="24"
                :y="lLabelY"
                class="surface-label"
                @click="toggleSurface('L')"
              >L</text>
              <text
                x="24"
                y="28"
                class="surface-label-center"
                @click="toggleSurface('O')"
              >O</text>
            </svg>
          </div>

          <!-- Lateral View -->
          <div class="view-container">
            <div class="view-label">
              {{ t('odontogram.views.lateral') }}
            </div>
            <svg
              :width="lateralDimensions.displayWidth"
              :height="lateralDimensions.displayHeight"
              :viewBox="lateralViewBox"
              class="tooth-svg lateral"
              :style="{ transform: toothTransform, transformOrigin: 'center center' }"
            >
              <!-- Gum line -->
              <path
                :d="lateralPaths.gumLine"
                fill="none"
                stroke="var(--odontogram-gum)"
                stroke-width="1.5"
              />

              <!-- Crown -->
              <path
                :d="lateralPaths.crown"
                fill="var(--odontogram-fill)"
                stroke="var(--odontogram-outline)"
                stroke-width="1.25"
                stroke-linecap="round"
                stroke-linejoin="round"
              />

              <!-- Highlight details -->
              <path
                v-for="(highlightPath, idx) in lateralPaths.highlight"
                :key="`highlight-${idx}`"
                :d="highlightPath"
                fill="none"
                stroke="var(--odontogram-detail)"
                stroke-width="0.75"
                stroke-linecap="round"
              />
            </svg>
          </div>
        </div>

        <!-- Surface buttons -->
        <div class="surface-buttons">
          <button
            v-for="surface in allSurfaces"
            :key="surface"
            type="button"
            class="surface-btn"
            :class="{ selected: isSurfaceSelected(surface) }"
            :style="isSurfaceSelected(surface) ? { borderColor: treatmentColor, backgroundColor: treatmentColor + '15' } : {}"
            @click="toggleSurface(surface)"
          >
            <span class="surface-letter">{{ surface }}</span>
            <span class="surface-name">{{ t(`odontogram.surfaces.${surface}`) }}</span>
          </button>
        </div>

        <!-- Selected surfaces summary -->
        <div
          v-if="selectedSurfaces.length > 0"
          class="selected-summary"
        >
          <span class="summary-label">{{ t('odontogram.selectedSurfaces') }}:</span>
          <div class="summary-badges">
            <span
              v-for="surface in selectedSurfaces"
              :key="surface"
              class="summary-badge"
              :style="{ backgroundColor: treatmentColor + '20', color: treatmentColor }"
            >
              {{ surface }} - {{ t(`odontogram.surfaces.${surface}`) }}
            </span>
          </div>
        </div>

        <!-- Tooth info -->
        <div class="tooth-info">
          <UIcon
            name="i-lucide-info"
            class="w-4 h-4"
          />
          <span>{{ toothName }}</span>
        </div>
      </div>
    </template>

    <template #footer>
      <div class="flex justify-between items-center w-full">
        <span class="text-caption text-subtle">
          {{ selectedSurfaces.length }} {{ t('odontogram.surfacesSelected') }}
        </span>
        <div class="flex gap-2">
          <UButton
            color="neutral"
            variant="ghost"
            @click="handleCancel"
          >
            {{ t('common.cancel') }}
          </UButton>
          <UButton
            color="primary"
            :disabled="selectedSurfaces.length === 0"
            @click="handleConfirm"
          >
            {{ t('common.confirm') }}
          </UButton>
        </div>
      </div>
    </template>
  </UModal>
</template>

<style scoped>
.surface-selector {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.tooth-views {
  display: flex;
  justify-content: center;
  gap: 32px;
}

.view-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.view-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--color-gray-500);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.tooth-svg {
  background: var(--odontogram-bg);
  border-radius: 12px;
  padding: 8px;
}

.tooth-svg.lateral {
  transform-origin: center;
}

.surface-path {
  cursor: pointer;
  transition: all 0.15s ease;
}

.surface-path:hover {
  filter: brightness(0.95);
}

.surface-label,
.surface-label-center {
  font-size: 6px;
  font-weight: 600;
  fill: #6B7280;
  text-anchor: middle;
  cursor: pointer;
  user-select: none;
}

.surface-label-center {
  fill: #9CA3AF;
}

/* Surface buttons */
.surface-buttons {
  display: flex;
  justify-content: center;
  gap: 8px;
  flex-wrap: wrap;
}

.surface-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 12px 16px;
  border: 2px solid #E5E7EB;
  border-radius: 10px;
  background: white;
  transition: all 0.15s ease;
  min-width: 80px;
}

:root.dark .surface-btn {
  background: #27272A;
  border-color: #3F3F46;
}

.surface-btn:hover {
  border-color: #93C5FD;
  transform: translateY(-1px);
}

.surface-btn.selected {
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
}

.surface-letter {
  font-size: 18px;
  font-weight: 700;
  color: #374151;
}

:root.dark .surface-letter {
  color: #E5E7EB;
}

.surface-name {
  font-size: 11px;
  color: #6B7280;
}

/* Selected summary */
.selected-summary {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  background: #F9FAFB;
  border-radius: 8px;
}

:root.dark .selected-summary {
  background: #27272A;
}

.summary-label {
  font-size: 12px;
  font-weight: 500;
  color: #6B7280;
}

.summary-badges {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.summary-badge {
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
}

/* Tooth info */
.tooth-info {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-size: 13px;
  color: #6B7280;
  padding: 8px;
  background: #F4F4F5;
  border-radius: 6px;
}

:root.dark .tooth-info {
  background: #27272A;
  color: #A1A1AA;
}
</style>
