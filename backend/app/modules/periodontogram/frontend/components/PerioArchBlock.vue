<script setup lang="ts">
/**
 * One arch (upper or lower) of the SEPA layout.
 *
 * Spreadsheet-style inline editing — every cell is directly
 * actionable without a modal:
 *
 * - Numeric fields (Sondaje, Margen, Anchura encía) render as
 *   `<input type="number">` styled to look like a value at rest.
 *   Focus selects the value; Tab advances; blur commits via
 *   `editSite` / `editTooth`.
 * - Toggle fields (Sangrado, Placa) are single-click squares that
 *   flip their boolean.
 * - Enum fields (Movilidad, Pronóstico, Furca V/L) cycle through
 *   their value space on each click — null → first value → next →
 *   wraps back to null.
 * - Implante is a single-click toggle (mostly pre-filled from the
 *   odontogram, override stays local).
 *
 * Alignment is enforced by a `table-fixed` table with an explicit
 * `<colgroup>` — every metric cell shares its column with the tooth
 * directly above or below it, so a vertical scan reads cleanly per
 * FDI number.
 */
import { computed } from 'vue'
import type { Furcation, PerioSite, PerioTooth, Prognosis, SiteCode } from '../types'
import { PALATAL_SITES, VESTIBULAR_SITES } from '../types'

const props = defineProps<{
  arch: 'upper' | 'lower'
  teeth: PerioTooth[]
  readonly?: boolean
}>()

const emit = defineEmits<{
  editTooth: [toothNumber: number, patch: Record<string, unknown>]
  editSite: [toothNumber: number, siteCode: SiteCode, patch: Record<string, unknown>]
}>()

const { t } = useI18n()

// ---------------------------------------------------------------------------
// Ordering
// ---------------------------------------------------------------------------

const orderedTeeth = computed(() => {
  const quadrants = props.arch === 'upper' ? [1, 2] : [4, 3]
  const out: PerioTooth[] = []
  for (const q of quadrants) {
    const quadrantTeeth = props.teeth.filter(t => Math.floor(t.tooth_number / 10) === q)
    quadrantTeeth.sort((a, b) => {
      const pa = a.tooth_number % 10
      const pb = b.tooth_number % 10
      return q === 1 || q === 4 ? pb - pa : pa - pb
    })
    out.push(...quadrantTeeth)
  }
  return out
})

// Pixel width of the strip overlay = tooth columns only (label column
// is offset via `left`). Mirrors the <col style="width: 60px"> entries
// in the <colgroup>.
const TOOTH_COL_PX = 60
const profileOverlayWidth = computed(() => `${orderedTeeth.value.length * TOOTH_COL_PX}px`)

const heading = computed(() => t(props.arch === 'upper' ? 'periodontogram.arch.upper' : 'periodontogram.arch.lower'))
const innerFace = computed<'palatal' | 'lingual'>(() =>
  props.arch === 'upper' ? 'palatal' : 'lingual'
)
const innerFaceLabel = computed(() => t(props.arch === 'upper' ? 'periodontogram.arch.palatal' : 'periodontogram.arch.lingual'))
const innerSites = PALATAL_SITES

// ---------------------------------------------------------------------------
// Read helpers
// ---------------------------------------------------------------------------

function siteValue(tooth: PerioTooth, code: SiteCode): PerioSite | null {
  return tooth.sites.find(s => s.site_code === code) ?? null
}

// ---------------------------------------------------------------------------
// Cycle definitions for enum fields. Click cycles forward; null wraps
// back to the head — gives the dentist a single mouse target with
// keyboard friendliness (a value clears via the same button).
// ---------------------------------------------------------------------------

const MOBILITY_CYCLE: Array<number | null> = [null, 0, 1, 2, 3]
const PROGNOSIS_CYCLE: Array<Prognosis | null> = [null, 'good', 'fair', 'poor', 'hopeless']
const FURCA_CYCLE: Array<Furcation | null> = [null, '0', 'I', 'II', 'III']

function nextInCycle<T>(cycle: T[], current: T): T {
  const idx = cycle.findIndex(v => v === current)
  if (idx === -1) return cycle[1] ?? cycle[0]
  return cycle[(idx + 1) % cycle.length]
}

function prognosisGlyph(v: Prognosis | null | undefined): string {
  if (v === 'good') return 'B'
  if (v === 'fair') return 'M'
  if (v === 'poor') return 'D'
  if (v === 'hopeless') return '✕'
  return '·'
}

function mobilityGlyph(v: number | null | undefined): string {
  return v == null ? '·' : String(v)
}

function furcaGlyph(v: Furcation | null | undefined): string {
  return v ?? '·'
}

// ---------------------------------------------------------------------------
// Input parsing for numeric fields. Empty string clears the value.
// ---------------------------------------------------------------------------

