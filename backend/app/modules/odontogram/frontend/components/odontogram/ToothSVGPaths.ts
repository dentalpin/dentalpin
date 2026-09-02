/**
 * ToothSVGPaths.ts - Tooth SVG path definitions with quadrant symmetry
 *
 * Implements "napkin unfolding" symmetry:
 * - Q1 (11-18): Original paths (Superior Right)
 * - Q2 (21-28): scaleX(-1) mirror
 * - Q4 (41-48): scaleY(-1) mirror
 * - Q3 (31-38): scaleX(-1) scaleY(-1) mirror
 *
 * Paths extracted from professional dental SVGs with anatomically accurate proportions.
 */

import type { TreatmentStatus } from '~~/app/types'
import {
  isDeciduousTooth as isDeciduousToothFn,
  isUpperTooth as isUpperToothFn,
  SURFACE_TREATMENTS,
  WHOLE_TOOTH_TREATMENTS,
  STATUS_STYLES as STATUS_STYLES_CONFIG,
  TREATMENT_COLORS as TREATMENT_COLORS_CONFIG,
  getTreatmentColor,
  normalizeTreatmentType
} from '~~/app/config/odontogramConstants'

// Re-export helpers
export const isUpperTooth = isUpperToothFn
export const isDeciduousTooth = isDeciduousToothFn

// Surface and whole-tooth treatment types
export const SURFACE_TREATMENT_TYPES: readonly string[] = SURFACE_TREATMENTS
export const WHOLE_TOOTH_TREATMENT_TYPES: readonly string[] = WHOLE_TOOTH_TREATMENTS

// Helper functions for treatment types
export function makesToothTransparent(treatmentType: string): boolean {
  return treatmentType === 'extraction' || treatmentType === 'missing'
}

// Re-export treatment color helper
export { getTreatmentColor }

// Legacy TREATMENT_COLORS export for backwards compatibility (light mode colors)
export const TREATMENT_COLORS: Record<string, string> = Object.fromEntries(
  Object.entries(TREATMENT_COLORS_CONFIG).map(([key, config]) => [key, config.light])
)

// Helper function to get icon anchors for a tooth
export function getIconAnchors(toothNumber: number): IconAnchors | undefined {
  return getLateralPath(toothNumber).anchors
}

// Helper function to get partial pulp path
export function getPartialPulpPath(toothNumber: number, level: 'full' | 'two_thirds' | 'half'): string | undefined {
  const paths = getLateralPath(toothNumber)
  if (level === 'full') return paths.pulp
  if (level === 'two_thirds') return paths.pulpTwoThirds
  if (level === 'half') return paths.pulpHalf
  return paths.pulp
}

// Pattern definitions for SVG
export const PATTERN_DEFINITIONS = `
  <defs>
    <!-- Planned treatment pattern (diagonal stripes - RED) -->
    <pattern id="pattern-planned" patternUnits="userSpaceOnUse" width="6" height="6" patternTransform="rotate(45)">
      <line x1="0" y1="0" x2="0" y2="6" stroke="#EF4444" stroke-width="2" />
    </pattern>

    <!-- Planned treatment patterns by color -->
    <pattern id="pattern-planned-amber" patternUnits="userSpaceOnUse" width="6" height="6" patternTransform="rotate(45)">
      <line x1="0" y1="0" x2="0" y2="6" stroke="#F59E0B" stroke-width="2" />
    </pattern>
    <pattern id="pattern-planned-blue" patternUnits="userSpaceOnUse" width="6" height="6" patternTransform="rotate(45)">
      <line x1="0" y1="0" x2="0" y2="6" stroke="#3B82F6" stroke-width="2" />
    </pattern>
    <pattern id="pattern-planned-green" patternUnits="userSpaceOnUse" width="6" height="6" patternTransform="rotate(45)">
      <line x1="0" y1="0" x2="0" y2="6" stroke="#22C55E" stroke-width="2" />
    </pattern>

    <!-- Filling texture pattern (green dots) -->
    <pattern id="filling-pattern" patternUnits="userSpaceOnUse" width="3" height="3">
      <rect width="3" height="3" fill="#22C55E"/>
      <circle cx="1.5" cy="1.5" r="0.5" fill="#16A34A"/>
    </pattern>

    <!-- Rule 4: Treatment pattern fills -->
    <!-- Diagonal stripes (unerupted - gray) -->
    <pattern id="pattern-unerupted" patternUnits="userSpaceOnUse" width="6" height="6" patternTransform="rotate(45)">
      <line x1="0" y1="0" x2="0" y2="6" stroke="#9CA3AF" stroke-width="1.5" />
    </pattern>

    <!-- Diagonal stripes (crown - amber) -->
    <pattern id="pattern-crown" patternUnits="userSpaceOnUse" width="6" height="6" patternTransform="rotate(-45)">
      <line x1="0" y1="0" x2="0" y2="6" stroke="#F59E0B" stroke-width="1.5" />
    </pattern>

    <!-- Dots (inlay - blue) -->
    <pattern id="pattern-inlay" patternUnits="userSpaceOnUse" width="4" height="4">
      <circle cx="2" cy="2" r="1" fill="#3B82F6"/>
    </pattern>

    <!-- Grid (pontic - blue) -->
    <pattern id="pattern-pontic" patternUnits="userSpaceOnUse" width="6" height="6">
      <path d="M 6 0 L 0 0 0 6" fill="none" stroke="#3B82F6" stroke-width="1"/>
    </pattern>

    <!-- Vertical stripes (bridge_abutment - blue) -->
    <pattern id="pattern-bridge-abutment" patternUnits="userSpaceOnUse" width="4" height="4">
      <line x1="2" y1="0" x2="2" y2="4" stroke="#3B82F6" stroke-width="1.5" />
    </pattern>

    <!-- Horizontal stripes (overlay - blue) -->
    <pattern id="pattern-overlay" patternUnits="userSpaceOnUse" width="4" height="4">
      <line x1="0" y1="2" x2="4" y2="2" stroke="#3B82F6" stroke-width="1.5" />
    </pattern>
  </defs>
`

