<script setup lang="ts">
import type { Surface, ToothTreatmentView, TreatmentStatus } from '~~/app/types'
import {
  getOcclusalPath,
  getOcclusalSurfaceCenter,
  getLateralPath,
  getToothTransform,
  getToothDisplayConfig,
  isUpperTooth,
  isDeciduousTooth,
  PATTERN_DEFINITIONS,
  STATUS_STYLES,
  TREATMENT_COLORS,
  TREATMENT_OVERLAYS,
  makesToothTransparent,
  getIconAnchors,
  getPatternId
} from './ToothSVGPaths'
import {
  getToothNameKey,
  getToothPositionKeys,
  hasVisualizationRule,
  PULP_FILL_CONFIG,
  OCCLUSAL_VISUALIZATION,
  PATTERN_CONFIG,
  normalizeTreatmentType,
  getTreatmentColor
} from '~~/app/config/odontogramConstants'
// Note: Icon rendering uses inline SVG elements based on treatment type, not LATERAL_ICONS directly
import ImplantSVG from './ImplantSVG.vue'

const props = defineProps<{
  toothNumber: number
  generalCondition: string
  treatments?: ToothTreatmentView[]
  readonly?: boolean
  selected?: boolean
  showLateral?: boolean
  isDisplaced?: boolean
  isRotated?: boolean
  isHovered?: boolean
  isHighlighted?: boolean
  pendingTreatment?: { type: string, status: TreatmentStatus } | null
}>()

const emit = defineEmits<{
  surfaceClick: [surface: Surface]
  toothClick: []
  treatmentClick: [treatment: ToothTreatmentView]
}>()

const { t } = useI18n()

const isUpper = computed(() => isUpperTooth(props.toothNumber))
const isDeciduous = computed(() => isDeciduousTooth(props.toothNumber))
const occlusalPaths = computed(() => getOcclusalPath(props.toothNumber))
const lateralPaths = computed(() => getLateralPath(props.toothNumber))

// Quadrant-based transform for symmetry (napkin unfolding)
const toothTransform = computed(() => getToothTransform(props.toothNumber))

// Lateral view: use the viewBox from the tooth paths (dynamic per tooth type)
const lateralViewBox = computed(() => lateralPaths.value.viewBox)

// Get display configuration for this tooth (scale and alignment)
const displayConfig = computed(() => getToothDisplayConfig(props.toothNumber))

// Parse viewBox dimensions and calculate display size with proper scaling
const lateralDimensions = computed(() => {
  const vb = lateralViewBox.value.split(' ').map(Number)
  const vbWidth = vb[2] || 60
  const vbHeight = vb[3] || 130
  const aspectRatio = vbWidth / vbHeight

  // Base display width, adjusted by scale factor
  const baseWidth = 55
  const displayWidth = Math.round(baseWidth * displayConfig.value.scale)
  const displayHeight = Math.round(displayWidth / aspectRatio)

  return { displayWidth, displayHeight }
})
const lateralDisplayWidth = computed(() => lateralDimensions.value.displayWidth)
const lateralDisplayHeight = computed(() => lateralDimensions.value.displayHeight)

const _toothName = computed(() => {
  const nameKey = getToothNameKey(props.toothNumber)
  const positionKeys = getToothPositionKeys(props.toothNumber)
  return `${t(nameKey)} ${t(positionKeys.vertical)} ${t(positionKeys.horizontal)}`
})

// A prosthetic replacement (implant, bridge, crown, pontic, abutment,
// overlay, inlay, unerupted) supersedes the "missing/extracted" state:
// the tooth is functionally present again, so its anatomy should not
// be faded under the restoration.
const hasReplacementTreatment = computed(() => {
  return props.treatments?.some(t =>
    t.treatment_type === 'implant'
    || t.treatment_type === 'bridge'
    || t.treatment_type === 'crown_on_implant'
    || t.treatment_type === 'provisional_crown_on_implant'
    || hasVisualizationRule(t.treatment_type, 'pattern_fill')
  ) || false
})

// Check if tooth should be transparent (extracted/missing without a
// prosthetic replacement).
const isToothTransparent = computed(() => {
  if (hasReplacementTreatment.value) return false
  if (props.generalCondition === 'missing' || props.generalCondition === 'extraction_indicated') {
    return true
  }
  return props.treatments?.some(t =>
    makesToothTransparent(t.treatment_type) && t.status === 'existing'
  ) || false
})

const toothOpacity = computed(() => {
  if (isToothTransparent.value) return 0.25
  return 1
})

function handleToothClick() {
  emit('toothClick')
}

const toothTreatments = computed(() => props.treatments || [])

// Check if tooth has an implant (roots should be hidden)
const hasImplantTreatment = computed(() => {
  return toothTreatments.value.some(t => t.treatment_type === 'implant')
})

// Treatments that paint the lateral crown with a solid prosthetic fill
// (instead of relying on the pattern_fill rule). Bridges and crowns on
// implants share this rendering because the result looks closer to the
// real metal-ceramic / prosthetic finish.
const SOLID_CROWN_FILL_TYPES = ['bridge', 'crown_on_implant', 'provisional_crown_on_implant'] as const

// Bridge treatment on this tooth (clinical_type === 'bridge').
// Roles come from the per-tooth membership: 'pillar' | 'pontic' | null.
const bridgeTreatment = computed(() => {
  return toothTreatments.value.find(t => t.treatment_type === 'bridge')
})

