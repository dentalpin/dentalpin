<script setup lang="ts">
/**
 * One tooth rendered as a lateral silhouette plus three site markers
 * for the requested face.
 *
 * When `tooth.is_implant` is true, the natural root paths are
 * suppressed and the odontogram's `ImplantSVG` component is layered
 * into the root area instead — same visual language as the
 * odontogram so the dentist sees consistent iconography across
 * modules. Crown + gum line stay drawn so the clinical context
 * (carious crown, deep recession, etc.) survives the implant
 * placement.
 *
 * Reuses the odontogram's professional lateral SVG paths
 * (`getLateralPath`, `getToothTransform`). For palatal/lingual rows
 * we compose a vertical flip on top of the quadrant transform so the
 * same SVG can stand in for the other face of the tooth — the
 * established SEPA convention for showing both faces of an arch
 * stacked vertically.
 */
import { computed } from 'vue'
import type { PerioSite, PerioTooth, SiteCode } from '../types'
import { PALATAL_SITES, VESTIBULAR_SITES } from '../types'
import {
  getLateralPath,
  getToothPosition,
  getToothTransform
} from '../../../odontogram/frontend/components/odontogram/ToothSVGPaths'

const props = defineProps<{
  tooth: PerioTooth
  /** Anatomical face this row represents. */
  face: 'vestibular' | 'palatal' | 'lingual'
  readonly?: boolean
  /**
   * Where to render the three site markers relative to the tooth SVG.
   * Defaults to `below`. Set to `above` on the inner row of each arch
   * (palatal in upper, vestibular in lower) so both markers bands sit
   * between the two tooth rows — keeps the arch block symmetric around
   * the markers strip.
   */
  markersPosition?: 'above' | 'below'
}>()

const lateralPaths = computed(() => getLateralPath(props.tooth.tooth_number))
const baseTransform = computed(() => getToothTransform(props.tooth.tooth_number))

// Extracted from the gum-line path of each tooth in ToothSVGPaths.ts.
// Used to align every tooth's CEJ (crown/root boundary) to the same
// Y inside the cell, regardless of natural viewBox height. The strip
// overlay's baseline lives at that same Y, so the CEJ sits on the
// first millimetre line of the SEPA profile.
const GUM_LINE_Y_BY_POSITION: Record<number, number> = {
  1: 95, 2: 85, 3: 103, 4: 62.5, 5: 80, 6: 85, 7: 78, 8: 63
}

const VIEWBOX_W_BY_POSITION: Record<number, number> = {
  1: 46, 2: 40, 3: 47, 4: 40, 5: 40, 6: 64, 7: 66, 8: 67
}

// Common 70 × 150 view window. 70 wide covers the widest molar
// (vbW=67); 150 tall fits every tooth's crown bottom without cropping
// (worst case is pos 7 second molar with 46 vbY of crown past the gum
// line — 150 − 97.5 = 52.5 vbY of headroom). Gum pinned at vbY=97.5,
// so it lands at cellY = (97.5 / 150) × 112 ≈ 72.8 inside the h-28
// cell. Strip overlays in PerioArchBlock anchor to that same cellY.
const VIEW_W = 70
const VIEW_H = 150
const TARGET_GUM_VB_Y = 97.5

const alignedViewBox = computed(() => {
  const position = getToothPosition(props.tooth.tooth_number)
  const vbW = VIEWBOX_W_BY_POSITION[position] ?? VIEWBOX_W_BY_POSITION[1]
  const gly = GUM_LINE_Y_BY_POSITION[position] ?? GUM_LINE_Y_BY_POSITION[1]
  // Centre the tooth horizontally inside the common view window, then
  // shift the view vertically so its CEJ row lands on TARGET_GUM_VB_Y.
  const xV = vbW / 2 - VIEW_W / 2
  const yV = gly - TARGET_GUM_VB_Y
  return `${xV} ${yV} ${VIEW_W} ${VIEW_H}`
})