// Get pattern ID for a treatment type
export function getPatternId(treatmentType: string): string | null {
  const normalized = normalizeTreatmentType(treatmentType)
  const patternMap: Record<string, string> = {
    unerupted: 'pattern-unerupted',
    crown: 'pattern-crown',
    inlay: 'pattern-inlay',
    pontic: 'pattern-pontic',
    bridge_abutment: 'pattern-bridge-abutment',
    overlay: 'pattern-overlay'
  }
  return patternMap[normalized] || null
}

// ============================================================================
// QUADRANT SYMMETRY FUNCTIONS
// ============================================================================

/**
 * Get CSS transform for a tooth based on its quadrant
 * Implements "napkin unfolding" symmetry
 */
export function getToothTransform(toothNumber: number): string {
  const quadrant = Math.floor(toothNumber / 10)

  switch (quadrant) {
    case 1: return '' // Q1: Original (Superior Right)
    case 2: return 'scaleX(-1)' // Q2: Horizontal mirror (Superior Left)
    case 3: return 'scaleX(-1) scaleY(-1)' // Q3: Diagonal mirror (Inferior Left)
    case 4: return 'scaleY(-1)' // Q4: Vertical mirror (Inferior Right)
    // Deciduous teeth
    case 5: return '' // Q5: Original (Superior Right)
    case 6: return 'scaleX(-1)' // Q6: Horizontal mirror (Superior Left)
    case 7: return 'scaleX(-1) scaleY(-1)' // Q7: Diagonal mirror (Inferior Left)
    case 8: return 'scaleY(-1)' // Q8: Vertical mirror (Inferior Right)
    default: return ''
  }
}

/**
 * Get tooth position within quadrant (1-8 for permanent, 1-5 for deciduous)
 */
export function getToothPosition(toothNumber: number): number {
  return toothNumber % 10
}

/** Position within the quadrant (1 = central incisor … 8 = third molar). */
export type ToothPosition = 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8

function isToothPosition(n: number): n is ToothPosition {
  return Number.isInteger(n) && n >= 1 && n <= 8
}

/**
 * Position whose SVG shape draws this tooth: deciduous teeth reuse the
 * permanent shapes (see DECIDUOUS_TO_PERMANENT_MAP); anything outside the
 * FDI range falls back to the central incisor.
 */
function getShapePosition(toothNumber: number): ToothPosition {
  const position = getToothPosition(toothNumber)
  const shape = isDeciduousTooth(toothNumber) ? DECIDUOUS_TO_PERMANENT_MAP[position] : position
  return shape !== undefined && isToothPosition(shape) ? shape : 1
}

// ============================================================================
// LATERAL VIEW PATHS
// Extracted from professional dental SVGs
// ============================================================================

// Anchor points for icon positioning on lateral view
interface IconAnchor {
  x: number
  y: number
}

interface IconAnchors {
  crownCenter: IconAnchor // Center of crown (for brackets, fractures)
  apex: IconAnchor // Root apex (for periapical lesions, apicoectomy)
  beyondApex: IconAnchor // Beyond apex (for overfill indicator)
  aboveCrown: IconAnchor // Above crown (for rotated indicator)
  besideCrown: IconAnchor // Beside crown (for displaced indicator)
  rootCenter: IconAnchor // Center of root area (for post, implant)
}

interface LateralPaths {
  crown: string
  root?: string
  roots?: string[]
  pulp?: string // Full pulp chamber outline (for root canal visualization)
  pulpTwoThirds?: string // Upper 2/3 of pulp chamber
  pulpHalf?: string // Upper 1/2 of pulp chamber
  highlight: string[]
  gumLine: string
  viewBox: string
  anchors?: IconAnchors // Anchor points for icon positioning
}

// ============================================================================
// LATERAL VIEW DISPLAY CONFIGURATION
// Scale and alignment settings for each tooth position
// ============================================================================

interface ToothDisplayConfig {
  scale: number // Scale factor relative to base display width (55px)
  offsetY: number // Vertical offset to align crowns (positive = down)
  displayHeight: number // Fixed display height for consistent alignment
}

// Configuration to ensure proper alignment and sizing
// Upper teeth: roots point UP, crown at BOTTOM - crown line should be aligned
// Lower teeth: roots point DOWN, crown at TOP - crown line should be aligned
// Scales calibrated so all teeth have similar visual height (~100px)
const TOOTH_DISPLAY_CONFIG: Record<ToothPosition, ToothDisplayConfig> = {
  // Incisors - narrower teeth, need smaller scale to achieve similar height
  1: { scale: 0.65, offsetY: 0, displayHeight: 100 },
  2: { scale: 0.62, offsetY: 0, displayHeight: 100 },
  // Canine - similar to incisors
  3: { scale: 0.62, offsetY: 0, displayHeight: 100 },
  // Premolars - medium width
  4: { scale: 0.62, offsetY: 0, displayHeight: 100 },
  5: { scale: 0.62, offsetY: 0, displayHeight: 100 },
  // Molars - wider teeth, need larger scale to compensate for aspect ratio
  6: { scale: 0.95, offsetY: 0, displayHeight: 100 },
  7: { scale: 1.0, offsetY: 0, displayHeight: 100 },
  8: { scale: 1.20, offsetY: 0, displayHeight: 100 }
}

export function getToothDisplayConfig(toothNumber: number): ToothDisplayConfig {
  return TOOTH_DISPLAY_CONFIG[getShapePosition(toothNumber)]
}