// Pontic teeth have no root: the natural tooth is missing and the prosthetic
// pontic floats between the two abutments.
const isBridgePontic = computed(() => bridgeTreatment.value?.role === 'pontic')

// Generic prosthetic crown fill (bridge OR crown-on-implant variants
// share the same lateral-crown solid render).
const crownFillTreatment = computed(() => {
  return toothTreatments.value.find(t =>
    (SOLID_CROWN_FILL_TYPES as readonly string[]).includes(t.treatment_type)
  )
})

const hasCrownFillTreatment = computed(() => crownFillTreatment.value !== undefined)

const crownFillColor = computed(() => {
  if (!crownFillTreatment.value) return 'none'
  return getTreatmentColor(crownFillTreatment.value.treatment_type)
})

const crownFillOpacity = computed(() => {
  if (!crownFillTreatment.value) return 0
  return STATUS_STYLES[crownFillTreatment.value.status]?.opacity ?? 1
})

function hasTreatment(type: string, status?: TreatmentStatus): boolean {
  return toothTreatments.value.some(t =>
    t.treatment_type === type && (status === undefined || t.status === status)
  )
}

function getTreatmentOfType(type: string): ToothTreatmentView | undefined {
  return toothTreatments.value.find(t => t.treatment_type === type)
}

function getImplantFill(_treatment: ToothTreatmentView): string {
  return TREATMENT_COLORS.implant || '#10B981'
}

// ============================================================================
// Visualization Rule Logic
// ============================================================================

// Rule 1: Pulp fill treatments (lateral view)
const pulpFillTreatments = computed(() => {
  return toothTreatments.value.filter(t =>
    hasVisualizationRule(t.treatment_type, 'pulp_fill')
  )
})

const hasPulpTreatment = computed(() => pulpFillTreatments.value.length > 0)

// Get the primary pulp treatment (first one with pulp_fill rule)
function getPulpTreatment(): ToothTreatmentView | undefined {
  return pulpFillTreatments.value[0]
}

// Get the pulp fill level ('full', 'two_thirds', 'half')
const pulpFillLevel = computed(() => {
  const treatment = getPulpTreatment()
  if (!treatment) return 'full'
  const normalized = normalizeTreatmentType(treatment.treatment_type)
  const config = PULP_FILL_CONFIG[normalized]
  return config?.level || 'full'
})

// Always use the full pulp path - clipping handles partial fills
function getPulpFillPath(): string | undefined {
  return lateralPaths.value.pulp
}

// Get fill color for pulp based on treatment
function getPulpFillColor(): string {
  const treatment = getPulpTreatment()
  if (!treatment) return 'none'
  const normalized = normalizeTreatmentType(treatment.treatment_type)
  const config = PULP_FILL_CONFIG[normalized]
  return config?.color || getTreatmentColor(treatment.treatment_type)
}

// Get fill opacity for pulp based on treatment status
function getPulpFillOpacity(): number {
  const treatment = getPulpTreatment()
  if (!treatment) return 0
  return STATUS_STYLES[treatment.status]?.opacity ?? 1
}

// Unique clip-path ID for this tooth
const pulpClipId = computed(() => `pulp-clip-${props.toothNumber}`)

// Parse viewBox to get dimensions for clip-path calculation
const viewBoxDimensions = computed(() => {
  const vb = lateralViewBox.value.split(' ').map(Number)
  return {
    x: vb[0] || 0,
    y: vb[1] || 0,
    width: vb[2] || 60,
    height: vb[3] || 130
  }
})

// Calculate clip-path Y offset and height based on fill level
// In the SVG, crown is at the BOTTOM (higher Y values), roots at TOP (lower Y values)
// So we clip from the TOP to hide the root portion and show the crown portion
const pulpClipY = computed(() => {
  const { y, height } = viewBoxDimensions.value
  switch (pulpFillLevel.value) {
    case 'half': return y + height * 0.35 // Start at 50% down (show bottom 50%)
    case 'two_thirds': return y + height * 0.2 // Start at 30% down (show bottom 70%)
    default: return y
  }
})

const pulpClipHeight = computed(() => {
  const { height } = viewBoxDimensions.value
  switch (pulpFillLevel.value) {
    case 'half': return height * 0.5 // Show bottom 50%
    case 'two_thirds': return height * 0.7 // Show bottom 70%
    default: return height
  }
})

// Check if we need a clip-path (only for partial fills)
const needsPulpClip = computed(() => {
  return pulpFillLevel.value !== 'full'
})

// Rule 2: Occlusal surface treatments (cenital view)
const occlusalSurfaceTreatments = computed(() => {
  return toothTreatments.value.filter(t =>
    hasVisualizationRule(t.treatment_type, 'occlusal_surface')
  )
})

// Get occlusal visualization config for a treatment
function getOcclusalConfig(treatment: ToothTreatmentView) {
  const normalized = normalizeTreatmentType(treatment.treatment_type)
  return OCCLUSAL_VISUALIZATION[normalized]
}

// Rule 3: Lateral icon treatments (lateral view)
const lateralIconTreatments = computed(() => {
  return toothTreatments.value.filter(t =>
    hasVisualizationRule(t.treatment_type, 'lateral_icon')
    && t.treatment_type !== 'implant' // Implant is handled separately by ImplantSVG
  )
})

// Get icon anchors for this tooth
const iconAnchors = computed(() => getIconAnchors(props.toothNumber))