function parseIntOrNull(raw: string): number | null {
  if (raw.trim() === '') return null
  const n = Number(raw)
  if (!Number.isFinite(n)) return null
  return Math.round(n)
}

// ---------------------------------------------------------------------------
// Event handlers
// ---------------------------------------------------------------------------

function onSiteNumberInput(
  toothNumber: number,
  code: SiteCode,
  field: 'probing_depth_mm' | 'gingival_margin_mm',
  e: Event
) {
  if (props.readonly) return
  const raw = (e.target as HTMLInputElement).value
  emit('editSite', toothNumber, code, { [field]: parseIntOrNull(raw) })
}

function onSiteToggle(
  toothNumber: number,
  code: SiteCode,
  field: 'bleeding_on_probing' | 'plaque',
  current: boolean | undefined
) {
  if (props.readonly) return
  emit('editSite', toothNumber, code, { [field]: !current })
}

function onToothNumberInput(
  toothNumber: number,
  field: 'keratinized_gingiva_mm',
  e: Event
) {
  if (props.readonly) return
  const raw = (e.target as HTMLInputElement).value
  emit('editTooth', toothNumber, { [field]: parseIntOrNull(raw) })
}

function onToothCycle(
  tooth: PerioTooth,
  field: 'mobility' | 'prognosis' | 'furcation_buccal' | 'furcation_lingual'
) {
  if (props.readonly || !tooth.is_present) return
  if (field === 'mobility') {
    emit('editTooth', tooth.tooth_number, { mobility: nextInCycle(MOBILITY_CYCLE, tooth.mobility ?? null) })
  } else if (field === 'prognosis') {
    emit('editTooth', tooth.tooth_number, { prognosis: nextInCycle(PROGNOSIS_CYCLE, tooth.prognosis ?? null) })
  } else if (field === 'furcation_buccal') {
    emit('editTooth', tooth.tooth_number, { furcation_buccal: nextInCycle(FURCA_CYCLE, tooth.furcation_buccal ?? null) })
  } else {
    emit('editTooth', tooth.tooth_number, { furcation_lingual: nextInCycle(FURCA_CYCLE, tooth.furcation_lingual ?? null) })
  }
}

function onImplantToggle(tooth: PerioTooth) {
  if (props.readonly) return
  emit('editTooth', tooth.tooth_number, { is_implant: !tooth.is_implant })
}

// ---------------------------------------------------------------------------
// Focus auto-select — typing immediately overwrites the previous value
// instead of appending characters.
// ---------------------------------------------------------------------------

function selectOnFocus(e: FocusEvent) {
  const target = e.target as HTMLInputElement
  if (target?.select) target.select()
}
</script>