// Paths indexed by position (1-8) - using actual SVG paths from reference
const LATERAL_PATHS_BY_POSITION: Record<ToothPosition, LateralPaths> = {
  // Position 1: Central Incisor (tooth 11) - viewBox 46x134
  1: {
    viewBox: '0 0 46 134',
    crown: 'M39.2326 94.6438C33.1163 85.5409 14.1409 86.0457 6.65385 94.6438C-0.669089 102.084 0.287887 121.08 3.03399 127.814C15.6411 135.545 38.1091 133.675 43.8511 128.437C46.722 121.828 43.8511 103.747 39.2326 94.6438Z',
    root: 'M18.1375 13.8391C16.1403 42.3702 9.64956 79.4307 6.65381 94.3946C18.9498 99.8859 26.179 100.443 39.8567 95.5168C40.4808 78.9319 40.0564 39.577 33.3659 14.8367C26.953 -8.87723 18.913 2.76033 18.1375 13.8391Z',
    // Full pulp chamber
    pulp: 'M24.6596 4.92303C30.269 4.6849 31.2334 104.288 22.1317 95.1425C19.5389 92.7118 23.1687 67.5969 24.3785 42.7689C25.3455 22.9252 23.5958 4.9682 24.6596 4.92303Z',
    // Upper 2/3 of pulp (for root_canal_two_thirds)
    pulpTwoThirds: 'M24.6596 4.92303C30.269 4.6849 29 70 23.5 65C21 63 23.1687 45 24.3785 30C25.3455 18 23.5958 4.9682 24.6596 4.92303Z',
    // Upper 1/2 of pulp (for root_canal_half)
    pulpHalf: 'M24.6596 4.92303C30.269 4.6849 28 50 24 48C22 46 23.1687 35 24.3785 22C25.3455 14 23.5958 4.9682 24.6596 4.92303Z',
    highlight: [],
    gumLine: 'M 0,95 Q 23,100 46,95',
    anchors: {
      crownCenter: { x: 23, y: 110 },
      apex: { x: 23, y: 8 },
      beyondApex: { x: 23, y: -5 },
      aboveCrown: { x: 23, y: 125 },
      besideCrown: { x: 45, y: 110 },
      rootCenter: { x: 23, y: 50 }
    }
  },
  // Position 2: Lateral Incisor (tooth 12) - viewBox 40x125
  2: {
    viewBox: '0 0 40 125',
    crown: 'M36.0861 86.4908C33.7138 80.3598 11.2384 78.6075 6.61846 84.8639C0.82482 92.7098 0.250476 113.268 1.62396 116.146C2.99745 119.024 8.866 122.152 18.6053 123.653C28.3446 125.155 35.7115 121.526 37.959 117.647C40.2066 113.768 38.4585 92.6219 36.0861 86.4908Z',
    root: 'M12.487 53.0815C10.4083 62.2149 9.40701 74.1863 8.61621 83.112C16.2849 89.5132 36.3357 86.7405 36.3357 86.7405C36.3357 86.7405 34.7467 75.1037 35.0871 71.475C37.6081 44.5978 35.3738 25.049 34.213 18.4214C32.6315 12.4571 28.4694 0.328393 22.476 1.0291C14.9842 1.90499 18.3555 19.2973 17.7312 26.8049C17.0027 35.5656 14.1102 45.9493 12.487 53.0815Z',
    pulp: 'M23.8494 41.5699C24.8167 21.6581 21.6019 4.15698 23.8495 4.15698C28.1612 4.15698 29.9677 35.6889 27.7202 60.2138C26.8687 78.8752 25.6047 94.7422 20.9135 92.2458C17.2318 87.6165 22.6392 66.4831 23.8494 41.5699Z',
    pulpTwoThirds: 'M23.8494 41.5699C24.8167 21.6581 21.6019 4.15698 23.8495 4.15698C28.1612 4.15698 28 30 26 45C25 55 24 60 22 58C19 55 22.6392 45 23.8494 30Z',
    pulpHalf: 'M23.8494 30C24.8167 18 21.6019 4.15698 23.8495 4.15698C28.1612 4.15698 27 25 25 35C24 42 23 45 21 43C19 40 22.6392 35 23.8494 22Z',
    highlight: [],
    gumLine: 'M 0,85 Q 20,92 40,85',
    anchors: {
      crownCenter: { x: 20, y: 100 },
      apex: { x: 23, y: 5 },
      beyondApex: { x: 23, y: -8 },
      aboveCrown: { x: 20, y: 118 },
      besideCrown: { x: 38, y: 100 },
      rootCenter: { x: 23, y: 45 }
    }
  },
  // Position 3: Canine (tooth 13) - viewBox 47x146
  3: {
    viewBox: '0 0 47 146',
    crown: 'M44.5622 115.129C42.5478 107.137 40.7902 95.6772 22.907 95.8989C3.61725 96.1381 1 114.898 1 129.988C1 136.106 7.90619 141.245 12.8348 143.598C17.3509 145.755 30.8565 145.156 34.2382 143.598C37.7635 141.975 41.3094 141.201 44.5622 135.108C46.8285 130.862 46.0953 121.211 44.5622 115.129Z',
    root: 'M9.09261 76.4153C8.17217 80.9327 7.17502 95.9485 6.7915 102.892C6.7915 102.892 16.3143 107.776 22.907 107.886C29.8761 108.003 40.0297 102.892 40.0297 102.892C38.1121 97.8724 34.7883 71.2707 35.4275 67.1299C36.0667 62.989 34.4048 42.9121 33.5099 38.3948C32.6151 33.8775 30.3139 20.5764 29.9304 15.0552C29.5469 9.53405 25.9674 0.875868 22.3879 1.00135C18.8084 1.12683 19.0641 4.01289 18.1692 5.51866C17.2743 7.02443 17.1465 16.561 16.763 20.5764C16.3795 24.5917 16.3795 25.5956 14.5897 29.36C12.8 33.1244 11.7772 43.7903 11.7772 47.0528C11.7772 50.3153 10.2432 70.7687 9.09261 76.4153Z',
    pulp: 'M19.3901 108.569C20.4638 72.4818 22.0439 6.61914 22.4697 6.61914C26.6797 6.61914 26.8139 49.0405 26.9928 84.7355C27.0356 93.2851 27.8031 101.605 28.0152 108.731C28.0857 111.1 26.141 113.006 23.7516 113.006C21.2913 113.006 19.3176 111.008 19.3901 108.569Z',
    pulpTwoThirds: 'M21 75C21.5 45 22.0439 6.61914 22.4697 6.61914C26.6797 6.61914 26.5 40 26.3 65C26.2 72 25.5 78 23.7 78C22 78 21 70 21 65Z',
    pulpHalf: 'M22 50C22.3 30 22.0439 6.61914 22.4697 6.61914C26.6797 6.61914 26.3 25 26 42C25.8 50 25 55 23.5 55C22 55 22 48 22 42Z',
    highlight: [],
    gumLine: 'M 0,103 Q 23,110 47,103',
    anchors: {
      crownCenter: { x: 23, y: 120 },
      apex: { x: 23, y: 5 },
      beyondApex: { x: 23, y: -8 },
      aboveCrown: { x: 23, y: 140 },
      besideCrown: { x: 45, y: 120 },
      rootCenter: { x: 23, y: 55 }
    }
  },
  // Position 4: First Premolar (tooth 14) - viewBox normalized to ~40x100 scale
  4: {
    viewBox: '0 0 40 100',
    crown: 'M33.75 62.5c-3.75,-4 -23.5,-4 -26.5,0 -5.25,7 -6,15.25 -6,19 -0.25,2.75 2.5,8.25 17,10 18,2 20.5,-7.5 20.5,-9.5 0,-3.5 -1,-15.25 -5.25,-19.5z',
    roots: [
      'M21.5 27.75c2.5,-7.75 4,-13.75 4.5,-17.75 0.25,-1.75 -1.5,-8.5 0.5,-8.5 2.25,0 8.25,8 9,13.5 0.75,5.25 -0.5,22.25 -1.25,29 -0.75,5.5 -0.75,14.25 -0.5,18 -12.5,7.5 -18,7 -26.5,0.5 0,0 2,-3.75 2.5,-12.5 0.25,-5.25 -1.5,-14.25 -1.75,-20.25 -1.25,-16.25 2.75,-27.75 5.5,-28.25 3.5,0.25 3.5,18 8,25.75l0.25 0.5'
    ],
    pulp: 'M19.25 38.5c0.25,1 0,1.75 1.25,2.5 1.75,-2.5 5.75,-9.25 7,-18 1.75,-11 0.75,-14.5 0.75,-15.25 0,-0.5 4,-1 2.5,14 -1.5,15.25 -4.25,21.5 -5,26.75 -0.75,5.25 -1.25,6 -1.75,13.5 -0.75,6.5 -9.25,5.25 -9.25,-0.75 0,-1.5 0,-5.25 0,-7.5 0,-2.75 -3.5,-18 -3.75,-26.25 -0.25,-6.5 0,-20.25 1.25,-21.25 1.5,-1.5 2.75,13.25 3.75,19.25 1,6.25 2.25,8.5 2.75,10.25l0.25 1.75z',
    pulpTwoThirds: 'M18 28c0.5,1 1,2 2,1 2,-2 4,-8 5,-14 1,-8 0.5,-10 0.5,-10.5 0,-0.3 2,-0.5 1.5,8 -0.5,8 -2,14 -3,18 -1,4 -1.5,4.5 -2,8 -0.5,4 -6,3.5 -6,-0.5 0,-1 0,-3 0,-5 0,-2 -2,-12 -2.5,-18 -0.3,-5 0,-14 1,-15 1,-1 2,9 2.5,13 0.5,4 1.5,6 2,8z',
    pulpHalf: 'M17 20c0.5,0.5 1,1.5 1.5,1 1.5,-1.5 3,-6 4,-10 0.8,-6 0.3,-8 0.3,-8.5 0,-0.2 1.5,-0.3 1,6 -0.3,5 -1.5,10 -2,13 -0.5,2.5 -1,3 -1.5,5.5 -0.3,2.5 -4,2 -4,-0.3 0,-0.5 0,-2 0,-3 0,-1.5 -1.5,-8 -2,-12 -0.2,-3 0,-10 0.7,-10.5 0.7,-0.5 1.5,6 2,9 0.3,3 1,4 1.5,6z',
    highlight: [],
    gumLine: 'M 0,62.5 Q 20,67.5 40,62.5',
    anchors: {
      crownCenter: { x: 20, y: 75 },
      apex: { x: 20, y: 3 },
      beyondApex: { x: 20, y: -8 },
      aboveCrown: { x: 20, y: 92 },
      besideCrown: { x: 38, y: 75 },
      rootCenter: { x: 20, y: 35 }
    }
  },
  // Position 5: Second Premolar (tooth 15) - viewBox 40x125
  5: {
    viewBox: '0 0 40 125',
    crown: 'M32.0429 80.3319C25.3641 76.7153 12.3775 76.9648 8.17236 80.3319C2.73036 89.0619 -0.0157515 103.786 1.34475 110.396C2.70524 117.005 18.5365 125.61 21.2575 123.74C24.6402 121.414 38.3256 113.139 38.944 108.4C39.5624 103.661 34.8625 94.5572 34.6151 87.8227C34.4172 82.4352 32.9797 80.8392 32.0429 80.3319Z',
    root: 'M9.01314 60.2618C8.22157 63.8534 8.10614 75.0609 8.14736 80.2156C17.5183 82.1917 23.0911 82.7369 33.6258 81.9617C33.5021 81.0887 32.5126 72.9825 31.6469 65.8739C30.7574 58.5708 31.0285 49.412 31.0285 46.5436C31.0285 43.6752 29.9153 33.3242 28.4311 29.5828C26.947 25.8415 27.5654 18.4834 26.8233 15.3656C26.0812 12.2478 20.8866 0.400168 17.9182 1.02373C14.9498 1.64728 17.1761 6.38633 16.1867 15.9891C15.3951 23.6714 12.8473 34.5296 11.9815 37.0654C10.7447 40.3079 10.0026 55.7721 9.01314 60.2618Z',
    pulp: 'M18.6602 6.8971C23.0444 1.05663 24.7882 59.2963 24.4272 85.6725C24.406 87.219 23.1529 88.4437 21.619 88.4437C20.0082 88.4437 18.7249 87.0911 18.7917 85.4684C19.91 58.2791 19.4075 17.8055 18.6602 6.8971Z',
    pulpTwoThirds: 'M19 6.8971C23 1.05663 24 45 23.8 58C23.7 62 22.5 64 21.2 64C19.8 64 19 62 19.1 58C19.5 45 19.2 15 19 6.8971Z',
    pulpHalf: 'M19.5 6.8971C22.5 1.05663 23.5 30 23.2 40C23.1 44 22.2 46 21 46C19.8 46 19.2 44 19.3 40C19.6 30 19.4 12 19.5 6.8971Z',
    highlight: [],
    gumLine: 'M 0,80 Q 20,88 40,80',
    anchors: {
      crownCenter: { x: 20, y: 95 },
      apex: { x: 20, y: 5 },
      beyondApex: { x: 20, y: -8 },
      aboveCrown: { x: 20, y: 118 },
      besideCrown: { x: 38, y: 95 },
      rootCenter: { x: 20, y: 45 }
    }
  },
  // Position 6: First Molar (tooth 16) - viewBox 64x128
  6: {
    viewBox: '0 0 64 128',
    crown: 'M52.5724 83.8192C38.6457 77.1735 21.2542 79.2177 11.7848 82.6763C9.77918 83.4088 8.23738 84.9707 7.35306 86.9098C5.1137 91.8204 1 101.871 1 109.443C1 114.19 5.86637 124.628 14.0266 126.184C20.4417 127.407 24.7345 122.822 31.8129 122.686C39.6605 122.535 44.3969 129.286 51.6033 126.184C58.803 123.084 64.5464 115.023 62.6258 109.443C60.8828 104.378 59.6213 92.6599 54.5345 85.8667C54.0084 85.1642 53.3957 84.2121 52.5724 83.8192Z',
    roots: [
      'M31.6876 1C25.1117 1 26.9905 28.8602 19.7883 35.2319C21.1244 45.8096 28.5513 59.3963 32.3139 60.4685C35.8211 61.468 44.0879 37.2308 45.7162 28.8602C41.0818 22.7385 37.1989 1 31.6876 1Z',
      'M54.537 84.9802C54.537 83.5 52.5329 73.4613 54.537 64.8658C57.0421 54.1215 59.2967 40.8785 59.2967 31.3836C59.2967 22.4209 58.7387 10.8979 52.1445 5.22081C51.5917 4.74482 50.7688 5.08408 50.6455 5.80208C48.2891 19.5153 42.5034 48.131 33.2436 59.8685C30.5486 63.2845 16.6396 32.362 13.0019 10.5877C12.8671 9.78116 11.9139 9.48249 11.4381 10.1484C8.49442 14.2692 4.6997 23.8642 6.43885 39.1295C8.94396 61.1178 9.94601 59.2438 9.94601 68.364C9.94601 72.1459 8.4267 80.7768 7.6531 85.1369'
    ],
    pulp: 'M37.1988 80.0831C37.6999 79.4584 46.3425 64.8414 48.7223 53.9721C51.1022 43.1029 55.3609 29.61 51.7285 16.6169C48.0961 3.62377 56.9892 42.1033 32.0634 74.836C28.5169 74.836 11.3588 40.418 11.9479 21.9296C11.9552 21.7004 11.6501 21.6422 11.583 21.8616C6.57857 38.2285 23.1191 71.6539 24.6733 74.8358C25.8632 77.2722 25.5083 79.75 25.4248 80.0831',
    pulpTwoThirds: 'M35 55C36 52 42 45 44 35C46 25 48 18 46 12C44 6 50 30 32 52C29 52 18 30 18 18C18 17 17.5 17 17.5 18C14 30 25 50 26 52C27 54 26.5 56 26.5 56',
    pulpHalf: 'M34 40C35 38 38 32 40 25C42 18 43 12 42 8C41 4 45 22 32 38C30 38 22 22 22 15C22 14 21.5 14 21.5 15C19 24 27 36 28 38C29 40 28.5 42 28.5 42',
    highlight: [],
    gumLine: 'M 0,85 Q 32,95 64,85',
    anchors: {
      crownCenter: { x: 32, y: 105 },
      apex: { x: 32, y: 5 },
      beyondApex: { x: 32, y: -8 },
      aboveCrown: { x: 32, y: 125 },
      besideCrown: { x: 60, y: 105 },
      rootCenter: { x: 32, y: 45 }
    }
  },
  // Position 7: Second Molar (tooth 17) - viewBox 66x124
  7: {
    viewBox: '0 0 66 124',
    crown: 'M57.655 80.8343C57.2557 80.5265 56.8413 80.2327 56.4129 79.9525C44.8747 72.4037 23.1621 74.6455 11.3233 76.9591C10.1919 77.2013 8.70714 77.8501 7.72107 78.7268C7.41105 79.0024 7.15033 79.3005 6.96539 79.6156C-7.5536 104.353 8.35603 122.835 13.4349 122.835C18.6519 122.835 21.1362 113.835 28.589 112.835C36.0418 111.834 46.4758 124.585 52.6865 122.835C57.5011 121.478 63.8657 109.459 64.8594 104.709C65.8531 99.9594 61.3815 83.8342 57.655 80.8343Z',
    roots: [
      'M23.1237 1.08372C17.9564 4.38375 17.6582 22.6256 18.1551 31.334C20.6394 39.2507 26.8998 54.484 32.0671 52.084C37.2344 49.684 39.1058 39.9172 39.3957 35.3338C34.1787 29.3338 30.2039 17.7089 30.2039 15.3339C30.2039 12.9588 28.2164 -0.166297 23.1237 1.08372Z',
      'M10.79 62.9522C11.6845 68.8711 7 78.5 7.31157 78.7704C27.6459 73.526 38.316 73.7571 56.0109 80C58.3299 72.0579 59.4894 47.6533 54.5201 30.8499C48.5135 10.5393 40.5231 6.64772 37.9971 7.02392C34.767 9.65731 40.7302 23.326 39.7363 31.9786C39.2337 36.3543 34.1459 54.2997 31.1643 51.6663C22.468 45.0201 18.6789 33.6715 17.3744 30.8499C16.2812 28.4853 15.3867 18.31 15.014 15.6766C14.6413 13.0432 12.9641 8.27783 10.79 8.65412C8.61602 9.0304 5.86595 15.8311 4.45422 22.3228C3.33612 27.4642 4.45422 40.0042 5.94496 47.6535C7.37238 54.9779 9.79624 56.3761 10.79 62.9522Z'
    ],
    pulp: 'M37.2839 74.5841C36.8698 73.8758 36.2902 72.1841 37.2839 71.0841C38.526 69.7091 46.9105 56.2089 48.5253 44.4588C51.1959 32.146 44.1778 14.3333 40.1408 10.7085C38.7124 12.271 46.9726 27.3962 45.1094 39.2088C43.9915 47.9589 39.8924 61.5835 31.3216 68.0838C25.7321 65.2713 18.3413 47.9586 14.4286 32.146C11.5574 23.0066 11.3488 14.4022 11.0748 14.3333C10.3295 14.1458 9.28612 26.6834 11.0748 35.5835C13.3106 46.7086 17.7823 56.8962 23.9309 68.0838C24.9246 72.7839 24.3657 73.7714 24.3657 75.0839',
    pulpTwoThirds: 'M35 52C35 50 42 40 44 32C46 24 42 12 40 10C39 11 44 22 43 30C42 38 38 48 32 52C28 50 20 35 16 25C13 18 12 12 12 12C11 12 11 22 12 28C14 38 18 45 24 52C25 55 25 55 25 55',
    pulpHalf: 'M34 38C34 36 38 30 40 24C42 18 40 10 39 8C38 9 40 16 40 22C39 28 36 36 32 40C29 38 23 28 20 20C18 15 17 10 17 10C16 10 16 18 17 22C18 30 21 35 25 40C26 42 26 42 26 42',
    highlight: [],
    gumLine: 'M 0,78 Q 33,88 66,78',
    anchors: {
      crownCenter: { x: 33, y: 100 },
      apex: { x: 33, y: 5 },
      beyondApex: { x: 33, y: -8 },
      aboveCrown: { x: 33, y: 118 },
      besideCrown: { x: 62, y: 100 },
      rootCenter: { x: 33, y: 42 }
    }
  },
  // Position 8: Third Molar (tooth 18) - viewBox 67x104
  8: {
    viewBox: '0 0 67 104',
    crown: 'M58.1322 63.4319C48.1437 53.9492 13.933 57.9421 8.18956 62.1842C5.31786 66.2599 -0.100915 76.682 1.19759 85.7652C2.33379 93.7129 8.96183 100.615 11.9353 100.987C17.9284 101.735 27.5423 95.3723 33.7851 96.3704C40.028 97.3686 44.0234 103.357 48.7679 102.983C53.5125 102.609 59.8802 99.3649 64.6247 92.8769C69.3693 82.1469 60.5045 70.7928 58.1322 63.4319Z',
    roots: [
      'M30.9758 1.09548C28.5411 1.78154 24.8995 7.08434 24.4209 9.70447C24.2544 20.4602 25.9192 41.1732 33.91 37.9792C41.9008 34.7851 41.4846 20.8761 40.2777 14.3209C39.5285 12.2622 34.1616 0.197776 30.9758 1.09548Z',
      'M40.877 4.12291C58.0573 11.4094 58.1489 46.1284 56.9835 62.1402C38.3215 55.4866 27.3562 55.8281 7.04093 63C9.63795 60.5048 10.1207 54.0303 10.0375 52.1586C9.74852 45.6613 6.60782 42.3046 7.04093 31.8214C7.9399 10.0619 15.1566 3.54066 18.6526 3C24.1687 3 27.3814 27.6287 32.1621 35.9891C32.4602 36.5103 33.1208 36.5476 33.4394 36.0387C34.5725 34.2284 36.4464 30.1401 38.3799 24.5852C41.3765 15.9762 35.7579 2.25139 40.877 4.12291Z'
    ],
    pulp: 'M42.0257 57.817C47.6443 47.9604 55.5102 24.5289 42.0257 9.65659C40.5274 7.78507 43.961 19.3885 43.3367 30.8048C42.5876 38.1661 40.5274 51.5788 34.6592 52.8265C31.08 51.9738 23.4096 46.8624 21.362 33.2378C19.558 21.2342 19.5274 12.3845 19.8019 8.34397C19.8479 7.66557 19.2514 7.21362 18.7915 7.71442C16.2381 10.4948 13.7475 20.5912 15.4313 33.2378C17.8659 44.0926 24.7955 56.7565 26.8556 57.817',
    pulpTwoThirds: 'M40 42C44 35 48 20 40 10C39 9 42 16 41 25C40 32 38 40 34 42C32 41 26 35 23 26C21 18 20 12 20 10C20 9 19 10 19 12C18 18 18 28 21 36C24 44 27 48 28 48',
    pulpHalf: 'M38 30C42 24 44 15 40 8C39 7 40 12 40 18C39 24 37 30 34 32C32 31 28 26 25 20C23 14 22 10 22 8C22 7 21 8 21 10C20 14 21 22 23 28C25 34 27 36 28 36',
    highlight: [],
    gumLine: 'M 0,63 Q 33,73 67,63',
    anchors: {
      crownCenter: { x: 33, y: 82 },
      apex: { x: 33, y: 5 },
      beyondApex: { x: 33, y: -8 },
      aboveCrown: { x: 33, y: 100 },
      besideCrown: { x: 62, y: 82 },
      rootCenter: { x: 33, y: 35 }
    }
  }
}