// Rule 4: Pattern fill treatments (cenital view)
const patternFillTreatments = computed(() => {
  return toothTreatments.value.filter(t =>
    hasVisualizationRule(t.treatment_type, 'pattern_fill')
  )
})

// Get pattern config for a treatment (available for future use)
function _getPatternConfig(treatment: ToothTreatmentView) {
  const normalized = normalizeTreatmentType(treatment.treatment_type)
  return PATTERN_CONFIG[normalized]
}

const showingPreview = computed(() => props.isHovered && props.pendingTreatment)

// Check if there are planned treatments visible in occlusal view
const hasPlannedOcclusalTreatments = computed(() => {
  return toothTreatments.value.some(t =>
    t.status === 'planned' && (
      hasVisualizationRule(t.treatment_type, 'occlusal_surface')
      || hasVisualizationRule(t.treatment_type, 'pattern_fill')
    )
  )
})

// Check if there are planned treatments visible in lateral view
const hasPlannedLateralTreatments = computed(() => {
  return toothTreatments.value.some(t =>
    t.status === 'planned' && (
      hasVisualizationRule(t.treatment_type, 'pulp_fill')
      || hasVisualizationRule(t.treatment_type, 'lateral_icon')
    )
  )
})
</script>

<template>
  <div
    class="tooth-dual-view-wrapper"
    :class="{
      'selected': selected,
      'readonly': readonly,
      'displaced': isDisplaced,
      'rotated': isRotated,
      'highlighted': isHighlighted,
      'has-preview': showingPreview,
      'is-upper': isUpper,
      'is-lower': !isUpper,
      'is-deciduous': isDeciduous
    }"
    @click="handleToothClick"
  >
    <!-- Lateral View Container - fixed height for alignment -->
    <div
      v-if="showLateral"
      class="lateral-view-container"
      :class="{ upper: isUpper, lower: !isUpper }"
    >
      <svg
        :width="lateralDisplayWidth"
        :height="lateralDisplayHeight"
        :viewBox="lateralViewBox"
        class="lateral-view"
        :style="{
          transform: toothTransform,
          transformOrigin: 'center center'
        }"
      >
        <!-- Clip-path for partial pulp fills (half, two_thirds) -->
        <!-- Clips from the top (root side) to show only the crown portion of the pulp -->
        <defs v-if="needsPulpClip">
          <clipPath :id="pulpClipId">
            <rect
              :x="viewBoxDimensions.x"
              :y="pulpClipY"
              :width="viewBoxDimensions.width"
              :height="pulpClipHeight"
            />
          </clipPath>
        </defs>

        <!-- Roots (render first, behind crown) - hidden when implant present
             or when tooth is a pontic (missing natural tooth in a bridge). -->
        <g
          v-if="!hasImplantTreatment && !isBridgePontic"
          class="roots"
          :opacity="toothOpacity"
        >
          <!-- Single root -->
          <template v-if="'root' in lateralPaths && lateralPaths.root">
            <path
              :d="lateralPaths.root"
              class="tooth-root"
              stroke-width="0.6"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </template>
          <!-- Multiple roots -->
          <template v-else-if="'roots' in lateralPaths && lateralPaths.roots">
            <path
              v-for="(rootPath, idx) in lateralPaths.roots"
              :key="idx"
              :d="rootPath"
              class="tooth-root"
              stroke-width="0.6"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </template>
        </g>

        <!-- Implant (replaces roots) -->
        <g
          v-if="hasImplantTreatment"
          class="implant-root"
        >
          <ImplantSVG
            :view-box="lateralViewBox"
            :tooth-number="toothNumber"
            :fill="getImplantFill(getTreatmentOfType('implant')!)"
            :status="getTreatmentOfType('implant')!.status"
          />
        </g>

        <!-- Crown -->
        <g class="crown">
          <!-- Crown outline -->
          <path
            :d="lateralPaths.crown"
            class="tooth-crown"
            stroke-width="0.6"
            stroke-linecap="round"
            stroke-linejoin="round"
            :opacity="toothOpacity"
          />

          <!-- Solid prosthetic crown fill (bridge + crown-on-implant variants
               share the same lateral-crown solid render). -->
          <path
            v-if="hasCrownFillTreatment"
            :d="lateralPaths.crown"
            :fill="crownFillColor"
            :fill-opacity="crownFillOpacity"
            stroke="none"
            class="bridge-crown-fill"
          />

          <!-- Rule 1: Pulp chamber with dynamic fill based on treatment type -->
          <!-- Prosthetic crown covers natural anatomy: hide pulp chamber. -->
          <!-- Pulp outline (always visible when no treatment) -->
          <path
            v-if="lateralPaths.pulp && !hasImplantTreatment && !hasPulpTreatment && !hasCrownFillTreatment"
            :d="lateralPaths.pulp"
            class="tooth-pulp"
            fill="none"
            stroke-width="0.5"
            stroke-linecap="round"
            stroke-linejoin="round"
            :opacity="toothOpacity"
          />
          <!-- Pulp outline (visible when partial fill to show unfilled area) -->
          <path
            v-if="lateralPaths.pulp && hasPulpTreatment && !hasImplantTreatment && needsPulpClip && !hasCrownFillTreatment"
            :d="lateralPaths.pulp"
            class="tooth-pulp"
            fill="none"
            stroke-width="0.5"
            stroke-linecap="round"
            stroke-linejoin="round"
            :opacity="toothOpacity"
          />
          <!-- Filled pulp (Rule 1 treatments - pulpitis, root canal, etc.) -->
          <!-- Uses clip-path for partial fills (half, two_thirds) to ensure fill stays within pulp bounds -->
          <path
            v-if="hasPulpTreatment && !hasImplantTreatment && !hasCrownFillTreatment"
            :d="getPulpFillPath()"
            class="tooth-pulp pulp-filled"
            :fill="getPulpFillColor()"
            :fill-opacity="getPulpFillOpacity()"
            stroke="none"
            :clip-path="needsPulpClip ? `url(#${pulpClipId})` : undefined"
          />

          <!-- Highlight details (enamel lines, cusps) -->
          <path
            v-for="(highlightPath, idx) in lateralPaths.highlight"
            :key="`highlight-${idx}`"
            :d="highlightPath"
            class="tooth-highlight"
            stroke-width="0.35"
            stroke-linecap="round"
            stroke-linejoin="round"
            fill="none"
            :opacity="toothOpacity"
          />
        </g>

        <!-- Treatment overlays on lateral view -->
        <g class="treatment-overlays-lateral">
          <!-- Note: Surface treatments with occlusal_surface rule are NOT shown here.
               They are already visible in the cenital view and should not paint the crown. -->

          <!-- Implant treatment - now rendered in the root area, not as overlay -->

          <!-- Root canal indicator -->
          <g
            v-if="hasTreatment('root_canal')"
            class="root-canal-treatment"
          >
            <path
              :d="TREATMENT_OVERLAYS.rootCanal.indicator"
              :fill="TREATMENT_COLORS.root_canal"
              :opacity="STATUS_STYLES[getTreatmentOfType('root_canal')!.status].opacity"
              stroke="none"
            />
          </g>

          <!-- Post indicator -->
          <g
            v-if="hasTreatment('post')"
            class="post-treatment"
          >
            <path
              :d="TREATMENT_OVERLAYS.post.shaft"
              :fill="TREATMENT_COLORS.post"
              :opacity="STATUS_STYLES[getTreatmentOfType('post')!.status].opacity"
              stroke="#6B7280"
              stroke-width="0.5"
            />
          </g>

          <!-- Rule 3: Lateral view icons (fracture, periapical, extraction, etc.) -->
          <g
            v-for="treatment in lateralIconTreatments"
            :key="`lateral-icon-${treatment.id}`"
            class="lateral-icon-treatment"
          >
            <!-- Special case: root_canal_overfill shows circle at apex -->
            <template v-if="treatment.treatment_type === 'root_canal_overfill' && iconAnchors">
              <circle
                :cx="iconAnchors.apex.x"
                :cy="iconAnchors.apex.y"
                r="6"
                :fill="getTreatmentColor(treatment.treatment_type)"
                :fill-opacity="STATUS_STYLES[treatment.status]?.opacity ?? 1"
                :stroke="getTreatmentColor(treatment.treatment_type)"
                stroke-width="1"
              />
            </template>

            <!-- Extraction / Missing X markers -->
            <template v-else-if="['extraction', 'missing'].includes(treatment.treatment_type) && iconAnchors && !hasReplacementTreatment">
              <g
                :transform="`translate(${iconAnchors.crownCenter.x}, ${iconAnchors.crownCenter.y})`"
                :opacity="treatment.treatment_type === 'missing' ? 0.5 : STATUS_STYLES[treatment.status]?.opacity ?? 1"
              >
                <line
                  x1="-20"
                  y1="-20"
                  x2="20"
                  y2="20"
                  :stroke="getTreatmentColor(treatment.treatment_type)"
                  stroke-width="5"
                  stroke-linecap="round"
                />
                <line
                  x1="20"
                  y1="-20"
                  x2="-20"
                  y2="20"
                  :stroke="getTreatmentColor(treatment.treatment_type)"
                  stroke-width="5"
                  stroke-linecap="round"
                />
              </g>
            </template>

            <!-- Periapical lesions at apex -->
            <template v-else-if="treatment.treatment_type.startsWith('periapical_') && iconAnchors">
              <circle
                :cx="iconAnchors.apex.x"
                :cy="iconAnchors.apex.y - (treatment.treatment_type === 'periapical_large' ? 12 : treatment.treatment_type === 'periapical_medium' ? 8 : 4)"
                :r="treatment.treatment_type === 'periapical_large' ? 16 : treatment.treatment_type === 'periapical_medium' ? 10 : 6"
                :fill="getTreatmentColor(treatment.treatment_type)"
                :fill-opacity="0.7 * (STATUS_STYLES[treatment.status]?.opacity ?? 1)"
                :stroke="getTreatmentColor(treatment.treatment_type)"
                stroke-width="1"
              />
            </template>

            <!-- Fracture zigzag -->
            <template v-else-if="treatment.treatment_type === 'fracture' && iconAnchors">
              <path
                :d="`M ${iconAnchors.crownCenter.x - 6},${iconAnchors.crownCenter.y - 16} L ${iconAnchors.crownCenter.x},${iconAnchors.crownCenter.y - 8} L ${iconAnchors.crownCenter.x - 4},${iconAnchors.crownCenter.y} L ${iconAnchors.crownCenter.x + 2},${iconAnchors.crownCenter.y + 8} L ${iconAnchors.crownCenter.x - 2},${iconAnchors.crownCenter.y + 16}`"
                fill="none"
                :stroke="getTreatmentColor(treatment.treatment_type)"
                stroke-width="3"
                :stroke-opacity="STATUS_STYLES[treatment.status]?.opacity ?? 1"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
            </template>

            <!-- Apicoectomy line at apex -->
            <template v-else-if="treatment.treatment_type === 'apicoectomy' && iconAnchors">
              <line
                :x1="iconAnchors.apex.x - 16"
                :y1="iconAnchors.apex.y + 4"
                :x2="iconAnchors.apex.x + 16"
                :y2="iconAnchors.apex.y + 4"
                :stroke="getTreatmentColor(treatment.treatment_type)"
                stroke-width="4"
                :stroke-opacity="STATUS_STYLES[treatment.status]?.opacity ?? 1"
                stroke-linecap="round"
              />
            </template>

            <!-- Rotated indicator - circular rotation arrow (Lucide rotate-cw) -->
            <template v-else-if="treatment.treatment_type === 'rotated' && iconAnchors">
              <g :transform="`translate(${iconAnchors.crownCenter.x}, ${iconAnchors.crownCenter.y})`">
                <path
                  d="M 9,0 A 9,9 0 1,1 0,-9 C 2.52,-9 4.93,-8 6.74,-6.26 L 9,-4 M 9,-9 V -4 H 4"
                  fill="none"
                  :stroke="getTreatmentColor(treatment.treatment_type)"
                  stroke-width="2"
                  :stroke-opacity="STATUS_STYLES[treatment.status]?.opacity ?? 1"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                />
              </g>
            </template>

            <!-- Displaced indicator - horizontal arrow -->
            <template v-else-if="treatment.treatment_type === 'displaced' && iconAnchors">
              <g :transform="`translate(${iconAnchors.besideCrown.x}, ${iconAnchors.besideCrown.y})`">
                <path
                  d="M -16,0 L 16,0"
                  fill="none"
                  :stroke="getTreatmentColor(treatment.treatment_type)"
                  stroke-width="3"
                  :stroke-opacity="STATUS_STYLES[treatment.status]?.opacity ?? 1"
                  stroke-linecap="round"
                />
                <path
                  d="M 10,-6 L 16,0 L 10,6"
                  fill="none"
                  :stroke="getTreatmentColor(treatment.treatment_type)"
                  stroke-width="3"
                  :stroke-opacity="STATUS_STYLES[treatment.status]?.opacity ?? 1"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                />
              </g>
            </template>

            <!-- Post in root -->
            <template v-else-if="treatment.treatment_type === 'post' && iconAnchors">
              <rect
                :x="iconAnchors.rootCenter.x - 4"
                :y="iconAnchors.rootCenter.y - 15"
                width="8"
                height="50"
                rx="2"
                :fill="getTreatmentColor(treatment.treatment_type)"
                :fill-opacity="STATUS_STYLES[treatment.status]?.opacity ?? 1"
              />
            </template>

            <!-- Orthodontic treatments on crown -->
            <template v-else-if="['bracket', 'tube', 'band', 'attachment', 'retainer'].includes(treatment.treatment_type) && iconAnchors">
              <g :transform="`translate(${iconAnchors.crownCenter.x}, ${iconAnchors.crownCenter.y})`">
                <!-- Bracket -->
                <template v-if="treatment.treatment_type === 'bracket'">
                  <rect
                    x="-8"
                    y="-8"
                    width="16"
                    height="16"
                    :fill="getTreatmentColor(treatment.treatment_type)"
                    :fill-opacity="0.8 * (STATUS_STYLES[treatment.status]?.opacity ?? 1)"
                  />
                  <line
                    x1="-12"
                    y1="0"
                    x2="12"
                    y2="0"
                    :stroke="getTreatmentColor(treatment.treatment_type)"
                    stroke-width="2"
                  />
                </template>
                <!-- Tube -->
                <template v-else-if="treatment.treatment_type === 'tube'">
                  <rect
                    x="-10"
                    y="-6"
                    width="20"
                    height="12"
                    rx="2"
                    :fill="getTreatmentColor(treatment.treatment_type)"
                    :fill-opacity="0.8 * (STATUS_STYLES[treatment.status]?.opacity ?? 1)"
                  />
                  <circle
                    cx="0"
                    cy="0"
                    r="3"
                    fill="white"
                  />
                </template>
                <!-- Band -->
                <template v-else-if="treatment.treatment_type === 'band'">
                  <line
                    x1="-16"
                    y1="-4"
                    x2="16"
                    y2="-4"
                    :stroke="getTreatmentColor(treatment.treatment_type)"
                    stroke-width="3"
                  />
                  <line
                    x1="-16"
                    y1="4"
                    x2="16"
                    y2="4"
                    :stroke="getTreatmentColor(treatment.treatment_type)"
                    stroke-width="3"
                  />
                </template>
                <!-- Attachment -->
                <template v-else-if="treatment.treatment_type === 'attachment'">
                  <ellipse
                    cx="0"
                    cy="0"
                    rx="8"
                    ry="6"
                    :fill="getTreatmentColor(treatment.treatment_type)"
                    :fill-opacity="STATUS_STYLES[treatment.status]?.opacity ?? 1"
                  />
                </template>
                <!-- Retainer -->
                <template v-else-if="treatment.treatment_type === 'retainer'">
                  <path
                    d="M -20,0 Q -14,-6 -8,0 Q -2,6 4,0 Q 10,-6 16,0"
                    fill="none"
                    :stroke="getTreatmentColor(treatment.treatment_type)"
                    stroke-width="3"
                    stroke-linecap="round"
                  />
                </template>
              </g>
            </template>
          </g>
        </g>

      </svg>

      <!-- Planned indicator"P" for lateral view (outside SVG to avoid transform) -->
      <div
        v-if="hasPlannedLateralTreatments"
        class="planned-indicator-lateral"
      >
        <span class="planned-p">P</span>
      </div>
    </div>

    <!-- Occlusal View (Top-down) -->
    <div class="occlusal-view-container">
      <svg
        width="55"
        height="55"
        viewBox="0 0 50 50"
        class="occlusal-view"
        :style="{
          transform: toothTransform,
          transformOrigin: 'center center'
        }"
      >
        <!-- SVG Patterns and Gradients Definition -->
        <defs v-html="PATTERN_DEFINITIONS" />

        <!-- Background - pointer-events none to let clicks pass through to surfaces -->
        <rect
          x="0"
          y="0"
          width="50"
          height="50"
          fill="transparent"
          pointer-events="none"
        />

        <!-- Background outline -->
        <path
          :d="occlusalPaths.outline"
          class="tooth-occlusal"
          stroke-width="1"
          stroke-linecap="round"
          stroke-linejoin="round"
          pointer-events="none"
          :opacity="toothOpacity"
        />

        <!-- Highlight details (fissures, ridges) -->
        <path
          v-for="(highlightPath, idx) in occlusalPaths.highlight"
          :key="`occlusal-highlight-${idx}`"
          :d="highlightPath"
          class="tooth-highlight"
          stroke-width="0.6"
          stroke-linecap="round"
          stroke-linejoin="round"
          fill="none"
          pointer-events="none"
          :opacity="toothOpacity"
        />

        <!-- Treatment overlays on occlusal view -->
        <g class="treatment-overlays">
          <!-- Rule 2: Occlusal surface treatments (solid fill, dot, outline) -->
          <template
            v-for="treatment in occlusalSurfaceTreatments"
            :key="`occlusal-${treatment.id}`"
          >
            <!-- Get the config for this treatment type -->
            <template v-if="getOcclusalConfig(treatment)">
              <!-- Solid fill type - fill the surface(s) -->
              <template v-if="getOcclusalConfig(treatment)?.type === 'solid_fill'">
                <template v-if="treatment.surfaces && treatment.surfaces.length > 0">
                  <path
                    v-for="surface in treatment.surfaces"
                    :key="`${treatment.id}-${surface}`"
                    :d="occlusalPaths.surfaces[surface]"
                    :fill="getTreatmentColor(treatment.treatment_type)"
                    :fill-opacity="STATUS_STYLES[treatment.status]?.opacity ?? 1"
                    stroke="none"
                    class="treatment-surface-overlay"
                  />
                </template>
                <template v-else>
                  <path
                    :d="occlusalPaths.surfaces.O"
                    :fill="getTreatmentColor(treatment.treatment_type)"
                    :fill-opacity="STATUS_STYLES[treatment.status]?.opacity ?? 1"
                    stroke="none"
                    class="treatment-surface-overlay"
                  />
                </template>
              </template>

              <!-- Dot type - show dot indicator in surface center -->
              <template v-else-if="getOcclusalConfig(treatment)?.type === 'dot'">
                <template v-if="treatment.surfaces && treatment.surfaces.length > 0">
                  <circle
                    v-for="surface in treatment.surfaces"
                    :key="`${treatment.id}-${surface}-dot`"
                    :cx="getOcclusalSurfaceCenter(toothNumber, surface).x"
                    :cy="getOcclusalSurfaceCenter(toothNumber, surface).y"
                    r="4"
                    :fill="getTreatmentColor(treatment.treatment_type)"
                    :fill-opacity="STATUS_STYLES[treatment.status]?.opacity ?? 1"
                    class="treatment-dot-overlay"
                  />
                </template>
                <template v-else>
                  <circle
                    cx="25"
                    cy="25"
                    r="4"
                    :fill="getTreatmentColor(treatment.treatment_type)"
                    :fill-opacity="STATUS_STYLES[treatment.status]?.opacity ?? 1"
                    class="treatment-dot-overlay"
                  />
                </template>
              </template>

              <!-- Outline type - show light outline on surface -->
              <template v-else-if="getOcclusalConfig(treatment)?.type === 'outline'">
                <template v-if="treatment.surfaces && treatment.surfaces.length > 0">
                  <path
                    v-for="surface in treatment.surfaces"
                    :key="`${treatment.id}-${surface}-outline`"
                    :d="occlusalPaths.surfaces[surface]"
                    fill="none"
                    :stroke="getTreatmentColor(treatment.treatment_type)"
                    :stroke-width="1.5"
                    :stroke-opacity="STATUS_STYLES[treatment.status]?.opacity ?? 1"
                    class="treatment-outline-overlay"
                  />
                </template>
                <template v-else>
                  <path
                    :d="occlusalPaths.surfaces.O"
                    fill="none"
                    :stroke="getTreatmentColor(treatment.treatment_type)"
                    :stroke-width="1.5"
                    :stroke-opacity="STATUS_STYLES[treatment.status]?.opacity ?? 1"
                    class="treatment-outline-overlay"
                  />
                </template>
              </template>
            </template>

            <!-- Fallback for legacy treatments not in config -->
            <template v-else>
              <template v-if="treatment.surfaces && treatment.surfaces.length > 0">
                <path
                  v-for="surface in treatment.surfaces"
                  :key="`${treatment.id}-${surface}`"
                  :d="occlusalPaths.surfaces[surface]"
                  :fill="getTreatmentColor(treatment.treatment_type)"
                  :fill-opacity="STATUS_STYLES[treatment.status]?.opacity ?? 1"
                  stroke="none"
                  class="treatment-surface-overlay"
                />
              </template>
              <template v-else>
                <path
                  :d="occlusalPaths.surfaces.O"
                  :fill="getTreatmentColor(treatment.treatment_type)"
                  :fill-opacity="STATUS_STYLES[treatment.status]?.opacity ?? 1"
                  stroke="none"
                  class="treatment-surface-overlay"
                />
              </template>
            </template>
          </template>

          <!-- Rule 4: Pattern fill treatments (crown, pontic, overlay, etc.) -->
          <template
            v-for="treatment in patternFillTreatments"
            :key="`pattern-${treatment.id}`"
          >
            <path
              :d="occlusalPaths.outline"
              :fill="getPatternId(treatment.treatment_type) ? `url(#${getPatternId(treatment.treatment_type)})` : getTreatmentColor(treatment.treatment_type)"
              :fill-opacity="STATUS_STYLES[treatment.status]?.opacity ?? 1"
              :stroke="getTreatmentColor(treatment.treatment_type)"
              stroke-width="1.5"
              class="pattern-fill-overlay"
            />
          </template>

          <!-- Whole tooth treatments not covered by other rules -->
          <template
            v-for="treatment in toothTreatments.filter(t =>
              !hasVisualizationRule(t.treatment_type, 'occlusal_surface')
              && !hasVisualizationRule(t.treatment_type, 'pattern_fill')
              && !['bracket', 'tube', 'band', 'attachment', 'retainer', 'implant', 'bridge', 'crown_on_implant', 'provisional_crown_on_implant'].includes(t.treatment_type)
              && !hasVisualizationRule(t.treatment_type, 'pulp_fill')
              && !hasVisualizationRule(t.treatment_type, 'lateral_icon')
            )"
            :key="`whole-${treatment.id}`"
          >
            <g class="whole-tooth-indicator">
              <path
                :d="occlusalPaths.outline"
                :fill="getTreatmentColor(treatment.treatment_type)"
                :fill-opacity="(STATUS_STYLES[treatment.status]?.opacity ?? 1) * 0.4"
                :stroke="getTreatmentColor(treatment.treatment_type)"
                stroke-width="2"
              />
            </g>
          </template>
        </g>

        <!-- Missing tooth X overlay -->
        <g
          v-if="generalCondition === 'missing' && !hasReplacementTreatment"
          class="missing-indicator"
          pointer-events="none"
        >
          <line
            x1="8"
            y1="8"
            x2="42"
            y2="42"
            stroke="#6B7280"
            stroke-width="2.5"
            stroke-linecap="round"
          />
          <line
            x1="42"
            y1="8"
            x2="8"
            y2="42"
            stroke="#6B7280"
            stroke-width="2.5"
            stroke-linecap="round"
          />
        </g>

        <!-- Extraction indicated marker -->
        <g
          v-if="generalCondition === 'extraction_indicated' && !hasReplacementTreatment"
          class="extraction-indicator"
          pointer-events="none"
        >
          <line
            x1="10"
            y1="10"
            x2="40"
            y2="40"
            stroke="#DC2626"
            stroke-width="2"
            stroke-dasharray="5,3"
            stroke-linecap="round"
          />
          <line
            x1="40"
            y1="10"
            x2="10"
            y2="40"
            stroke="#DC2626"
            stroke-width="2"
            stroke-dasharray="5,3"
            stroke-linecap="round"
          />
        </g>

        <!-- Preview overlay for pending treatment -->
        <g
          v-if="showingPreview"
          class="preview-overlay"
          opacity="0.5"
          pointer-events="none"
        >
          <path
            :d="occlusalPaths.outline"
            :fill="getTreatmentColor(pendingTreatment!.type)"
            stroke="var(--odontogram-selected)"
            stroke-width="2"
          />
        </g>

        <!-- Selection highlight -->
        <path
          v-if="selected"
          :d="occlusalPaths.outline"
          fill="none"
          stroke="var(--odontogram-selected)"
          stroke-width="2.5"
          class="selection-ring"
          pointer-events="none"
        />

      </svg>

      <!-- Planned indicator"P" for occlusal view (outside SVG to avoid transform) -->
      <div
        v-if="hasPlannedOcclusalTreatments"
        class="planned-indicator-occlusal"
      >
        <span class="planned-p">P</span>
      </div>
    </div>

    <!-- Tooth number label -->
    <div
      class="tooth-number"
      :class="{ selected: selected }"
    >
      {{ toothNumber }}
    </div>
  </div>
