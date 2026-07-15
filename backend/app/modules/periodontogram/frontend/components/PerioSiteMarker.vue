<script setup lang="ts">
/**
 * Tiny dot rendering a single probing site.
 *
 * Colour is driven by `probing_depth_mm` via the heatmap composable.
 * Bleeding and plaque state is shown in the metric table rows (Sangrado
 * / Placa) — keeping it out of the marker avoids visual duplication.
 */
import { computed } from 'vue'
import type { PerioSite } from '../types'
import { probingDepthClasses } from '../composables/usePerioHeatmap'

const props = defineProps<{
  site: PerioSite | null
  size?: 'sm' | 'md'
  /** Display-only mode — no hover scale, no click handler. */
  readonly?: boolean
}>()

const colourClass = computed(() => probingDepthClasses(props.site?.probing_depth_mm ?? null))
// Tap targets bump to 44px on touch devices via the @media block in
// the style section below. Visual size stays compact on desktop.
const sizeClass = computed(() => (props.size === 'sm' ? 'h-4 w-4 text-[10px]' : 'h-5 w-5 text-xs'))

const { t } = useI18n()
</script>

<template>
  <span
    class="perio-site-marker inline-flex items-center justify-center rounded-full font-mono font-medium ring-1 ring-inset"
    :class="[colourClass, sizeClass]"
    :aria-label="t('periodontogram.arch.siteMarkerAria', { code: site?.site_code ?? '', depth: site?.probing_depth_mm ?? t('common.noValue') })"
  >
    <span v-if="site?.probing_depth_mm != null">{{ site.probing_depth_mm }}</span>
    <span v-else>·</span>
  </span>
</template>

<style scoped>
.perio-site-marker {
  position: relative;
}

@media (pointer: coarse) {
  .perio-site-marker {
    min-width: 44px;
    min-height: 44px;
  }
}
</style>