// ============================================================================
// OCCLUSAL VIEW PATHS (ViewBox: 0 0 50 50)
// Anatomically shaped outlines per tooth category with 5 treatment zones
// (O center + M/D/V/L outer sectors). Quadrant symmetry via CSS transform.
// ============================================================================

interface Point {
  x: number
  y: number
}

interface OcclusalPaths {
  outline: string
  highlight: string[]
  surfaces: Record<string, string>
  surfaceCenters: Record<string, Point>
}

function pointStr(p: Point): string {
  return `${p.x},${p.y}`
}

/** Build 5-sector surface paths from outer/inner corner points (Q1 orientation). */
function buildOcclusalSurfaces(outer: Point[], inner: Point[]): Record<string, string> {
  const [otl, otr, obr, obl] = outer
  const [itl, itr, ibr, ibl] = inner
  return {
    O: `M ${pointStr(itr)} L ${pointStr(itl)} L ${pointStr(ibl)} L ${pointStr(ibr)} Z`,
    V: `M ${pointStr(itl)} L ${pointStr(itr)} L ${pointStr(otr)} L ${pointStr(otl)} Z`,
    L: `M ${pointStr(ibl)} L ${pointStr(obl)} L ${pointStr(obr)} L ${pointStr(ibr)} Z`,
    M: `M ${pointStr(itl)} L ${pointStr(otl)} L ${pointStr(obl)} L ${pointStr(ibl)} Z`,
    D: `M ${pointStr(itr)} L ${pointStr(obr)} L ${pointStr(otr)} L ${pointStr(itr)} Z`
  }
}