</template>

<style scoped>
.tooth-dual-view-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  cursor: pointer;
  transition: transform 0.15s ease, filter 0.15s ease;
  position: relative;
}

.tooth-dual-view-wrapper:hover {
  transform: translateY(-1px);
}

.tooth-dual-view-wrapper.readonly {
  cursor: default;
}

.tooth-dual-view-wrapper.readonly:hover {
  transform: none;
}

.tooth-dual-view-wrapper.has-preview {
  filter: drop-shadow(0 0 4px rgba(59, 130, 246, 0.5));
}

.tooth-dual-view-wrapper.highlighted {
  filter: drop-shadow(0 0 6px rgba(245, 158, 11, 0.6));
  animation: highlight-pulse 1s ease-in-out infinite;
}

/* Tooth SVG styling using CSS variables */
.tooth-crown,
.tooth-occlusal {
  fill: var(--odontogram-fill);
  stroke: var(--odontogram-outline);
  transition: fill 0.15s ease, stroke 0.15s ease;
}

.tooth-root {
  fill: var(--odontogram-root-fill);
  stroke: var(--odontogram-outline);
  transition: fill 0.15s ease, stroke 0.15s ease;
}

.tooth-highlight {
  stroke: var(--odontogram-detail);
  transition: stroke 0.15s ease;
}