<template>
  <section class="perio-arch-block rounded-lg border border-default bg-surface">
    <header class="flex items-center justify-between px-3 py-2">
      <h4 class="text-xs font-semibold uppercase tracking-wide text-muted">{{ heading }}</h4>
      <span class="text-[10px] text-subtle">
        {{ t('periodontogram.arch.vestibular') }} (MV V DV) ↔ {{ innerFaceLabel }} (ML L DL)
      </span>
    </header>

    <table
      class="perio-arch-table table-fixed border-collapse text-center font-mono text-[11px] leading-tight"
    >
      <colgroup>
        <col style="width: 96px" />
        <col v-for="tooth in orderedTeeth" :key="`col-${tooth.tooth_number}`" style="width: 60px" />
      </colgroup>

      <thead v-if="arch === 'upper'">
        <tr>
          <th class="px-1 text-right font-medium text-muted"></th>
          <th
            v-for="tooth in orderedTeeth"
            :key="`fdi-${tooth.tooth_number}`"
            class="px-1 py-1 font-medium text-default"
          >
            {{ tooth.tooth_number }}
          </th>
        </tr>
      </thead>

      <!-- ============== UPPER ARCH ============== -->
      <tbody v-if="arch === 'upper'" class="divide-y divide-gray-100 dark:divide-gray-800">
        <!-- Implante (toggle ● / ·) -->
        <tr>
          <th scope="row" class="px-1 text-right font-medium text-muted">{{ t('periodontogram.arch.implant') }}</th>
          <td v-for="tooth in orderedTeeth" :key="`imp-${tooth.tooth_number}`" class="px-1">
            <button
              class="perio-cell-cycle"
              :class="{ 'text-emerald-600 dark:text-emerald-400': tooth.is_implant }"
              :disabled="readonly"
              :title="tooth.is_implant ? t('periodontogram.arch.implantToggleOn') : t('periodontogram.arch.implantToggleOff')"
              @click="onImplantToggle(tooth)"
            >
              {{ tooth.is_implant ? '●' : '·' }}
            </button>
          </td>
        </tr>

        <!-- Mobility (cycle 0..3 + null) -->
        <tr>
          <th scope="row" class="px-1 text-right font-medium text-muted">{{ t('periodontogram.arch.mobility') }}</th>
          <td v-for="tooth in orderedTeeth" :key="`mob-${tooth.tooth_number}`" class="px-1">
            <button
              class="perio-cell-cycle"
              :disabled="readonly || !tooth.is_present"
              :title="t('periodontogram.arch.mobilityTitle')"
              @click="onToothCycle(tooth, 'mobility')"
            >
              {{ mobilityGlyph(tooth.mobility) }}
            </button>
          </td>
        </tr>

        <!-- Prognosis cycle -->
        <tr>
          <th scope="row" class="px-1 text-right font-medium text-muted">{{ t('periodontogram.arch.prognosis') }}</th>
          <td v-for="tooth in orderedTeeth" :key="`pron-${tooth.tooth_number}`" class="px-1">
            <button
              class="perio-cell-cycle"
              :disabled="readonly || !tooth.is_present"
              :title="t('periodontogram.arch.prognosisTitle')"
              @click="onToothCycle(tooth, 'prognosis')"
            >
              {{ prognosisGlyph(tooth.prognosis) }}
            </button>
          </td>
        </tr>

        <!-- Furca V / L cycles -->
        <tr>
          <th scope="row" class="px-1 text-right font-medium text-muted">{{ t('periodontogram.arch.furcaV') }}</th>
          <td v-for="tooth in orderedTeeth" :key="`furv-${tooth.tooth_number}`" class="px-1">
            <button
              class="perio-cell-cycle"
              :disabled="readonly || !tooth.is_present"
              :title="t('periodontogram.arch.furcaVTitle')"
              @click="onToothCycle(tooth, 'furcation_buccal')"
            >
              {{ furcaGlyph(tooth.furcation_buccal) }}
            </button>
          </td>
        </tr>
        <tr>
          <th scope="row" class="px-1 text-right font-medium text-muted">{{ t('periodontogram.arch.furcaLP') }}</th>
          <td v-for="tooth in orderedTeeth" :key="`furl-${tooth.tooth_number}`" class="px-1">
            <button
              class="perio-cell-cycle"
              :disabled="readonly || !tooth.is_present"
              :title="t('periodontogram.arch.furcaLPTitle')"
              @click="onToothCycle(tooth, 'furcation_lingual')"
            >
              {{ furcaGlyph(tooth.furcation_lingual) }}
            </button>
          </td>
        </tr>

        <!-- Gingival width (numeric input) -->
        <tr>
          <th scope="row" class="px-1 text-right font-medium text-muted">{{ t('periodontogram.arch.gingivalWidth') }}</th>
          <td v-for="tooth in orderedTeeth" :key="`kg-${tooth.tooth_number}`" class="px-1">
            <input
              type="number"
              min="0"
              max="20"
              :value="tooth.keratinized_gingiva_mm ?? ''"
              :disabled="readonly || !tooth.is_present"
              class="perio-cell-input"
              @focus="selectOnFocus"
              @change="(e) => onToothNumberInput(tooth.tooth_number, 'keratinized_gingiva_mm', e)"
            />
          </td>
        </tr>

        <!-- Vestibular site metrics — amber tint, sits above the V tooth row -->
        <tr v-for="row in [
          { kind: 'site-pd', label: t('periodontogram.arch.probing') },
          { kind: 'site-gm', label: t('periodontogram.arch.margin') },
          { kind: 'site-plaque', label: t('periodontogram.arch.plaque') },
          { kind: 'site-bop', label: t('periodontogram.arch.bleeding') }
        ]" :key="`v-${row.kind}`" class="perio-row-vestibular">
          <th scope="row" class="px-1 text-right font-medium text-amber-700 dark:text-amber-400">
            {{ row.label }} <span class="text-[9px] text-amber-500 dark:text-amber-300/80">V</span>
          </th>
          <td v-for="tooth in orderedTeeth" :key="`v-${row.kind}-${tooth.tooth_number}`" class="px-1">
            <div class="flex items-center justify-center gap-0.5 tabular-nums">
              <template v-for="code in VESTIBULAR_SITES" :key="`v-${row.kind}-${tooth.tooth_number}-${code}`">
                <input
                  v-if="row.kind === 'site-pd'"
                  type="number"
                  min="0"
                  max="15"
                  :value="siteValue(tooth, code)?.probing_depth_mm ?? ''"
                  :disabled="readonly || !tooth.is_present"
                  class="perio-cell-input perio-cell-input--site"
                  :title="t('periodontogram.arch.probingTitle', { code })"
                  @focus="selectOnFocus"
                  @change="(e) => onSiteNumberInput(tooth.tooth_number, code, 'probing_depth_mm', e)"
                />
                <input
                  v-else-if="row.kind === 'site-gm'"
                  type="number"
                  min="-5"
                  max="10"
                  :value="siteValue(tooth, code)?.gingival_margin_mm ?? ''"
                  :disabled="readonly || !tooth.is_present"
                  class="perio-cell-input perio-cell-input--site"
                  :title="t('periodontogram.arch.marginTitle', { code })"
                  @focus="selectOnFocus"
                  @change="(e) => onSiteNumberInput(tooth.tooth_number, code, 'gingival_margin_mm', e)"
                />
                <button
                  v-else-if="row.kind === 'site-plaque'"
                  type="button"
                  class="perio-cell-toggle perio-cell-toggle--plaque"
                  :class="{ 'is-on': siteValue(tooth, code)?.plaque }"
                  :disabled="readonly || !tooth.is_present"
                  :title="t('periodontogram.arch.plaqueTitle', { code })"
                  @click="onSiteToggle(tooth.tooth_number, code, 'plaque', siteValue(tooth, code)?.plaque)"
                />
                <button
                  v-else-if="row.kind === 'site-bop'"
                  type="button"
                  class="perio-cell-toggle perio-cell-toggle--bop"
                  :class="{ 'is-on': siteValue(tooth, code)?.bleeding_on_probing }"
                  :disabled="readonly || !tooth.is_present"
                  :title="t('periodontogram.arch.bleedingTitle', { code })"
                  @click="onSiteToggle(tooth.tooth_number, code, 'bleeding_on_probing', siteValue(tooth, code)?.bleeding_on_probing)"
                />
              </template>
            </div>
          </td>
        </tr>

        <!-- Vestibular tooth row. The label <th> doubles as the
             positioning context for the SEPA profile overlay, which
             absolute-positions itself over the tooth cells to the
             right and renders gridlines + polylines directly on top
             of the rendered root area of the tooth silhouettes. -->
        <tr class="tooth-row">
          <th
            scope="row"
            class="px-1 text-right text-[10px] font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-400 perio-row-anchor"
          >
            {{ t('periodontogram.arch.vestibular') }}
            <div class="perio-profile-anchor perio-profile-anchor--top" :style="{ width: profileOverlayWidth }">
              <PerioProfileStrip
                :teeth="orderedTeeth"
                face="vestibular"
                direction="depth-up"
              />
            </div>
          </th>
          <td v-for="tooth in orderedTeeth" :key="`v-tooth-${tooth.tooth_number}`" class="px-0 align-top">
            <PerioToothLateral :tooth="tooth" face="vestibular" :readonly="readonly" />
          </td>
        </tr>

        <!-- Palatal tooth row. Overlay extends from bottom upward
             because the palatal face is flipped: root renders down. -->
        <tr class="tooth-row">
          <th
            scope="row"
            class="px-1 text-right text-[10px] font-semibold uppercase tracking-wide text-sky-700 dark:text-sky-400 perio-row-anchor"
          >
            {{ innerFaceLabel }}
            <div class="perio-profile-anchor perio-profile-anchor--bottom" :style="{ width: profileOverlayWidth }">
              <PerioProfileStrip
                :teeth="orderedTeeth"
                :face="innerFace"
                direction="depth-down"
              />
            </div>
          </th>
          <td v-for="tooth in orderedTeeth" :key="`p-tooth-${tooth.tooth_number}`" class="px-0 align-top">
            <PerioToothLateral
              :tooth="tooth"
              :face="innerFace"
              :readonly="readonly"
              markers-position="above"
            />
          </td>
        </tr>

        <!-- Palatal site metrics — sky tint -->
        <tr v-for="row in [
          { kind: 'site-bop', label: t('periodontogram.arch.bleeding') },
          { kind: 'site-plaque', label: t('periodontogram.arch.plaque') },
          { kind: 'site-gm', label: t('periodontogram.arch.margin') },
          { kind: 'site-pd', label: t('periodontogram.arch.probing') }
        ]" :key="`p-${row.kind}`" class="perio-row-palatal">
          <th scope="row" class="px-1 text-right font-medium text-sky-700 dark:text-sky-400">
            {{ row.label }} <span class="text-[9px] text-sky-500 dark:text-sky-300/80">{{ innerFaceLabel.charAt(0) }}</span>
          </th>
          <td v-for="tooth in orderedTeeth" :key="`p-${row.kind}-${tooth.tooth_number}`" class="px-1">
            <div class="flex items-center justify-center gap-0.5 tabular-nums">
              <template v-for="code in innerSites" :key="`p-${row.kind}-${tooth.tooth_number}-${code}`">
                <input
                  v-if="row.kind === 'site-pd'"
                  type="number"
                  min="0"
                  max="15"
                  :value="siteValue(tooth, code)?.probing_depth_mm ?? ''"
                  :disabled="readonly || !tooth.is_present"
                  class="perio-cell-input perio-cell-input--site"
                  :title="t('periodontogram.arch.probingTitle', { code })"
                  @focus="selectOnFocus"
                  @change="(e) => onSiteNumberInput(tooth.tooth_number, code, 'probing_depth_mm', e)"
                />
                <input
                  v-else-if="row.kind === 'site-gm'"
                  type="number"
                  min="-5"
                  max="10"
                  :value="siteValue(tooth, code)?.gingival_margin_mm ?? ''"
                  :disabled="readonly || !tooth.is_present"
                  class="perio-cell-input perio-cell-input--site"
                  :title="t('periodontogram.arch.marginTitle', { code })"
                  @focus="selectOnFocus"
                  @change="(e) => onSiteNumberInput(tooth.tooth_number, code, 'gingival_margin_mm', e)"
                />
                <button
                  v-else-if="row.kind === 'site-plaque'"
                  type="button"
                  class="perio-cell-toggle perio-cell-toggle--plaque"
                  :class="{ 'is-on': siteValue(tooth, code)?.plaque }"
                  :disabled="readonly || !tooth.is_present"
                  :title="t('periodontogram.arch.plaqueTitle', { code })"
                  @click="onSiteToggle(tooth.tooth_number, code, 'plaque', siteValue(tooth, code)?.plaque)"
                />
                <button
                  v-else-if="row.kind === 'site-bop'"
                  type="button"
                  class="perio-cell-toggle perio-cell-toggle--bop"
                  :class="{ 'is-on': siteValue(tooth, code)?.bleeding_on_probing }"
                  :disabled="readonly || !tooth.is_present"
                  :title="t('periodontogram.arch.bleedingTitle', { code })"
                  @click="onSiteToggle(tooth.tooth_number, code, 'bleeding_on_probing', siteValue(tooth, code)?.bleeding_on_probing)"
                />
              </template>
            </div>
          </td>
        </tr>
      </tbody>

      <!-- ============== LOWER ARCH (mirror) ============== -->
      <tbody v-else class="divide-y divide-gray-100 dark:divide-gray-800">
        <!-- Lingual site metrics on top -->
        <tr v-for="row in [
          { kind: 'site-pd', label: t('periodontogram.arch.probing') },
          { kind: 'site-gm', label: t('periodontogram.arch.margin') },
          { kind: 'site-plaque', label: t('periodontogram.arch.plaque') },
          { kind: 'site-bop', label: t('periodontogram.arch.bleeding') }
        ]" :key="`l-${row.kind}`" class="perio-row-palatal">
          <th scope="row" class="px-1 text-right font-medium text-sky-700 dark:text-sky-400">
            {{ row.label }} <span class="text-[9px] text-sky-500 dark:text-sky-300/80">L</span>
          </th>
          <td v-for="tooth in orderedTeeth" :key="`l-${row.kind}-${tooth.tooth_number}`" class="px-1">
            <div class="flex items-center justify-center gap-0.5 tabular-nums">
              <template v-for="code in innerSites" :key="`l-${row.kind}-${tooth.tooth_number}-${code}`">
                <input
                  v-if="row.kind === 'site-pd'"
                  type="number"
                  min="0"
                  max="15"
                  :value="siteValue(tooth, code)?.probing_depth_mm ?? ''"
                  :disabled="readonly || !tooth.is_present"
                  class="perio-cell-input perio-cell-input--site"
                  :title="t('periodontogram.arch.probingTitle', { code })"
                  @focus="selectOnFocus"
                  @change="(e) => onSiteNumberInput(tooth.tooth_number, code, 'probing_depth_mm', e)"
                />
                <input
                  v-else-if="row.kind === 'site-gm'"
                  type="number"
                  min="-5"
                  max="10"
                  :value="siteValue(tooth, code)?.gingival_margin_mm ?? ''"
                  :disabled="readonly || !tooth.is_present"
                  class="perio-cell-input perio-cell-input--site"
                  :title="t('periodontogram.arch.marginTitle', { code })"
                  @focus="selectOnFocus"
                  @change="(e) => onSiteNumberInput(tooth.tooth_number, code, 'gingival_margin_mm', e)"
                />
                <button
                  v-else-if="row.kind === 'site-plaque'"
                  type="button"
                  class="perio-cell-toggle perio-cell-toggle--plaque"
                  :class="{ 'is-on': siteValue(tooth, code)?.plaque }"
                  :disabled="readonly || !tooth.is_present"
                  :title="t('periodontogram.arch.plaqueTitle', { code })"
                  @click="onSiteToggle(tooth.tooth_number, code, 'plaque', siteValue(tooth, code)?.plaque)"
                />
                <button
                  v-else-if="row.kind === 'site-bop'"
                  type="button"
                  class="perio-cell-toggle perio-cell-toggle--bop"
                  :class="{ 'is-on': siteValue(tooth, code)?.bleeding_on_probing }"
                  :disabled="readonly || !tooth.is_present"
                  :title="t('periodontogram.arch.bleedingTitle', { code })"
                  @click="onSiteToggle(tooth.tooth_number, code, 'bleeding_on_probing', siteValue(tooth, code)?.bleeding_on_probing)"
                />
              </template>
            </div>
          </td>
        </tr>

        <!-- Lingual tooth row — overlay extends from top down (root
             renders upward on the lower-arch lingual face: quadrant
             flip cancels the face flip). -->
        <tr class="tooth-row">
          <th
            scope="row"
            class="px-1 text-right text-[10px] font-semibold uppercase tracking-wide text-sky-700 dark:text-sky-400 perio-row-anchor"
          >
            {{ innerFaceLabel }}
            <div class="perio-profile-anchor perio-profile-anchor--top" :style="{ width: profileOverlayWidth }">
              <PerioProfileStrip
                :teeth="orderedTeeth"
                :face="innerFace"
                direction="depth-up"
              />
            </div>
          </th>
          <td v-for="tooth in orderedTeeth" :key="`l-tooth-${tooth.tooth_number}`" class="px-0 align-bottom">
            <PerioToothLateral :tooth="tooth" :face="innerFace" :readonly="readonly" />
          </td>
        </tr>

        <!-- Vestibular tooth row — overlay extends from bottom up
             (root renders downward on the lower-arch vestibular
             face). -->
        <tr class="tooth-row">
          <th
            scope="row"
            class="px-1 text-right text-[10px] font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-400 perio-row-anchor"
          >
            {{ t('periodontogram.arch.vestibular') }}
            <div class="perio-profile-anchor perio-profile-anchor--bottom" :style="{ width: profileOverlayWidth }">
              <PerioProfileStrip
                :teeth="orderedTeeth"
                face="vestibular"
                direction="depth-down"
              />
            </div>
          </th>
          <td v-for="tooth in orderedTeeth" :key="`v-tooth-${tooth.tooth_number}`" class="px-0 align-top">
            <PerioToothLateral
              :tooth="tooth"
              face="vestibular"
              :readonly="readonly"
              markers-position="above"
            />
          </td>
        </tr>

        <!-- Vestibular site metrics directly below the V tooth row -->
        <tr v-for="row in [
          { kind: 'site-bop', label: t('periodontogram.arch.bleeding') },
          { kind: 'site-plaque', label: t('periodontogram.arch.plaque') },
          { kind: 'site-gm', label: t('periodontogram.arch.margin') },
          { kind: 'site-pd', label: t('periodontogram.arch.probing') }
        ]" :key="`v-${row.kind}`" class="perio-row-vestibular">
          <th scope="row" class="px-1 text-right font-medium text-amber-700 dark:text-amber-400">
            {{ row.label }} <span class="text-[9px] text-amber-500 dark:text-amber-300/80">V</span>
          </th>
          <td v-for="tooth in orderedTeeth" :key="`v-${row.kind}-${tooth.tooth_number}`" class="px-1">
            <div class="flex items-center justify-center gap-0.5 tabular-nums">
              <template v-for="code in VESTIBULAR_SITES" :key="`v-${row.kind}-${tooth.tooth_number}-${code}`">
                <input
                  v-if="row.kind === 'site-pd'"
                  type="number"
                  min="0"
                  max="15"
                  :value="siteValue(tooth, code)?.probing_depth_mm ?? ''"
                  :disabled="readonly || !tooth.is_present"
                  class="perio-cell-input perio-cell-input--site"
                  :title="t('periodontogram.arch.probingTitle', { code })"
                  @focus="selectOnFocus"
                  @change="(e) => onSiteNumberInput(tooth.tooth_number, code, 'probing_depth_mm', e)"
                />
                <input
                  v-else-if="row.kind === 'site-gm'"
                  type="number"
                  min="-5"
                  max="10"
                  :value="siteValue(tooth, code)?.gingival_margin_mm ?? ''"
                  :disabled="readonly || !tooth.is_present"
                  class="perio-cell-input perio-cell-input--site"
                  :title="t('periodontogram.arch.marginTitle', { code })"
                  @focus="selectOnFocus"
                  @change="(e) => onSiteNumberInput(tooth.tooth_number, code, 'gingival_margin_mm', e)"
                />
                <button
                  v-else-if="row.kind === 'site-plaque'"
                  type="button"
                  class="perio-cell-toggle perio-cell-toggle--plaque"
                  :class="{ 'is-on': siteValue(tooth, code)?.plaque }"
                  :disabled="readonly || !tooth.is_present"
                  :title="t('periodontogram.arch.plaqueTitle', { code })"
                  @click="onSiteToggle(tooth.tooth_number, code, 'plaque', siteValue(tooth, code)?.plaque)"
                />
                <button
                  v-else-if="row.kind === 'site-bop'"
                  type="button"
                  class="perio-cell-toggle perio-cell-toggle--bop"
                  :class="{ 'is-on': siteValue(tooth, code)?.bleeding_on_probing }"
                  :disabled="readonly || !tooth.is_present"
                  :title="t('periodontogram.arch.bleedingTitle', { code })"
                  @click="onSiteToggle(tooth.tooth_number, code, 'bleeding_on_probing', siteValue(tooth, code)?.bleeding_on_probing)"
                />
              </template>
            </div>
          </td>
        </tr>

        <!-- Per-tooth metrics (reversed — closest to vestibular row) -->
        <tr>
          <th scope="row" class="px-1 text-right font-medium text-muted">{{ t('periodontogram.arch.gingivalWidth') }}</th>
          <td v-for="tooth in orderedTeeth" :key="`kg-${tooth.tooth_number}`" class="px-1">
            <input
              type="number"
              min="0"
              max="20"
              :value="tooth.keratinized_gingiva_mm ?? ''"
              :disabled="readonly || !tooth.is_present"
              class="perio-cell-input"
              @focus="selectOnFocus"
              @change="(e) => onToothNumberInput(tooth.tooth_number, 'keratinized_gingiva_mm', e)"
            />
          </td>
        </tr>
        <tr>
          <th scope="row" class="px-1 text-right font-medium text-muted">{{ t('periodontogram.arch.furcaLP') }}</th>
          <td v-for="tooth in orderedTeeth" :key="`furl-${tooth.tooth_number}`" class="px-1">
            <button
              class="perio-cell-cycle"
              :disabled="readonly || !tooth.is_present"
              :title="t('periodontogram.arch.furcaLPTitle')"
              @click="onToothCycle(tooth, 'furcation_lingual')"
            >{{ furcaGlyph(tooth.furcation_lingual) }}</button>
          </td>
        </tr>
        <tr>
          <th scope="row" class="px-1 text-right font-medium text-muted">{{ t('periodontogram.arch.furcaV') }}</th>
          <td v-for="tooth in orderedTeeth" :key="`furv-${tooth.tooth_number}`" class="px-1">
            <button
              class="perio-cell-cycle"
              :disabled="readonly || !tooth.is_present"
              :title="t('periodontogram.arch.furcaVTitle')"
              @click="onToothCycle(tooth, 'furcation_buccal')"
            >{{ furcaGlyph(tooth.furcation_buccal) }}</button>
          </td>
        </tr>
        <tr>
          <th scope="row" class="px-1 text-right font-medium text-muted">{{ t('periodontogram.arch.prognosis') }}</th>
          <td v-for="tooth in orderedTeeth" :key="`pron-${tooth.tooth_number}`" class="px-1">
            <button
              class="perio-cell-cycle"
              :disabled="readonly || !tooth.is_present"
              :title="t('periodontogram.arch.prognosisTitle')"
              @click="onToothCycle(tooth, 'prognosis')"
            >{{ prognosisGlyph(tooth.prognosis) }}</button>
          </td>
        </tr>
        <tr>
          <th scope="row" class="px-1 text-right font-medium text-muted">{{ t('periodontogram.arch.mobility') }}</th>
          <td v-for="tooth in orderedTeeth" :key="`mob-${tooth.tooth_number}`" class="px-1">
            <button
              class="perio-cell-cycle"
              :disabled="readonly || !tooth.is_present"
              :title="t('periodontogram.arch.mobilityTitle')"
              @click="onToothCycle(tooth, 'mobility')"
            >{{ mobilityGlyph(tooth.mobility) }}</button>
          </td>
        </tr>
        <tr>
          <th scope="row" class="px-1 text-right font-medium text-muted">{{ t('periodontogram.arch.implant') }}</th>
          <td v-for="tooth in orderedTeeth" :key="`imp-${tooth.tooth_number}`" class="px-1">
            <button
              class="perio-cell-cycle"
              :class="{ 'text-emerald-600 dark:text-emerald-400': tooth.is_implant }"
              :disabled="readonly"
              :title="tooth.is_implant ? t('periodontogram.arch.implantToggleOn') : t('periodontogram.arch.implantToggleOff')"
              @click="onImplantToggle(tooth)"
            >{{ tooth.is_implant ? '●' : '·' }}</button>
          </td>
        </tr>
      </tbody>

      <tfoot v-if="arch === 'lower'">
        <tr>
          <th class="px-1 text-right font-medium text-muted"></th>
          <th
            v-for="tooth in orderedTeeth"
            :key="`fdi-${tooth.tooth_number}`"
            class="px-1 py-1 font-medium text-default"
          >
            {{ tooth.tooth_number }}
          </th>
        </tr>
      </tfoot>
    </table>
  </section>