function buildOcclusalDividers(outer: Point[], inner: Point[]): string[] {
  const [otl, otr, obr, obl] = outer
  const [itl, itr, ibr, ibl] = inner
  return [
    `M ${pointStr(itl)} L ${pointStr(otl)}`,
    `M ${pointStr(itr)} L ${pointStr(otr)}`,
    `M ${pointStr(ibl)} L ${pointStr(obl)}`,
    `M ${pointStr(ibr)} L ${pointStr(obr)}`,
    `M ${pointStr(itr)} L ${pointStr(itl)} L ${pointStr(ibl)} L ${pointStr(ibr)} Z`
  ]
}

function buildOcclusalPaths(
  outline: string,
  outer: Point[],
  inner: Point[],
  highlight: string[],
  surfaceCenters: Record<string, Point>
): OcclusalPaths {
  return {
    outline,
    highlight,
    surfaces: buildOcclusalSurfaces(outer, inner),
    surfaceCenters
  }
}

// Incisor — wide mesio-distal, narrow bucco-lingual (incisal edge toward V)
const INCISOR_OUTER: Point[] = [
  { x: 9, y: 16 }, { x: 41, y: 16 }, { x: 41, y: 34 }, { x: 9, y: 34 }
]
const INCISOR_INNER: Point[] = [
  { x: 20, y: 22 }, { x: 30, y: 22 }, { x: 30, y: 28 }, { x: 20, y: 28 }
]
const OCCLUSAL_INCISOR = buildOcclusalPaths(
  'M 9,18 Q 9,14 13,14 L 37,14 Q 41,14 41,18 L 41,32 Q 41,36 37,36 L 13,36 Q 9,36 9,32 Z',
  INCISOR_OUTER,
  INCISOR_INNER,
  [
    'M 13,32 Q 25,34 37,32',
    ...buildOcclusalDividers(INCISOR_OUTER, INCISOR_INNER)
  ],
  { O: { x: 25, y: 25 }, M: { x: 14, y: 25 }, D: { x: 36, y: 25 }, V: { x: 25, y: 17 }, L: { x: 25, y: 33 } }
)