.tooth-pulp {
  stroke: var(--odontogram-detail);
  transition: fill 0.2s ease, stroke 0.15s ease;
}

.tooth-pulp.pulp-filled {
  stroke: none;
}

@keyframes highlight-pulse {
  0%, 100% {
    filter: drop-shadow(0 0 6px rgba(245, 158, 11, 0.6));
  }
  50% {
    filter: drop-shadow(0 0 10px rgba(245, 158, 11, 0.8));
  }
}

.tooth-number {
  font-size: 10px;
  color: var(--color-gray-600);
  font-weight: 600;
  user-select: none;
  text-align: center;
  margin-top: 2px;
  transition: color 0.15s ease;
}

.tooth-number.selected {
  color: var(--odontogram-selected);
}

:root.dark .tooth-number {
  color: var(--color-gray-400);
}

.surface {
  transition: opacity 0.15s ease;
  pointer-events: all;
}

.surface.clickable:hover {
  opacity: 0.85;
}

/* Lateral view container - fixed height for alignment across all teeth */
.lateral-view-container {
  position: relative;
  display: flex;
  justify-content: center;
  width: 100%;
  height: 110px; /* Fixed height for consistent crown alignment + space for apex icons */
  overflow: visible; /* Allow apex icons to be visible */
}

/* Upper teeth: align SVG to bottom so crowns line up */
.lateral-view-container.upper {
  align-items: flex-end;
  padding-top: 10px; /* Extra space for apex icons */
}