</template>

<style scoped>
/* Cell-level inline editors. Keep the visual chrome minimal so the
   chart still reads like a SEPA paper chart, but surface every cell
   as a single-click target. */

.perio-cell-cycle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  padding: 0 4px;
  border-radius: 4px;
  border: 1px solid transparent;
  background: transparent;
  font-family: inherit;
  font-size: inherit;
  color: inherit;
  cursor: pointer;
  transition: background-color 100ms ease, border-color 100ms ease;
}

.perio-cell-cycle:hover:not(:disabled) {
  background-color: var(--perio-cell-hover);
}

.perio-cell-cycle:focus-visible {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 1px var(--color-primary);
}

.perio-cell-cycle:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.perio-cell-input {
  width: 100%;
  padding: 0 2px;
  border: 1px solid transparent;
  background: transparent;
  font-family: inherit;
  font-size: inherit;
  color: var(--color-text);
  text-align: center;
  font-variant-numeric: tabular-nums;
  appearance: textfield;
  -moz-appearance: textfield;
  border-radius: 3px;
  transition: background-color 100ms ease, border-color 100ms ease;
}

.perio-cell-input::-webkit-outer-spin-button,
.perio-cell-input::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.perio-cell-input:hover:not(:disabled) {
  background-color: var(--perio-cell-hover);
}