// Canine — cuspal diamond with buccal cusp toward V
const CANINE_OUTER: Point[] = [
  { x: 10, y: 9 }, { x: 40, y: 9 }, { x: 40, y: 41 }, { x: 10, y: 41 }
]
const CANINE_INNER: Point[] = [
  { x: 20, y: 22 }, { x: 30, y: 22 }, { x: 30, y: 28 }, { x: 20, y: 28 }
]
const OCCLUSAL_CANINE = buildOcclusalPaths(
  'M 25,8 Q 36,12 40,25 Q 36,38 25,42 Q 14,38 10,25 Q 14,12 25,8 Z',
  CANINE_OUTER,
  CANINE_INNER,
  [
    'M 25,8 L 25,28',
    ...buildOcclusalDividers(CANINE_OUTER, CANINE_INNER)
  ],
  { O: { x: 25, y: 25 }, M: { x: 15, y: 25 }, D: { x: 35, y: 25 }, V: { x: 25, y: 14 }, L: { x: 25, y: 36 } }
)

// Premolar — oval with buccal and lingual cusps
const PREMOLAR_OUTER: Point[] = [
  { x: 13, y: 13 }, { x: 37, y: 13 }, { x: 37, y: 37 }, { x: 13, y: 37 }
]
const PREMOLAR_INNER: Point[] = [
  { x: 20, y: 20 }, { x: 30, y: 20 }, { x: 30, y: 30 }, { x: 20, y: 30 }
]
const OCCLUSAL_PREMOLAR = buildOcclusalPaths(
  'M 14,12 Q 25,10 36,12 Q 40,25 36,38 Q 25,40 14,38 Q 10,25 14,12 Z',
  PREMOLAR_OUTER,
  PREMOLAR_INNER,
  [
    'M 18,19 Q 25,17 32,19',
    'M 20,31 Q 25,33 30,31',
    'M 25,17 L 25,33',
    ...buildOcclusalDividers(PREMOLAR_OUTER, PREMOLAR_INNER)
  ],
  { O: { x: 25, y: 25 }, M: { x: 15, y: 25 }, D: { x: 35, y: 25 }, V: { x: 25, y: 15 }, L: { x: 25, y: 35 } }
)