/* Lower teeth: align SVG to top so crowns line up (after scaleY flip) */
.lateral-view-container.lower {
  align-items: flex-start;
  padding-bottom: 10px; /* Extra space for apex icons */
}

.lateral-view {
  display: block;
  flex-shrink: 0;
  overflow: visible; /* Allow icons beyond viewBox to be visible */
}

.occlusal-view {
  display: block;
  pointer-events: all;
  margin: 5px 0; /* Vertical spacing from lateral view */
}

/* For UPPER teeth: lateral first (order 1), occlusal second (order 2) */
/* For LOWER teeth: occlusal first (order 1), lateral second (order 2) */
.tooth-dual-view-wrapper.is-upper .lateral-view-container {
  order: 1;
}

.tooth-dual-view-wrapper.is-upper .occlusal-view-container {
  order: 2;
}

.tooth-dual-view-wrapper.is-lower .lateral-view-container {
  order: 2;
}

.tooth-dual-view-wrapper.is-lower .occlusal-view-container {
  order: 1;
}

.tooth-dual-view-wrapper.is-lower .tooth-number {
  order: 3;
}

.tooth-dual-view-wrapper.is-upper .tooth-number {
  order: 3;
}

.treatment-overlays,
.treatment-overlays-lateral {
  pointer-events: none;
}