.perio-cell-input:focus {
  outline: none;
  background-color: var(--color-surface);
  border-color: var(--perio-cell-focus-ring);
  box-shadow: 0 0 0 1px var(--perio-cell-focus-ring);
}

.perio-cell-input:disabled {
  cursor: not-allowed;
  color: var(--color-text-disabled);
}

.perio-cell-input--site {
  width: 14px;
  padding: 0;
  font-weight: 600;
}

.perio-cell-toggle {
  width: 14px;
  height: 14px;
  border-radius: 3px;
  border: 1px solid var(--perio-cell-toggle-border);
  background: var(--perio-cell-toggle-bg);
  cursor: pointer;
  transition: transform 100ms ease, background-color 100ms ease;
}

.perio-cell-toggle:hover:not(:disabled) {
  transform: scale(1.1);
}

.perio-cell-toggle:focus-visible {
  outline: none;
  box-shadow: 0 0 0 2px var(--color-primary);
}

/* Calm-design pastel fills — soft background + accent border so the
   marker reads as "on" without shouting. Matches the alert / badge
   tonal scale used across the rest of DentalPin. */
.perio-cell-toggle--bop.is-on {
  background-color: var(--color-danger-soft);
  border-color: var(--color-danger-accent);
}

.perio-cell-toggle--plaque.is-on {
  background-color: var(--color-primary-soft);
  border-color: var(--color-primary);
}