// Molar — squarish with four cusps and central cross fissure
const MOLAR_OUTER: Point[] = [
  { x: 11, y: 11 }, { x: 39, y: 11 }, { x: 39, y: 39 }, { x: 11, y: 39 }
]
const MOLAR_INNER: Point[] = [
  { x: 19, y: 19 }, { x: 31, y: 19 }, { x: 31, y: 31 }, { x: 19, y: 31 }
]
const OCCLUSAL_MOLAR = buildOcclusalPaths(
  'M 12,13 Q 12,11 14,11 L 36,11 Q 38,11 38,13 L 38,37 Q 38,39 36,39 L 14,39 Q 12,39 12,37 Z',
  MOLAR_OUTER,
  MOLAR_INNER,
  [
    'M 25,13 L 25,37',
    'M 13,25 L 37,25',
    'M 17,17 L 33,33',
    'M 33,17 L 17,33',
    ...buildOcclusalDividers(MOLAR_OUTER, MOLAR_INNER)
  ],
  { O: { x: 25, y: 25 }, M: { x: 13, y: 25 }, D: { x: 37, y: 25 }, V: { x: 25, y: 13 }, L: { x: 25, y: 37 } }
)

// Quadrant symmetry is handled by CSS transform (napkin unfolding)
const OCCLUSAL_PATHS_BY_POSITION: Record<ToothPosition, OcclusalPaths> = {
  1: OCCLUSAL_INCISOR,
  2: OCCLUSAL_INCISOR,
  3: OCCLUSAL_CANINE,
  4: OCCLUSAL_PREMOLAR,
  5: OCCLUSAL_PREMOLAR,
  6: OCCLUSAL_MOLAR,
  7: OCCLUSAL_MOLAR,
  8: OCCLUSAL_MOLAR
}