.selection-ring {
  animation: pulse-ring 1.5s ease-in-out infinite;
}

@keyframes pulse-ring {
  0%, 100% {
    stroke-opacity: 1;
  }
  50% {
    stroke-opacity: 0.6;
  }
}

.preview-overlay {
  pointer-events: none;
  animation: preview-pulse 1s ease-in-out infinite;
}

@keyframes preview-pulse {
  0%, 100% {
    opacity: 0.4;
  }
  50% {
    opacity: 0.6;
  }
}

.implant-root .dental-implant {
  filter: drop-shadow(0 1px 2px rgba(0,0,0,0.15));
}

/* Occlusal view container for positioning planned indicator */
.occlusal-view-container {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* Planned indicator"P" styling */
.planned-indicator-lateral,
.planned-indicator-occlusal {
  position: absolute;
  pointer-events: none;
  z-index: 10;
}

.planned-indicator-lateral {
  top: 10px;
  left: 50%;
  transform: translateX(-50%);
}

.planned-indicator-occlusal {
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
}

.planned-p {
  color: #EF4444;
  font-size: 14px;
  font-weight: bold;
  font-family: Arial, sans-serif;
  text-shadow:
    -1px -1px 0 white,
    1px -1px 0 white,
    -1px 1px 0 white,
    1px 1px 0 white;
}

:root.dark .planned-p {
  text-shadow:
    -1px -1px 0 rgba(0,0,0,0.8),
    1px -1px 0 rgba(0,0,0,0.8),
    -1px 1px 0 rgba(0,0,0,0.8),
    1px 1px 0 rgba(0,0,0,0.8);
}
</style>