.perio-cell-toggle:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

/* Soft tinted bands behind site metric rows. Vestibular = amber,
   palatal/lingual = sky. Tokens flip the tint for dark mode so the
   bands stay readable on a dark surface. */
.perio-row-vestibular {
  background-color: var(--perio-vestibular-row);
}

.perio-row-palatal {
  background-color: var(--perio-palatal-row);
}

.perio-arch-table .tooth-row td {
  padding-top: 4px;
  padding-bottom: 4px;
}

/* The tooth row's label <th> is the positioning anchor for the SEPA
   profile overlay. Tables don't honor `position: relative` reliably on
   <tr>, but they DO on <th> / <td>, so we hang the absolute overlay
   off the row's first cell and stretch it across the tooth columns
   to the right. */
.perio-arch-table .perio-row-anchor {
  position: relative;
}

.perio-profile-anchor {
  position: absolute;
  /* Label column is 96 px (first <col>). Position overlay to start at
     the tooth columns and extend explicitly across them — `right: 0`
     wouldn't work because the th cell that anchors us is only 96 px
     wide, so the overlay would collapse. Width is set inline from
     `profileOverlayWidth` on the template. */
  left: 96px;
  height: 60px;
  pointer-events: none;
  z-index: 5;
}

.perio-profile-anchor--top {
  /* Outer row (vestibular upper, lingual lower) — markers rendered
     below the tooth, SVG sits at the top of the cell after the 4 px
     td padding. With VIEW_H=150 and TARGET_GUM_VB_Y=97.5, the gum
     line lands at within-SVG cellY = 97.5/150 × 112 ≈ 72.8, so the
     gum row-Y = 4 + 72.8 ≈ 77. Strip baseline (depth-up) sits at the
     strip's bottom edge → top = 77 − 60 = 17. */
  top: 17px;
}

.perio-profile-anchor--bottom {
  /* Inner row (palatal upper, vestibular lower) — markers rendered
     ABOVE the tooth, pushing the SVG down by markers (h-4 = 16 px) +
     gap (2 px) = 18 px, so SVG row-Y = 4 + 18 = 22. The face flip
     puts the gum at within-SVG cellY = 112 − 72.8 ≈ 39.2, so gum
     row-Y = 22 + 39.2 ≈ 61. Strip baseline (depth-down) sits at the
     strip's top edge → top = 61. */
  top: 61px;
  bottom: auto;
}
</style>