// ============================================================================
// DECIDUOUS TEETH (Simplified versions using permanent tooth shapes)
// ============================================================================

// Map deciduous positions to permanent tooth shapes
const DECIDUOUS_TO_PERMANENT_MAP: Record<number, ToothPosition> = {
  1: 1, // Deciduous central incisor → Central incisor
  2: 2, // Deciduous lateral incisor → Lateral incisor
  3: 3, // Deciduous canine → Canine
  4: 6, // First deciduous molar → First molar shape
  5: 7 // Second deciduous molar → Second molar shape
}

// ============================================================================
// PATH GETTER FUNCTIONS
// ============================================================================

export function getLateralPath(toothNumber: number): LateralPaths {
  return LATERAL_PATHS_BY_POSITION[getShapePosition(toothNumber)]
}

export function getOcclusalPath(toothNumber: number): OcclusalPaths {
  return OCCLUSAL_PATHS_BY_POSITION[getShapePosition(toothNumber)]
}

/** Center point for dot-style occlusal treatment overlays. */
export function getOcclusalSurfaceCenter(toothNumber: number, surface: string): Point {
  const paths = getOcclusalPath(toothNumber)
  return paths.surfaceCenters[surface] ?? { x: 25, y: 25 }
}

// ============================================================================
// TREATMENT OVERLAYS
// ============================================================================

export const TREATMENT_OVERLAYS = {
  implant: {
    fixture: 'M 22,35 L 20,75 Q 30,82 40,75 L 38,35 Z',
    threads: [
      'M 18,42 L 42,42',
      'M 16,52 L 44,52',
      'M 14,62 L 46,62',
      'M 16,72 L 44,72'
    ],
    abutment: 'M 24,28 L 24,35 L 36,35 L 36,28 C 36,24 24,24 24,28 Z',
    head: 'M 22,20 Q 30,16 38,20 L 38,28 C 38,30 22,30 22,28 Z'
  },
  crownOverlay: {
    outer: 'M 10,50 C 5,40 5,25 10,15 C 18,5 25,3 30,3 C 35,3 42,5 50,15 C 55,25 55,40 50,50 Z',
    metalBand: 'M 12,50 Q 30,55 48,50 L 50,40 Q 30,35 10,40 Z'
  },
  rootCanal: {
    indicator: 'M 30,55 m -5,0 a 5,5 0 1,0 10,0 a 5,5 0 1,0 -10,0',
    canalLines: [
      'M 30,45 L 30,65',
      'M 26,50 L 34,50',
      'M 26,60 L 34,60'
    ]
  },
  post: {
    shaft: 'M 28,35 L 28,60 L 32,60 L 32,35 Z'
  },
  veneer: {
    surface: 'M 15,55 C 10,45 10,35 15,25 Q 30,20 45,25 C 50,35 50,45 45,55 Q 30,60 15,55 Z'
  },
  missing: {
    line1: 'M 10,10 L 50,90',
    line2: 'M 50,10 L 10,90'
  },
  extraction: {
    line1: 'M 15,15 L 45,85',
    line2: 'M 45,15 L 15,85',
    dashArray: '5,4'
  }
}

// ============================================================================
// STATUS STYLES (re-exported from odontogramConstants for backwards compatibility)
// ============================================================================

// Convert from odontogramConstants format to local format
interface StatusStyle {
  opacity: number
  border: string
  borderWidth: number
  borderDash?: string
}

function toStatusStyle(value: typeof STATUS_STYLES_CONFIG[TreatmentStatus]): StatusStyle {
  return {
    opacity: value.opacity,
    border: value.border || 'none',
    borderWidth: value.borderWidth,
    ...(value.borderDash ? { borderDash: value.borderDash } : {})
  }
}

export const STATUS_STYLES: Record<TreatmentStatus, StatusStyle> = {
  existing: toStatusStyle(STATUS_STYLES_CONFIG.existing),
  planned: toStatusStyle(STATUS_STYLES_CONFIG.planned)
}