const faceTransform = computed(() => {
  if (props.face !== 'vestibular') {
    return `${baseTransform.value} scaleY(-1)`.trim()
  }
  return baseTransform.value
})

const visibleSites = computed<readonly SiteCode[]>(() =>
  props.face === 'vestibular' ? VESTIBULAR_SITES : PALATAL_SITES
)

const siteByCode = computed<Record<string, PerioSite | null>>(() => {
  const map: Record<string, PerioSite | null> = {}
  for (const code of visibleSites.value) map[code] = null
  for (const site of props.tooth.sites) {
    if (visibleSites.value.includes(site.site_code)) map[site.site_code] = site
  }
  return map
})

const visualOpacity = computed(() => (props.tooth.is_present ? 1 : 0.35))
</script>

<template>
  <div class="perio-tooth-lateral flex flex-col items-center gap-0.5">
    <!-- Three site markers — rendered above the tooth on inner rows
         (palatal in upper arch, vestibular in lower arch) so both
         arches' markers cluster between the two tooth rows. -->
    <div
      v-if="markersPosition === 'above'"
      class="flex items-center gap-0.5"
    >
      <PerioSiteMarker
        v-for="code in visibleSites"
        :key="`above-${code}`"
        :site="siteByCode[code]"
        size="sm"
        readonly
      />
    </div>

    <div
      class="perio-tooth-lateral__svg-wrapper relative"
      :style="{ opacity: visualOpacity }"
    >
      <svg
        :viewBox="alignedViewBox"
        class="h-28 w-[60px]"
        :style="{ transform: faceTransform }"
        preserveAspectRatio="xMidYMid meet"
      >
        <!-- Z-order matches the odontogram: root or implant first
             (back layer), crown on top so its bottom edge overlaps
             the implant neck cleanly, gum line on top of everything. -->

        <!-- Natural root paths (back layer when no implant). -->
        <g
          v-if="!tooth.is_implant"
          fill="none"
          stroke="var(--odontogram-outline-light)"
          stroke-width="1.5"
          stroke-linejoin="round"
        >
          <path
            v-if="lateralPaths.root"
            :d="lateralPaths.root"
          />
          <template v-else-if="lateralPaths.roots">
            <path
              v-for="(d, idx) in lateralPaths.roots"
              :key="idx"
              :d="d"
            />
          </template>
        </g>

        <!-- Implant fixture replaces the natural root area. Drawn
             before the crown so the crown's bottom edge covers the
             implant neck — same visual seal the odontogram produces. -->
        <ImplantSVG
          v-if="tooth.is_implant && tooth.is_present"
          :view-box="lateralPaths.viewBox"
          :tooth-number="tooth.tooth_number"
          fill="var(--perio-implant-fill)"
          status="existing"
        />

        <!-- Crown on top of root/implant. Surface-token fill so the
             crown's footprint occludes the implant neck — gives the
             same clean seal the odontogram produces between fixture
             and crown. -->
        <g
          fill="var(--odontogram-fill)"
          stroke="var(--odontogram-outline-light)"
          stroke-width="1.5"
          stroke-linejoin="round"
        >
          <path :d="lateralPaths.crown" />
        </g>

        <!-- Gum line is intentionally NOT painted on the tooth here.
             The SEPA strip overlay (PerioProfileStrip) renders the
             first mm gridline at exactly the CEJ cellY, so a separate
             red curve would double-mark the same horizontal and clash
             with the gridline. -->
      </svg>

      <span
        v-if="!tooth.is_present"
        class="absolute inset-0 flex items-center justify-center text-gray-400 dark:text-gray-600"
      >
        <span class="font-mono text-xs">—</span>
      </span>
    </div>

    <!-- Three site markers — rendered below by default (outer rows:
         vestibular in upper, lingual in lower). -->
    <div
      v-if="markersPosition !== 'above'"
      class="flex items-center gap-0.5"
    >
      <PerioSiteMarker
        v-for="code in visibleSites"
        :key="`below-${code}`"
        :site="siteByCode[code]"
        size="sm"
        readonly
      />
    </div>
  </div>
</template>
